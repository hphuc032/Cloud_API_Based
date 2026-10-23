"""Controlled lifecycle probes; run only by P6 disposable project runner."""
import json,sys,time
from deployment.common import configure_application
configure_application()
sys.path[:0]=["/tests/p2","/tests/p3","/tests/p4","/tests/p5"]
from pathlib import Path
import httpx
from transport import http_client
from test_observability import ingested,query

stage=sys.argv[1];path=Path('/results/p6-lifecycle.json')
data=json.loads(path.read_text()) if path.exists() else {}
if stage=='initial':
 with http_client('https://kong:8443') as c:r=c.get('/health')
 assert r.status_code==200
 rid=r.headers['x-request-id'];ingested('kong','http_request',rid);ingested('backend','http_request',rid)
 data['request_id']=rid
 data['before_restart']={s:len(query('{service="'+s+'"} | json | request_id="'+rid+'"')) for s in ['kong','backend']}
 assert data['before_restart']=={'kong':1,'backend':1}
elif stage=='recovered':
 rid=data['request_id']
 ingested('kong','http_request',rid)
 data['after_restart']={s:len(query('{service="'+s+'"} | json | request_id="'+rid+'"')) for s in ['kong','backend']}
 assert data['before_restart']==data['after_restart']
 with http_client('https://kong:8443') as c:r=c.get('/health')
 assert r.status_code==200
 ingested('backend','http_request',r.headers['x-request-id'])
 data['new_event_after_restart']=True
elif stage=='outage':
 from alert_recovery import grafana,observe,query_values,save
 with grafana() as gc:
  uids=['p6-upstream-errors'];initial=observe(gc,uids,'inactive')
  with http_client('https://kong:8443') as c:
   for _ in range(8):
    r=c.get('/health');assert r.status_code in (502,503)
  ingested('kong','upstream_error',r.headers['x-request-id'])
  values=query_values(gc,uids);firing=observe(gc,uids,'firing',65)
  recovery=observe(gc,uids,'inactive',110)
  save('upstream-errors',{'passed':True,'external_delivery_tested':False,'initial':initial,'queries':values,'firing':firing,'recovery':recovery})
  assert any(s['rules'][uids[0]]['state']=='pending' for s in firing)
 ingested('kong','upstream_error',r.headers['x-request-id'])
 data['controlled_backend_outage']={'status':r.status_code,'request_id':r.headers['x-request-id'],'ingested':True}
else:raise ValueError(stage)
path.write_text(json.dumps(data,indent=2))
print(json.dumps({'stage':stage,'passed':True}))
