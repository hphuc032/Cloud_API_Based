"""Seed old monitoring storage, upgrade, and restore a cold copy in isolation.

No existing project/volume can be supplied. Passwords stay in temporary secret
files; command receipts contain only paths and safe API result summaries.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[2]


def execute(component, old_image, new_image, output):
    output=output.resolve()
    project='cloud-api-imgupgrade-'+uuid.uuid4().hex[:12]
    network=project+'-storage'
    data=project+'-data'
    backup=project+'-coldcopy'
    name=project+'-server'
    commands=[]
    result={'component':component,'project':project,'status':'RUNNING','commands':commands}
    output.mkdir(parents=True,exist_ok=True)
    label=['--label','florasecure.image-review='+project]
    password=secrets.token_urlsafe(32)

    def run(argv, check=True):
        p=subprocess.run(argv,capture_output=True,text=True)
        commands.append({'argv':argv,'exit_code':p.returncode})
        if check and p.returncode:
            raise RuntimeError('Command failed: '+argv[0]+' '+str(p.returncode))
        return p

    def request(path, payload=None):
        # Keep the storage network internal: the client runs in the exact
        # disposable server namespace, with no published host port or Docker API.
        code='''import sys,json,urllib.request,urllib.error,base64,pathlib
x=json.load(sys.stdin);h={}
if x['component']=='grafana':h['Authorization']='Basic '+base64.b64encode(('admin:'+pathlib.Path('/run/secrets/password').read_text()).encode()).decode()
b=json.dumps(x['payload']).encode() if x['payload'] is not None else None
if b:h['Content-Type']='application/json'
q=urllib.request.Request('http://127.0.0.1:'+str(x['port'])+x['path'],data=b,headers=h)
http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:r=http.open(q,timeout=5)
except urllib.error.HTTPError as e:r=e
except OSError as e:print(json.dumps({'status':0,'error':type(e).__name__}));sys.exit(0)
raw=r.read()
try:body=json.loads(raw) if raw else None
except ValueError:body=raw.decode()
print(json.dumps({'status':r.status,'body':body}))
'''
        argv=['docker','run','--rm','-i','--network','container:'+name,
              '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
              '--mount','type=bind,source='+str(secret)+',target=/run/secrets/password,readonly',
              '--entrypoint','python','python:3.11-slim','-c',code]
        p=subprocess.run(argv,input=json.dumps({'component':component,'port':3000 if component=='grafana' else 3100,
            'path':path,'payload':payload}),capture_output=True,text=True)
        commands.append({'argv':argv,'path':path,'exit_code':p.returncode})
        if p.returncode:raise OSError('Disposable namespace client failed')
        response=json.loads(p.stdout)
        if response['status']==0:raise OSError('Disposable service is not ready')
        if response['status']>=400:raise urllib.error.HTTPError(path,response['status'],'HTTP probe failed',None,None)
        return response['status'],response.get('body')

    def query(phase):
        params=urllib.parse.urlencode({'query':'{service="image-upgrade",phase="'+phase+'"}',
                                     'start':str(time.time_ns()-3600*10**9),'end':str(time.time_ns()+10**9)})
        status,body=request('/loki/api/v1/query_range?'+params)
        assert status==200
        return sum(len(s['values']) for s in body['data']['result'])

    def marker(phase):
        if component=='grafana':
            return request('/api/dashboards/db',{'dashboard':{'uid':'image-review-'+phase,
                'title':'Image review '+phase,'schemaVersion':39,'panels':[],
                'tags':['disposable-image-review']},'overwrite':False})[0]
        return request('/loki/api/v1/push',{'streams':[{'stream':{
            'service':'image-upgrade','phase':phase},'values':[[str(time.time_ns()),'disposable storage marker']]}]})[0]

    def read_marker(phase):
        if component=='loki':return query(phase)
        try:
            status,body=request('/api/dashboards/uid/image-review-'+phase)
            assert status==200 and body['dashboard']['title']=='Image review '+phase
            return 1
        except urllib.error.HTTPError as error:
            if error.code==404:return 0
            raise

    try:
        for ref in [old_image,new_image]:
            info=json.loads(run(['docker','image','inspect',ref]).stdout)[0]
            assert info['Os']=='linux' and info['Architecture']=='amd64'
            result.setdefault('images',[]).append({'reference':ref,'id':info['Id'],
                'repo_digests':info.get('RepoDigests'),'platform':'linux/amd64'})
        run(['docker','network','create','--internal']+label+[network])
        for volume in [data,backup]:run(['docker','volume','create']+label+[volume])
        with tempfile.TemporaryDirectory(prefix=project+'-',dir=output) as temp:
            temp=Path(temp)
            secret=temp/'grafana-password';secret.write_text(password);secret.chmod(0o644)
            config=ROOT/'monitoring/loki/p6-loki.yml'

            def start(image,volume):
                args=['docker','run','-d','--name',name]+label+['--network',network,
                    '--mount','type=volume,source='+volume+
                    ',target='+('/var/lib/grafana' if component=='grafana' else '/loki')]
                if component=='grafana':
                    args+=['--mount','type=bind,source='+str(secret)+',target=/run/secrets/password,readonly',
                           '--mount','type=bind,source='+str(ROOT/'monitoring/p6-grafana')+',target=/etc/grafana/provisioning,readonly',
                           '-e','GF_SECURITY_ADMIN_USER=admin','-e','GF_SECURITY_ADMIN_PASSWORD__FILE=/run/secrets/password',
                           '-e','GF_AUTH_ANONYMOUS_ENABLED=false','-e','GF_USERS_ALLOW_SIGN_UP=false',
                           '-e','GF_ANALYTICS_CHECK_FOR_UPDATES=false','-e','GF_ANALYTICS_REPORTING_ENABLED=false',
                           '-e','GF_LOG_LEVEL=error',image]
                else:
                    args+=['--mount','type=bind,source='+str(config)+',target=/etc/loki/p6.yml,readonly',
                           '-e','HTTP_PROXY=','-e','HTTPS_PROXY=','-e','NO_PROXY=*',image,'-config.file=/etc/loki/p6.yml']
                run(args)
                info=json.loads(run(['docker','inspect',name]).stdout)[0]
                assert not info['HostConfig'].get('PortBindings')
                deadline=time.monotonic()+100
                while time.monotonic()<deadline:
                    try:
                        if component=='grafana':
                            assert request('/api/health')[0]==200
                        else:
                            assert request('/ready')[0]==200
                        break
                    except (OSError,urllib.error.URLError,AssertionError):time.sleep(1)
                else:raise AssertionError('Disposable monitoring service not ready')
                result.setdefault('stages',[]).append({'image_id':info['Image'],
                    'volume':volume,'ready':True,'user':info['Config'].get('User')})

            start(old_image,data)
            assert marker('before') in (200,204)
            deadline=time.monotonic()+30
            while read_marker('before')!=1 and time.monotonic()<deadline:time.sleep(1)
            assert read_marker('before')==1
            if component=='loki':assert request('/flush',{})[0] in (200,204)
            run(['docker','stop','--time','40',name]);run(['docker','rm',name])
            # Cold-copy owned volumes only. Python preserves each file's uid/gid
            # so non-root Grafana/Loki can use the rollback copy unchanged.
            copy_code="""import os,shutil,pathlib
src=pathlib.Path('/source');dst=pathlib.Path('/backup')
shutil.copytree(src,dst,dirs_exist_ok=True)
for p in [src,*src.rglob('*')]:
 s=p.stat();q=dst/p.relative_to(src);os.chown(q,s.st_uid,s.st_gid)
"""
            run(['docker','run','--rm','--network','none','--entrypoint','python',
                 '--mount','type=volume,source='+data+',target=/source,readonly',
                 '--mount','type=volume,source='+backup+',target=/backup',
                 'python:3.11-slim','-c',copy_code])
            start(new_image,data)
            assert read_marker('before')==1
            assert marker('after') in (200,204)
            deadline=time.monotonic()+30
            while read_marker('after')!=1 and time.monotonic()<deadline:time.sleep(1)
            assert read_marker('before')==read_marker('after')==1
            run(['docker','stop','--time','40',name]);run(['docker','rm',name])
            start(old_image,backup)
            assert read_marker('before')==1 and read_marker('after')==0
            result.update(status='PASS',old_marker_survives_upgrade=True,new_write_after_upgrade=True,
                          cold_copy_rollback_preserves_old_state=True,
                          reverse_binary_on_upgraded_storage_tested=False)
    except Exception as error:
        result.update(status='FAIL',error_type=type(error).__name__,error=str(error))
    finally:
        cleanup=[]
        cleanup.append(run(['docker','rm','--force',name],check=False).returncode)
        for volume in [data,backup]:cleanup.append(run(['docker','volume','rm',volume],check=False).returncode)
        cleanup.append(run(['docker','network','rm',network],check=False).returncode)
        result['cleanup_exit_codes']=cleanup
        # Container may not have been created when setup failed; volumes/network
        # failures are never hidden by an overall PASS.
        if result['status']=='PASS' and any(cleanup):result['status']='FAIL'
        (output/(project+'.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['project','component','status']}))
    return result['status']=='PASS'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--component',choices=['grafana','loki'],required=True)
    p.add_argument('--old-image',required=True);p.add_argument('--new-image',required=True)
    p.add_argument('--output',type=Path,default=ROOT/'tests/p7/artifacts/image-upgrades')
    args=p.parse_args()
    raise SystemExit(0 if execute(args.component,args.old_image,args.new_image,args.output) else 1)
