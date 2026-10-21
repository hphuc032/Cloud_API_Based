"""Fresh-volume retention experiment, never against an existing Loki deployment.

Direct synthetic storage probes are not evidence of security event collection.
Only delete delay/compaction/flush and old-sample admission are accelerated.
"""
import json,subprocess,tempfile,uuid,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CLIENT=r'''
import json,time,urllib.request,urllib.parse,re
from pathlib import Path
base='http://127.0.0.1:3100'
def get(path):return urllib.request.urlopen(base+path,timeout=5).read().decode()
def post(path,data=None):
 body=json.dumps(data).encode() if data is not None else b''
 return urllib.request.urlopen(urllib.request.Request(base+path,data=body,headers={'Content-Type':'application/json'}),timeout=5).status
for _ in range(50):
 try:
  if get('/ready').strip()=='ready':break
 except Exception:pass
 time.sleep(1)
else:raise AssertionError('Disposable Loki not ready')
now=time.time_ns();old=now-8*86400*10**9
payload={'streams':[{'stream':{'service':'retention-probe','age':age},'values':[[str(ts),'synthetic retention-only storage probe']]} for age,ts in [('old',old),('current',now)]]}
assert post('/loki/api/v1/push',payload)==204

def count(age,ts):
 params=urllib.parse.urlencode({'query':'{service="retention-probe",age="'+age+'"}','start':str(ts-10**9),'end':str(ts+10**9),'limit':10})
 result=json.loads(get('/loki/api/v1/query_range?'+params))
 return sum(len(s['values']) for s in result['data']['result'])
initial=[]
for _ in range(15):
 initial.append({'old':count('old',old),'current':count('current',now)})
 if initial[-1]['current']==1:break
 time.sleep(1)
else:
 Path('/evidence/retention.json').write_text(json.dumps({'passed':False,'stage':'initial visibility','initial':initial},indent=2))
 raise AssertionError('Current control sample not visible: '+json.dumps(initial))
received_metrics=[x for x in get('/metrics').splitlines() if not x.startswith('#') and 'lines_received' in x]
assert post('/flush') in (200,204)
snapshots=[];passed=False
for _ in range(96):
 metrics=[x for x in get('/metrics').splitlines() if not x.startswith('#') and 'retention' in x and ('deleted' in x or 'marker' in x)]
 snapshots.append({'old_count':count('old',old),'current_count':count('current',now),'retention_metrics':metrics})
 deletion=any('chunk' in line and 'deleted' in line and 'status="success"' in line and float(line.split()[-1])>0 for line in metrics)
 if snapshots[-1]['old_count']==0 and snapshots[-1]['current_count']==1 and deletion:
  passed=True;break
 time.sleep(5)
Path('/evidence/retention.json').write_text(json.dumps({'passed':passed,'target_retention_hours':168,'synthetic_old_age_days':8,'accelerated_delete_delay_seconds':1,'initial_visibility':initial,'accepted_push_status':204,'received_metrics':received_metrics,'snapshots':snapshots},indent=2))
assert passed,'Retention not independently confirmed by query and successful physical-deletion metric'
print('PASS: expired sample physically deleted; current sample retained')
'''

def main():
 project='cloud-api-p6-retention-'+uuid.uuid4().hex[:10]
 artifacts=ROOT/'tests/p6/artifacts/retention';artifacts.mkdir(parents=True,exist_ok=True)
 commands=[];result=1
 with tempfile.TemporaryDirectory(prefix=project) as directory:
  temp=Path(directory);cfg=(ROOT/'monitoring/loki/p6-loki.yml').read_text().replace('  log_level: warn','  log_level: info')
  cfg=cfg.replace('  retention_period: 168h','  retention_period: 168h\n  reject_old_samples: false').replace('  compaction_interval: 1m','  compaction_interval: 5s').replace('  retention_delete_delay: 2h','  retention_delete_delay: 1s')
  cfg+='\nquerier:\n  query_ingesters_within: 0s\n\ningester:\n  chunk_idle_period: 1s\n  max_chunk_age: 1m\n  chunk_retain_period: 0s\n  flush_check_period: 1s\n'
  (temp/'loki.yml').write_text(cfg);(temp/'loki.yml').chmod(0o644)
  (temp/'probe.py').write_text(CLIENT);(temp/'probe.py').chmod(0o644)
  compose={'services':{'loki':{'image':'grafana/loki:2.9.8','command':['-config.file=/etc/loki/p6.yml'],'volumes':[str(temp/'loki.yml')+':/etc/loki/p6.yml:ro','data:/loki'],'networks':['storage']}},'networks':{'storage':{'internal':True}},'volumes':{'data':{}}}
  (temp/'compose.json').write_text(json.dumps(compose))
  base=['docker','compose','-p',project,'-f',str(temp/'compose.json')]
  def run(args,**kw):
   commands.append(args);return subprocess.run(args,**kw)
  try:
   run(base+['up','-d'],check=True)
   cid=subprocess.check_output(base+['ps','-q','loki'],text=True).strip()
   result=run(['docker','run','--rm','--network','container:'+cid,'--entrypoint','python','-v',str(temp/'probe.py')+':/probe.py:ro','-v',str(artifacts)+':/evidence','cloud-api-backend-flat:verified','/probe.py']).returncode
   log=run(base+['logs','--no-color'],capture_output=True,text=True)
   (artifacts/'loki.txt').write_text(log.stdout+log.stderr)
  finally:
   cleanup=run(base+['down','--volumes','--timeout','10']).returncode
   (artifacts/'run.json').write_text(json.dumps({'project':project,'exit_code':result,'cleanup_exit':cleanup,'commands':commands},indent=2))
 return result
if __name__=='__main__':sys.exit(main())
