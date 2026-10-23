"""Fresh-volume retention experiment, never against an existing Loki deployment.

Direct synthetic storage probes are not evidence of security event collection.
The 168h policy is unchanged. Delay/flush/index synchronization are accelerated;
a graceful stop hands over indexes and an independent reader verifies the store.
"""
import json,subprocess,tempfile,uuid,sys,time,os
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CLIENT=r'''
import json,time,urllib.request,urllib.parse,re
from pathlib import Path
base='http://127.0.0.1:3100'
# Private storage/RPC probe never uses inherited external HTTP proxies.
http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
import sys,base64,hashlib
phase=sys.argv[1]
def is_chunk(p):
 try:return base64.b64decode(p.name+'===').decode().startswith('fake/')
 except Exception:return False
def files():
 return {str(p.relative_to('/storage')):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in Path('/storage/chunks').rglob('*') if p.is_file() and 'index' not in p.relative_to('/storage/chunks').parts and is_chunk(p)}
def get(path):return http.open(base+path,timeout=5).read().decode()
def compactor_metrics():return http.open('http://loki:3100/metrics',timeout=5).read().decode()
def post(path,data=None):
 body=json.dumps(data).encode() if data is not None else b''
 return http.open(urllib.request.Request(base+path,data=body,headers={'Content-Type':'application/json'}),timeout=5).status
for _ in range(50):
 try:
  if get('/ready').strip()=='ready':break
 except Exception:pass
 time.sleep(1)
else:raise AssertionError('Disposable Loki not ready')
def count(age,ts,origin=base):
 params=urllib.parse.urlencode({'query':'{service="retention-probe",age="'+age+'"}','start':str(ts-10**9),'end':str(ts+10**9),'limit':10})
 result=json.loads(http.open(origin+'/loki/api/v1/query_range?'+params,timeout=5).read())
 return sum(len(s['values']) for s in result['data']['result'])
state=Path('/evidence/seed.json')
if phase=='seed':
 now=time.time_ns();old=now-8*86400*10**9
 payload={'streams':[{'stream':{'service':'retention-probe','age':age},'values':[[str(ts),'synthetic retention-only storage probe']]} for age,ts in [('old',old),('current',now)]]}
 attempts=[]
 for _ in range(30):
  try:
   assert post('/loki/api/v1/push',payload)==204;break
  except urllib.error.HTTPError as exc:
   attempts.append({'status':exc.code,'body':exc.read().decode()});time.sleep(1)
 else:raise AssertionError(attempts)
 logical=[]
 for _ in range(30):
  logical.append({'old':count('old',old),'current':count('current',now)})
  if logical[-1]=={'old':0,'current':1}:break
  time.sleep(1)
 else:raise AssertionError('Writer logical lookback/current control: '+json.dumps(logical))
 assert post('/flush') in (200,204)
 for _ in range(30):
  initial_files=files()
  if len(initial_files)>=2:break
  time.sleep(1)
 assert len(initial_files)==2,initial_files
 state.write_text(json.dumps({'now':now,'old':old,'files':initial_files,'push_status':204,'writer_logical_visibility':logical},indent=2))
 print('Seed chunks:',initial_files);sys.exit(0)
Path('/evidence/runtime-config.yml').write_text(get('/config'))
seed=json.loads(state.read_text());now=seed['now'];old=seed['old']
initial=[]
for _ in range(15):
 initial.append({'old':count('old',old),'current':count('current',now)})
 if initial[-1]['current']==1:break
 time.sleep(1)
else:
 Path('/evidence/retention.json').write_text(json.dumps({'passed':False,'stage':'initial visibility','initial':initial},indent=2))
 raise AssertionError('Current control sample not visible: '+json.dumps(initial))
received_metrics=[x for x in compactor_metrics().splitlines() if not x.startswith('#') and 'lines_received' in x]
snapshots=[];passed=False;started=time.monotonic()
def chunk_age(path):
 try:
  key=base64.b64decode(Path(path).name+'===').decode();start=int(key.split(':')[1],16)
  return 'old' if abs(start-old//10**6)<1000 else 'current' if abs(start-now//10**6)<1000 else 'unknown'
 except Exception:return 'unknown'
old_files=[p for p in seed['files'] if chunk_age(p)=='old'];current_files=[p for p in seed['files'] if chunk_age(p)=='current']
assert len(old_files)==len(current_files)==1,(seed,old_files,current_files)
for _ in range(120):
 metrics=[x for x in compactor_metrics().splitlines() if not x.startswith('#') and 'retention' in x and ('deleted' in x or 'marker' in x)]
 snapshots.append({'old_count':count('old',old),'current_count':count('current',now),'retention_metrics':metrics,'files':files(),'elapsed_seconds':time.monotonic()-started})
 deletion=any('retention_sweeper_chunk_deleted_duration_seconds_count' in line and 'status="success"' in line and float(line.split()[-1])>0 for line in metrics)
 if snapshots[-1]['old_count']==0 and snapshots[-1]['current_count']==1 and deletion and all(p not in files() for p in old_files) and all(files().get(p)==seed['files'][p] for p in current_files):
  passed=True;break
 time.sleep(5)
writer_queries={'old':count('old',old,'http://loki:3100'),'current':count('current',now,'http://loki:3100')}
passed=passed and writer_queries=={'old':0,'current':1}
Path('/evidence/retention.json').write_text(json.dumps({'passed':passed,'writer_queries_after_deletion':writer_queries,'target_retention_hours':168,'synthetic_old_age_days':8,'accelerated_delete_delay_seconds':1,'initial_visibility':initial,'accepted_push_status':204,'received_metrics':received_metrics,'seed':seed,'old_files':old_files,'current_files':current_files,'snapshots':snapshots},indent=2))
assert passed,'Retention not independently confirmed by query and successful physical-deletion metric'
print('PASS: expired sample physically deleted; current sample retained')
'''

def main():
 project='cloud-api-p6-retention-'+uuid.uuid4().hex[:10]
 artifacts=ROOT/'tests/p6/artifacts'/project;artifacts.mkdir(parents=True,exist_ok=True)
 probe_image=os.environ.get('P6_RETENTION_PROBE_IMAGE','python:3.11-slim')
 commands=[];result=1;started_utc=datetime.now(timezone.utc).isoformat()
 with tempfile.TemporaryDirectory(prefix=project) as directory:
  temp=Path(directory);cfg=(ROOT/'monitoring/loki/p6-loki.yml').read_text().replace('  log_level: warn','  log_level: info')
  cfg=cfg.replace('  retention_period: 168h','  retention_period: 168h\n  reject_old_samples: false').replace('  compaction_interval: 1m','  compaction_interval: 5s').replace('  retention_delete_delay: 2h','  retention_delete_delay: 1s')
  cfg=cfg.replace('storage_config:','storage_config:\n  index_cache_validity: 5s')
  cfg+='\nquerier:\n  query_ingesters_within: 0s\n\ningester:\n  chunk_idle_period: 1s\n  max_chunk_age: 1m\n  chunk_retain_period: 0s\n  flush_check_period: 1s\n'
  cfg=cfg.replace('    cache_location: /loki/cache','    cache_location: /loki/cache\n    resync_interval: 5s')
  (temp/'loki.yml').write_text(cfg);(temp/'loki.yml').chmod(0o644)
  (temp/'probe.py').write_text(CLIENT);(temp/'probe.py').chmod(0o644)
  compose={'services':{'loki':{'image':'grafana/loki:2.9.8','environment':{'HTTP_PROXY':'','HTTPS_PROXY':'','ALL_PROXY':'','http_proxy':'','https_proxy':'','all_proxy':'','NO_PROXY':'*','no_proxy':'*'},'command':['-config.file=/etc/loki/p6.yml'],'volumes':[str(temp/'loki.yml')+':/etc/loki/p6.yml:ro','data:/loki'],'networks':['storage']}},'networks':{'storage':{'internal':True}},'volumes':{'data':{}}}
  reader_cfg=cfg.replace('  max_query_lookback: 168h','  max_query_lookback: 0s').replace('  query_ingesters_within: 0s','  query_store_only: true').replace('/loki/index','/tmp/p6-reader/index').replace('/loki/cache','/tmp/p6-reader/cache').replace('path_prefix: /loki','path_prefix: /tmp/p6-reader')
  reader_cfg=reader_cfg.replace('common:','common:\n  compactor_address: http://loki:3100')
  (temp/'reader.yml').write_text(reader_cfg);(temp/'reader.yml').chmod(0o644)
  compose['services']['reader']={'image':'grafana/loki:2.9.8','environment':compose['services']['loki']['environment'],'command':['-target=querier','-config.file=/etc/loki/reader.yml'],'volumes':[str(temp/'reader.yml')+':/etc/loki/reader.yml:ro','data:/loki:ro'],'networks':['storage'],'read_only':True,'tmpfs':['/tmp'],'cap_drop':['ALL'],'security_opt':['no-new-privileges:true']}
  (temp/'compose.json').write_text(json.dumps(compose))
  base=['docker','compose','-p',project,'-f',str(temp/'compose.json')]
  def run(args,**kw):
   commands.append(args);return subprocess.run(args,**kw)
  try:
   run(base+['up','-d','loki'],check=True)
   cid=subprocess.check_output(base+['ps','-q','loki'],text=True).strip()
   version=run(['docker','run','--rm','--entrypoint','/usr/bin/loki','grafana/loki:2.9.8','-version'],capture_output=True,text=True)
   (artifacts/'version.txt').write_text(version.stdout+version.stderr)
   def probe(phase):
    return run(['docker','run','--rm','--network','container:'+cid,'--entrypoint','python','-v',str(temp/'probe.py')+':/probe.py:ro','-v',str(artifacts)+':/evidence','-v',project+'_data:/storage:ro',probe_image,'/probe.py',phase]).returncode
   assert probe('seed')==0
   run(base+['stop','--timeout','60','loki'],check=True)
   run(base+['up','-d','loki'],check=True)
   run(base+['up','-d','reader'],check=True)
   cid=subprocess.check_output(base+['ps','-q','reader'],text=True).strip()
   result=probe('verify')
   log=run(base+['logs','--no-color'],capture_output=True,text=True)
   (artifacts/'loki.txt').write_text(log.stdout+log.stderr)
  finally:
   log=run(base+['logs','--no-color'],capture_output=True,text=True)
   (artifacts/'loki.txt').write_text(log.stdout+log.stderr)
   (artifacts/'config.yml').write_text(cfg)
   (artifacts/'reader-config.yml').write_text(reader_cfg)
   cleanup=run(base+['down','--volumes','--timeout','10']).returncode
   (artifacts/'run.json').write_text(json.dumps({'project':project,'exit_code':result,'cleanup_exit':cleanup,'commands':commands,'started_utc':started_utc,'finished_utc':datetime.now(timezone.utc).isoformat()},indent=2))
 return result
if __name__=='__main__':sys.exit(main())
