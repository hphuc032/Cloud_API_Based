"""P5 real SQL transactions, genuine P4 tokens, and deterministic validator tests."""
import hashlib,hmac,json,os,secrets,socket,time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from pathlib import Path
import httpx,psycopg2,pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from main import app
from app.config import settings
from app.routes import security,webhooks
from app.models.product import Product
from test_cutover import headers,tokens,client,backend,admin,identity,oidc_user

@pytest.fixture
def local():
    with TestClient(app,raise_server_exceptions=False) as c:yield c

def envelope(**changes):
    return dict(event='payment.success',event_id='p5-'+uuid4().hex,order_id='disposable-ack-only',**changes)

def signed(body,secret=None,ts=None):
    ts=str(ts if ts is not None else int(time.time()))
    mac=hmac.new((secret or settings.WEBHOOK_SECRET).encode(),ts.encode()+b'.'+body,hashlib.sha256).hexdigest()
    return {'X-Timestamp':ts,'X-Signature':'sha256='+mac,'Content-Type':'application/json'}

def raw(payload):return json.dumps(payload,separators=(',',':')).encode()

def receipt(event_id):
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
        cur.execute('SELECT payload_sha256,response FROM webhook_receipts WHERE provider=%s AND event_id=%s',
                    (settings.WEBHOOK_PROVIDER,'id:'+event_id));return cur.fetchall()

@pytest.mark.parametrize('payload',[[],None,True,1,'text',{}, {'event':[]},{'event':None},{'event':''},
 {'event':'payment.success'},{'event':'order.shipped','order_id':3},{'event':'unknown','event_id':None}])
def test_webhook_typed_object(local,payload):
    body=raw(payload);r=local.post('/api/v1/webhooks/receive',content=body,headers=signed(body))
    # Explicit null event_id is a compatibility fallback, not malformed identity.
    assert r.status_code==(200 if payload=={'event':'unknown','event_id':None} else 400)

@pytest.mark.parametrize('body',[b'{',b'{"event":"unknown","event":"payment.success"}',b'{"event":"unknown","data":NaN}',b'\xff'])
def test_webhook_malformed_json(local,body):
    assert local.post('/api/v1/webhooks/receive',content=body,headers=signed(body)).status_code==400

@pytest.mark.parametrize('kind',['missing','short','uppercase','unicode','wrong-secret','changed-body','changed-time','expired','future'])
def test_webhook_auth_negatives(local,kind):
    body=raw(envelope());h=signed(body)
    if kind=='missing':h.pop('X-Signature')
    elif kind=='short':h['X-Signature']='sha256=aa'
    elif kind=='uppercase':h['X-Signature']=h['X-Signature'].upper()
    elif kind=='unicode':h['X-Signature']='sha256='+'é'*64
    elif kind=='wrong-secret':h=signed(body,secrets.token_hex(32))
    elif kind=='changed-body':body+=b' '
    elif kind=='changed-time':h['X-Timestamp']=str(int(h['X-Timestamp'])-1)
    elif kind=='expired':h=signed(body,ts=int(time.time())-1000)
    elif kind=='future':h=signed(body,ts=int(time.time())+1000)
    # TestClient/httpx forbids non-ASCII headers at its client layer as well.
    if kind=='unicode':assert webhooks._verify_signature(body,h['X-Timestamp'],h['X-Signature']) is False;return
    assert local.post('/api/v1/webhooks/receive',content=body,headers=h).status_code==(401 if kind=='missing' else 403)

@pytest.mark.parametrize('streamed',[False,True])
def test_webhook_body_bound(local,streamed):
    body=b'x'*(settings.WEBHOOK_MAX_BODY_BYTES+1)
    content=(chunk for chunk in [body[:100],body[100:]]) if streamed else body
    assert local.post('/api/v1/webhooks/receive',content=content,headers=signed(body)).status_code==413


def test_duplicate_acknowledgement_once(local,monkeypatch):
    body=raw(envelope());event_id=json.loads(body)['event_id'];calls=[];original=webhooks._handle_event
    def handler(kind,payload,db):calls.append(kind);return original(kind,payload,db)
    monkeypatch.setattr(webhooks,'_handle_event',handler)
    first=local.post('/api/v1/webhooks/receive',content=body,headers=signed(body))
    second=local.post('/api/v1/webhooks/receive',content=body,headers=signed(body))
    assert first.status_code==second.status_code==200
    assert first.json()==second.json() and second.headers['x-webhook-replayed']=='true'
    assert len(calls)==len(receipt(event_id))==1


def test_concurrent_duplicates_real_postgres(local,monkeypatch):
    body=raw(envelope());event_id=json.loads(body)['event_id'];calls=[];original=webhooks._handle_event
    def handler(kind,payload,db):calls.append(kind);time.sleep(.1);return original(kind,payload,db)
    monkeypatch.setattr(webhooks,'_handle_event',handler)
    def send(_):
        with TestClient(app,raise_server_exceptions=False) as c:return c.post('/api/v1/webhooks/receive',content=body,headers=signed(body))
    with ThreadPoolExecutor(max_workers=8) as pool:responses=list(pool.map(send,range(8)))
    assert all(r.status_code==200 for r in responses)
    assert len({json.dumps(r.json(),sort_keys=True) for r in responses})==1
    assert len(calls)==len(receipt(event_id))==1
    assert sum(r.headers['x-webhook-replayed']=='false' for r in responses)==1


def test_same_event_conflict_and_canonical_retry(local):
    obj=envelope();body=raw(obj)
    first=local.post('/api/v1/webhooks/receive',content=body,headers=signed(body));assert first.status_code==200
    equivalent=json.dumps(obj,indent=2).encode()
    retry=local.post('/api/v1/webhooks/receive',content=equivalent,headers=signed(equivalent));assert retry.status_code==200
    assert retry.json()==first.json()
    conflicting=raw(dict(obj,order_id='different'))
    assert local.post('/api/v1/webhooks/receive',content=conflicting,headers=signed(conflicting)).status_code==409
    assert len(receipt(obj['event_id']))==1


def test_failed_operation_rolls_back_receipt_and_effect(local,monkeypatch,product):
    body=raw(envelope());event_id=json.loads(body)['event_id'];original=webhooks._handle_event
    def fail(kind,payload,db):
        # Isolated injected failure only: no production settlement is implemented.
        row=db.get(Product,product.id);row.stock_quantity=0;db.flush()
        raise HTTPException(503,'Injected disposable processing failure')
    monkeypatch.setattr(webhooks,'_handle_event',fail)
    assert local.post('/api/v1/webhooks/receive',content=body,headers=signed(body)).status_code==503
    assert receipt(event_id)==[]
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
        cur.execute('SELECT stock_quantity FROM products WHERE id=%s',(str(product.id),));assert cur.fetchone()[0]==100
    monkeypatch.setattr(webhooks,'_handle_event',original)
    assert local.post('/api/v1/webhooks/receive',content=body,headers=signed(body)).status_code==200
    assert len(receipt(event_id))==1


def test_secret_overlap_and_retirement(local,monkeypatch):
    body=raw(envelope());old=secrets.token_hex(32);now=int(time.time())
    monkeypatch.setattr(settings,'WEBHOOK_PREVIOUS_SECRET',old)
    monkeypatch.setattr(settings,'WEBHOOK_PREVIOUS_START',now-1)
    monkeypatch.setattr(settings,'WEBHOOK_PREVIOUS_UNTIL',now+60)
    assert local.post('/api/v1/webhooks/receive',content=body,headers=signed(body,old)).status_code==200
    assert local.post('/api/v1/webhooks/receive',content=body,headers=signed(body)).status_code==200
    monkeypatch.setattr(settings,'WEBHOOK_PREVIOUS_UNTIL',now-1)
    assert local.post('/api/v1/webhooks/receive',content=body,headers=signed(body,old)).status_code==403
    assert local.post('/api/v1/webhooks/receive',content=body,headers=signed(body)).status_code==200

@pytest.mark.parametrize('ip',['127.0.0.1','10.0.0.1','169.254.169.254','100.64.0.1','0.0.0.0','224.0.0.1','240.0.0.1',
 '192.0.2.1','198.18.0.1','::','::1','fc00::1','fe80::1','ff02::1','2001:db8::1','::ffff:127.0.0.1','::ffff:169.254.169.254',
 '64:ff9b::a9fe:a9fe','2002:7f00:1::','2001:0000:4136:e378:8000:63bf:3fff:fdd2'])
def test_ssrf_address_matrix(ip):assert security._is_blocked_ip(ip)

@pytest.mark.parametrize('ip',['93.184.216.34','2606:4700:4700::1111','::ffff:93.184.216.34'])
def test_ssrf_public_addresses(ip):assert not security._is_blocked_ip(ip)

@pytest.mark.parametrize('answers',[['93.184.216.34','::ffff:127.0.0.1'],['93.184.216.34','240.0.0.1'],['invalid']])
def test_ssrf_mixed_dns_fails_closed(monkeypatch,answers):
    monkeypatch.setattr(security.socket,'getaddrinfo',lambda *a:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,0)) for ip in answers])
    with pytest.raises(HTTPException):security._validate_public_url('https://example.com')

@pytest.mark.parametrize('url',['https://user:pass@example.com','https://example.com:99999','https://example.com\\@evil.test',
 'https://example.com..','https://-bad.example.com','http://2130706433','http://0177.0.0.1','http://0x7f000001','https://[::ffff:127.0.0.1]'])
def test_ssrf_parser_edges(local,headers,url):
    assert local.post('/api/v1/security/fetch-url',headers=headers('staff'),json={'url':url}).status_code in (400,403,422)

@pytest.mark.parametrize('field',['price','name','stock_quantity','is_active'])
def test_product_null_no_partial_mutation(local,headers,product,field):
    r=local.patch('/api/v1/products/'+str(product.id),headers=headers('staff'),json={'name':'must-not-apply',field:None})
    assert r.status_code==422
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
        cur.execute('SELECT name,price,stock_quantity,is_active FROM products WHERE id=%s',(str(product.id),));row=cur.fetchone()
        assert row[0]=='Baseline product' and float(row[1])==12.5 and row[2:]==(100,True)

@pytest.mark.parametrize('field',['role','is_active','is_verified'])
def test_user_null_no_partial_mutation(local,headers,users,field):
    assert local.patch('/api/v1/users/'+str(users['customer'].id),headers=headers('admin'),json={field:None}).status_code==422
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
        cur.execute('SELECT role,is_active,is_verified FROM users WHERE id=%s',(str(users['customer'].id),));assert cur.fetchone()==('customer',True,False)


def test_receipt_least_privilege():
    with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
        for statement in ['DELETE FROM webhook_receipts',"UPDATE webhook_receipts SET provider='forged'", "UPDATE webhook_receipts SET payload_sha256='forged'",'ALTER TABLE webhook_receipts ADD COLUMN forbidden int']:
            with conn.cursor() as cur,pytest.raises(psycopg2.errors.InsufficientPrivilege):cur.execute(statement)
            conn.rollback()
        with conn.cursor() as cur:cur.execute('SELECT count(*) FROM webhook_receipts')

@pytest.mark.parametrize('patch',[{'price':-1},{'price':0},{'price':10000000000},{'stock_quantity':2147483648},
 {'stock_quantity':-1},{'category_id':'not-a-uuid'},{'is_active':[]},{'name':[]},{'image_url':'https://example.com/'+('x'*500)}])
def test_adjacent_product_validation(local,headers,product,patch):
 assert local.patch('/api/v1/products/'+str(product.id),headers=headers('staff'),json=patch).status_code==422
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
  cur.execute('SELECT price,stock_quantity FROM products WHERE id=%s',(str(product.id),));row=cur.fetchone()
  assert float(row[0])==12.5 and row[1]==100

@pytest.mark.parametrize('number',['Infinity','-Infinity','NaN','1e999'])
def test_nonfinite_price_controlled_without_echo(local,headers,product,number):
 r=local.patch('/api/v1/products/'+str(product.id),headers={**headers('staff'),'Content-Type':'application/json'},content=('{"price":'+number+'}').encode())
 assert r.status_code==422
 assert all('input' not in item and 'ctx' not in item for item in r.json()['detail'])

@pytest.mark.parametrize('value',['owner',{},[],3])
def test_invalid_user_role_no_partial_mutation(local,headers,users,value):
 assert local.patch('/api/v1/users/'+str(users['customer'].id),headers=headers('admin'),json={'role':value}).status_code==422
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
  cur.execute('SELECT role FROM users WHERE id=%s',(str(users['customer'].id),));assert cur.fetchone()[0]=='customer'
