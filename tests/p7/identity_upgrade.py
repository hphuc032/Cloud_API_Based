"""Cold Keycloak minor upgrade on a copied lab DB; rollback restores old DB too."""
import json
import re
import subprocess


def execute(run,compose,project,artifacts,target):
    if not re.fullmatch(r'cloud-api-p7-[a-f0-9]{12}',project):
        raise ValueError('Disposable P7 project required')
    if not re.fullmatch(r'quay.io/keycloak/keycloak:[0-9.]+@sha256:[a-f0-9]{64}',target):
        raise ValueError('Exact official Keycloak image digest required')
    source=json.loads(run(compose+['config','--format','json'],capture_output=True,text=True).stdout)
    app=source['services']['backend']['environment']
    assert app['APP_ENV']=='test' and app['APP_DB_NAME']=='p0_baseline'
    original_image=source['services']['keycloak']['image']
    assert re.fullmatch(r'quay.io/keycloak/keycloak:[0-9.]+@sha256:[a-f0-9]{64}',original_image)
    assert original_image!=target
    overlay=artifacts/'identity-upgrade-compose.json'
    clone=project+'_identity_upgrade_clone'
    evidence={'status':'RUNNING','old_image':original_image,'target_image':target,
        'cold_copy_only':True,'production_data_used':False,'stages':[]}
    created=False;restored=False

    def probe(phase):
        run(compose+['run','--rm','--no-deps','-T','tests','python','/tests/p7/identity_upgrade_probe.py',phase],capture_output=True,text=True)

    def verify():
        run(compose+['run','--rm','--no-deps','-T','tests','python','/tests/p7/verify_recovered.py'],capture_output=True,text=True)

    def migrations():
        p=run(compose+['exec','-T','identity-db','psql','-X','-U','postgres','-d','keycloak','-Atqc',
                       'SELECT count(*) FROM databasechangelog'],capture_output=True,text=True)
        return int(p.stdout.strip())

    def start():
        run(compose+['up','--no-deps','-d','--force-recreate','--wait','--wait-timeout','120','identity-db'])
        run(compose+['up','--no-deps','-d','--force-recreate','--wait','--wait-timeout','300','keycloak'])
        run(compose+['up','--no-deps','-d','--force-recreate','--wait','--wait-timeout','90','identity-edge'])

    try:
        verify();probe('prepare')
        before=migrations()
        cid=run(compose+['ps','-q','identity-db'],capture_output=True,text=True).stdout.strip()
        info=json.loads(run(['docker','inspect',cid],capture_output=True,text=True).stdout)[0]
        volume=next(m['Name'] for m in info['Mounts'] if m['Destination']=='/var/lib/postgresql/data')
        v=json.loads(run(['docker','volume','inspect',volume],capture_output=True,text=True).stdout)[0]
        assert volume.startswith(project+'_') and v['Labels']['com.docker.compose.project']==project
        run(compose+['stop','--timeout','40','keycloak','identity-db'])
        run(['docker','volume','create','--label','florasecure.identity-upgrade='+project,clone])
        created=True
        copy_code="""import os,pathlib,shutil
src=pathlib.Path('/source');dst=pathlib.Path('/copy')
shutil.copytree(src,dst,dirs_exist_ok=True,symlinks=True)
for p in [src,*src.rglob('*')]:
 s=p.lstat();q=dst/p.relative_to(src);os.chown(q,s.st_uid,s.st_gid,follow_symlinks=False)
"""
        run(['docker','run','--rm','--network','none','--entrypoint','python',
            '--mount','type=volume,source='+volume+',target=/source,readonly',
            '--mount','type=volume,source='+clone+',target=/copy',
            'python:3.11-slim','-c',copy_code],capture_output=True,text=True)
        overlay.write_text(json.dumps({'services':{
            'identity-db':{'volumes':[{'type':'volume','source':'identity_upgrade_clone','target':'/var/lib/postgresql/data'}]},
            'keycloak':{'image':target,'environment':{
                'KC_SPI_CONNECTIONS_JPA__QUARKUS__ASYNC_COMMIT':'false','KC_FEATURES_DISABLED':'scim-api'}}},
            'volumes':{'identity_upgrade_clone':{'external':True,'name':clone}}},indent=2))
        compose+=['-f',str(overlay)]
        start();probe('compare');verify()
        after=migrations();assert after>before,'Expected a real minor-version schema migration'
        evidence['stages'].append({'phase':'new-version','migrations_before':before,'migrations_after':after,
            'identity_application_policy_and_keys_preserved':True,'real_pkce_rbac_ownership':True})
        run(compose+['stop','--timeout','40','keycloak','identity-db'])
        start();probe('compare');verify()
        evidence['stages'].append({'phase':'new-version-restarted','passed':True})
        evidence['status']='PASS'
    except Exception as error:
        evidence.update(status='FAIL',error_type=type(error).__name__)
    finally:
        # The original PostgreSQL volume was never mounted by the new binary.
        # Remove the clone override before recreating the old pair.
        try:
            run(compose+['stop','--timeout','40','keycloak','identity-db'])
            overlay.write_text(json.dumps({'services':{'keycloak':{'image':original_image}}}))
            if str(overlay) not in compose:compose+=['-f',str(overlay)]
            start();probe('compare');verify()
            assert migrations()==before
            restored=True
            evidence['stages'].append({'phase':'old-image-and-original-db-rollback','passed':True})
        except Exception as error:
            evidence.update(status='FAIL',rollback_error_type=type(error).__name__)
        if created and restored:
            v=json.loads(run(['docker','volume','inspect',clone],capture_output=True,text=True).stdout)[0]
            assert v['Labels']['florasecure.identity-upgrade']==project
            p=run(['docker','volume','rm',clone],check=False,capture_output=True,text=True)
            evidence['clone_cleanup_exit']=p.returncode
            if p.returncode:evidence['status']='FAIL'
        evidence['original_database_restored']=restored
        (artifacts/'identity-upgrade-results.json').write_text(json.dumps(evidence,indent=2))
    return evidence['status']=='PASS'
