"""Verified Chromium HTTPS, isolated NSS trust and real Keycloak adapter callbacks."""
import json,os,ssl,socket,subprocess,time,urllib.request
from pathlib import Path


def execute(run,compose,project,metadata,pki,identity_pki,fixtures,temp,artifacts,env):
    root=Path(__file__).resolve().parents[2]
    server=None;desktop_browser=None;browser_container=None
    try:
        run(compose+['run','--rm','--no-deps','-T','tests','python','/tests/p4/browser_setup.py','prepare'])
        browser_root=temp/'browser-runtime';browser_root.mkdir()
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
        if env.get('CLOUD_API_DESKTOP_BROWSER')=='1':
            import importlib.util
            spec=importlib.util.spec_from_file_location('desktop_browser',root/'tests/browser_runtime.py')
            runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
            desktop_browser=runtime.DesktopBrowser(run,project,browser_root,cdp_port)
            desktop_browser.start()
        else:
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
        else:
            if desktop_browser:
                (artifacts/'browser-startup.txt').write_text((browser_root/'startup.log').read_text())
            else:
                diagnostic=run(['docker','logs',browser_container],check=False,capture_output=True,text=True)
                (artifacts/'browser-startup.txt').write_text(diagnostic.stdout+diagnostic.stderr)
            raise RuntimeError('Disposable Chromium CDP endpoint did not start')
        config={'fixtures':str(fixtures/'identities.json'),'edge_ip':edge,'cdp':'http://127.0.0.1:'+str(cdp_port),
                'private_alias_resolution':'loopback TCP relay to Compose identity-edge; original TLS SNI/hostname' if desktop_browser else 'actual Compose identity-edge address only',
                'compose':compose,'results':str(artifacts/'browser-results.json')}
        (temp/'browser.json').write_text(json.dumps(config))
        vite_log=(artifacts/'vite.txt').open('w')
        # Invoke Vite directly so termination cannot leave npm's child server
        # holding the exact registered callback port after a failed run.
        server=subprocess.Popen(['node',str(root/'frontend/node_modules/vite/bin/vite.js'),
            '--host','127.0.0.1','--port','5174','--strictPort'],
            cwd=root/'frontend',env=settings,stdout=vite_log,stderr=subprocess.STDOUT)
        context=ssl.create_default_context(cafile=str(pki/'trust/edge-ca.pem'))
        for _ in range(40):
            try:
                with urllib.request.urlopen('https://localhost:5174/login',context=context,timeout=1) as r:
                    if r.status==200:break
            except (OSError,urllib.error.URLError):time.sleep(0.5)
        else:raise RuntimeError('Verified HTTPS frontend did not start')
        proc=run(['node',str(root/'tests/p4/browser.mjs')],env=settings,capture_output=True,text=True,check=False)
        print(proc.stdout,flush=True)
        # Do not emit exceptions containing credential forms, URLs with codes, or tokens.
        if proc.returncode:(artifacts/'browser-error.txt').write_text(proc.stderr)
        return proc.returncode==0
    except Exception as exc:
        (artifacts/'browser-error.txt').write_text(type(exc).__name__+': '+str(exc))
        print('Browser validation failed: '+type(exc).__name__,flush=True)
        return False
    finally:
        if desktop_browser:desktop_browser.close()
        if server:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
        if browser_container:run(['docker','rm','--force',browser_container],check=False,capture_output=True)
