"""Verified Chromium HTTPS, isolated NSS trust and real Keycloak adapter callbacks."""
import json,os,ssl,socket,subprocess,time,urllib.request
from pathlib import Path


def execute(run,compose,project,metadata,pki,identity_pki,fixtures,temp,artifacts,env):
    root=Path(__file__).resolve().parents[2]
    server=None;browser_container=None;frontend_container=None
    try:
        if 'application_id' not in json.loads((fixtures/'identities.json').read_text()):
            run(compose+['run','--rm','--no-deps','-T','tests','python','/tests/p4/browser_setup.py','prepare'])
        run(compose+['run','--rm','--no-deps','-T','tests','python','/tests/p5/browser_setup.py'])
        browser_root=temp/'p5-browser-runtime';browser_root.mkdir()
        nss=browser_root/'xdg/pki/nssdb';nss.mkdir(parents=True)
        run(['certutil','-N','-d','sql:'+str(nss),'--empty-password'],capture_output=True)
        for name,ca in [('p4-edge',pki/'trust/edge-ca.pem'),('p4-identity',identity_pki/'trust/identity-ca.pem')]:
            run(['certutil','-A','-d','sql:'+str(nss),'-n',name,'-t','C,,','-i',str(ca)],capture_output=True)
        cs={c['Config']['Labels']['com.docker.compose.service']:c for c in metadata}
        edge=cs['identity-edge']['NetworkSettings']['Networks'][project+'_oidc_transport']['IPAddress']
        info=json.loads(run(['docker','inspect',cs['kong']['Id']],capture_output=True,text=True).stdout)[0]
        port=info['NetworkSettings']['Ports']['8443/tcp'][0]['HostPort']
        settings=dict(env,VITE_OIDC_URL='https://identity-edge:8443',API_PROXY_TARGET='https://localhost:'+port,
            VITE_TLS_CERT=str(pki/'kong/edge.pem'),VITE_TLS_KEY=str(pki/'kong/edge.key'),
            NODE_EXTRA_CA_CERTS=str(pki/'trust/edge-ca.pem'),
            P4_BROWSER_CONFIG=str(temp/'browser.json'))
        settings.pop('SSLKEYLOGFILE',None)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));cdp_port=listener.getsockname()[1]
        # A separate disposable OS context avoids touching the host's existing
        # NSS store. HOME is never reassigned. System Chromium/libraries are read
        # only; the browser receives no database secrets or application private keys.
        browser_container=project+'-browser'
        args=['docker','run','-d','--name',browser_container,'--network','host','--read-only',
            '--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,nosuid,nodev',
            '-v',str(browser_root)+':/p4','-v','/usr:/usr:ro','-v','/lib:/lib:ro','-v','/lib64:/lib64:ro',
            '-v','/etc/fonts:/etc/fonts:ro','-e','XDG_DATA_HOME=/p4/xdg',
            '-e','XDG_CACHE_HOME=/p4/cache','-e','XDG_CONFIG_HOME=/p4/config',
            '--entrypoint','/usr/lib/chromium/chromium','python:3.11-slim','--headless','--no-sandbox',
            '--disable-dev-shm-usage','--no-proxy-server','--disable-breakpad',
            '--remote-debugging-address=127.0.0.1','--remote-debugging-port='+str(cdp_port),
            '--user-data-dir=/p4/profile','--host-resolver-rules=MAP identity-edge '+edge,'about:blank']
        run(args,capture_output=True,text=True)
        for _ in range(60):
            try:
                with urllib.request.urlopen('http://127.0.0.1:'+str(cdp_port)+'/json/version',timeout=1) as r:
                    assert json.load(r)['Browser'].startswith('Chrome/');break
            except (OSError,urllib.error.URLError):time.sleep(.5)
        else:raise RuntimeError('Disposable Chromium CDP endpoint did not start')
        config={'fixtures':str(fixtures/'identities.json'),'edge_ip':edge,'cdp':'http://127.0.0.1:'+str(cdp_port),
                'compose':compose,'results':str(artifacts/'p5-browser-results.json')}
        (temp/'browser.json').write_text(json.dumps(config))
        # Production self-hosted assets and exact-IdP CSP, not the Vite server.
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        import importlib.util
        spec=importlib.util.spec_from_file_location('p5_pki',root/'docker/pki.py');pk=importlib.util.module_from_spec(spec);spec.loader.exec_module(pk)
        ca=(serialization.load_pem_private_key((pki/'offline/edge.key').read_bytes(),password=None),x509.load_pem_x509_certificate((pki/'offline/edge.pem').read_bytes()))
        spa=temp/'spa-tls';spa.mkdir()
        pk.save_leaf(spa,ca,'spa',['localhost','127.0.0.1'])
        (spa/'edge-ca.pem').write_bytes((pki/'trust/edge-ca.pem').read_bytes())
        for f in spa.iterdir():f.chmod(0o444)
        nginx=temp/'spa.conf'
        run(['python3',str(root/'docker/render_spa.py'),'--issuer-origin','https://identity-edge:8443','--output',str(nginx)])
        build=run(['npm','run','build'],cwd=root/'frontend',env=dict(env,VITE_OIDC_URL='https://identity-edge:8443',VITE_SECURITY_LAB='true'),capture_output=True,text=True)
        (artifacts/'frontend-build.txt').write_text(build.stdout+build.stderr)
        dist=root/'frontend/dist';dist.chmod(0o755)
        for asset in dist.rglob('*'):asset.chmod(0o755 if asset.is_dir() else 0o644)
        frontend_container=project+'-spa'
        run(['docker','run','-d','--name',frontend_container,'--network',project+'_edge','--read-only',
            '--tmpfs','/var/cache/nginx','--tmpfs','/var/run','--tmpfs','/tmp',
            '-p','127.0.0.1:5174:8443','-v',str(root/'frontend/dist')+':/usr/share/nginx/html:ro',
            '-v',str(nginx)+':/etc/nginx/conf.d/default.conf:ro','-v',str(spa)+':/run/tls:ro',
            'nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10'],capture_output=True,text=True)
        context=ssl.create_default_context(cafile=str(pki/'trust/edge-ca.pem'))
        for _ in range(40):
            try:
                with urllib.request.urlopen('https://localhost:5174/login',context=context,timeout=1) as r:
                    if r.status==200:break
            except (OSError,urllib.error.URLError):time.sleep(0.5)
        else:raise RuntimeError('Verified HTTPS frontend did not start')
        proc=run(['node',str(root/'tests/p5/browser.mjs')],env=settings,capture_output=True,text=True,check=False)
        print(proc.stdout,flush=True)
        access=run(['docker','logs',frontend_container],capture_output=True,text=True).stdout
        query_absent='must-not-log-query' not in access
        (artifacts/'p5-spa-log-evidence.json').write_text(json.dumps({'query_probe_sent':True,'query_value_absent':query_absent},indent=2))
        if not query_absent:raise AssertionError('SPA access log exposed a query value')
        # Do not emit exceptions containing credential forms, URLs with codes, or tokens.
        if proc.returncode:(artifacts/'browser-error.txt').write_text(proc.stderr)
        return proc.returncode==0
    except Exception as exc:
        (artifacts/'browser-error.txt').write_text(type(exc).__name__+': '+str(exc))
        print('Browser validation failed: '+type(exc).__name__,flush=True)
        return False
    finally:
        if server:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
        if frontend_container:run(['docker','rm','--force',frontend_container],check=False,capture_output=True)
        if browser_container:run(['docker','rm','--force',browser_container],check=False,capture_output=True)
