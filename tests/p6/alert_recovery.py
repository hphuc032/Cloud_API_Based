"""Observe actual provisioned engine transitions; never fabricate Loki events."""
import json,time
from pathlib import Path
import httpx
from test_observability import grafana

def states(c,uids):
 r=c.get('/api/prometheus/grafana/api/v1/rules');r.raise_for_status()
 rules={r['name'].removeprefix('P6 '):r for g in r.json()['data']['groups'] for r in g['rules']}
 return {uid:rules[uid.removeprefix('p6-')] for uid in uids}

def observe(c,uids,target,seconds=110):
 snapshots=[];deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  rows=states(c,uids)
  snapshots.append({'utc_epoch':time.time(),'rules':{k:{f:v.get(f) for f in ('state','health','lastEvaluation','evaluationTime','alerts')} for k,v in rows.items()}})
  if all(v.get('state')==target and v.get('health')=='ok' for v in rows.values()):return snapshots
  time.sleep(2)
 failure={'target':target,'states':snapshots,'passed':False}
 save('failure-'+str(time.time_ns()),failure)
 raise AssertionError(json.dumps(failure))

def query_values(c,uids):
 rules=c.get('/api/v1/provisioning/alert-rules').json();out={}
 with httpx.Client(trust_env=False,timeout=10) as lc:
  for r in rules:
   if r['uid'] not in uids:continue
   expr=r['data'][0]['model']['expr'];q=lc.get('http://loki:3100/loki/api/v1/query',params={'query':expr});q.raise_for_status()
   value=float(q.json()['data']['result'][0]['value'][1]);threshold=r['data'][1]['model']['conditions'][0]['evaluator']['params'][0]
   assert value>threshold,(r['uid'],value,threshold)
   out[r['uid']]={'expr':expr,'value':value,'threshold':threshold,'for':r['for'],'window_seconds':60,'evaluation_interval_seconds':10}
 return out

def save(name,data):
 Path('/results/p6-alert-'+name+'.json').write_text(json.dumps(data,indent=2))
