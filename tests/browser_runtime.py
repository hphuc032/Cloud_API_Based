"""Opt-in WSL browser isolation; raw TCP relay preserves the IdP TLS identity.

Desktop's engine host network is not WSL's loopback. Bubblewrap uses the WSL
network namespace with an isolated filesystem/passwd/NSS store. No app secrets,
Docker API, personal browser profile or TLS-verification bypass is exposed.
"""
import json
import os
from pathlib import Path
import re
import subprocess


class DesktopBrowser:
    def __init__(self, run, project, root, port):
        if not re.fullmatch(r'cloud-api-p[4-7]-[a-f0-9]{12}', project):
            raise ValueError('Disposable browser project required')
        self.run, self.project, self.root, self.port = run, project, Path(root), port
        self.relay = project + '-browser-idp-relay'
        self.process = None
        self.log = None

    def start(self):
        # Clear the child environment rather than changing the host HOME.
        # Chromium 145 falls back to /tmp when HOME is absent; bind its NSS
        # location inside this private mount namespace to the generated store.
        passwd = self.root / 'passwd'
        passwd.write_text('browser:x:'+str(os.getuid())+':'+str(os.getgid())+':Browser:/p4:/usr/sbin/nologin\n')
        (self.root / '.pki').symlink_to('xdg/pki', target_is_directory=True)
        relay = '''import socket,socketserver,select
class Relay(socketserver.BaseRequestHandler):
 def handle(self):
  with socket.create_connection(('identity-edge',8443),5) as upstream:
   peers=(self.request,upstream)
   while True:
    ready,_,_=select.select(peers,[],[],60)
    if not ready:return
    for source in ready:
     data=source.recv(65536)
     if not data:return
     (upstream if source is self.request else self.request).sendall(data)
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address=True
 daemon_threads=True
Server(('0.0.0.0',9443),Relay).serve_forever()
'''
        self.run(['docker','run','-d','--name',self.relay,
                  '--label','org.florasecure.test-project='+self.project,
                  '--network',self.project+'_oidc_transport','--read-only',
                  '--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges',
                  '--pids-limit','32','--memory','64m','-p','127.0.0.1::9443',
                  '--entrypoint','python','python:3.11-slim','-c',relay],capture_output=True,text=True)
        info=json.loads(self.run(['docker','inspect',self.relay],capture_output=True,text=True).stdout)[0]
        assert info['Config']['Labels']['org.florasecure.test-project']==self.project
        binding=info['NetworkSettings']['Ports']['9443/tcp'][0]
        assert binding['HostIp']=='127.0.0.1'
        assert not info['Mounts'] and not info['HostConfig']['Privileged']
        args=['bwrap','--die-with-parent','--new-session','--unshare-user','--unshare-pid',
              '--unshare-ipc','--unshare-uts','--clearenv','--ro-bind','/usr','/usr',
              '--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64',
              '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/etc',
              '--ro-bind','/etc/fonts','/etc/fonts','--ro-bind','/etc/resolv.conf','/etc/resolv.conf',
              '--ro-bind',str(passwd),'/etc/passwd','--bind',str(self.root),'/p4','--chdir','/p4',
              '--symlink','/p4/xdg/pki','/tmp/.pki',
              '--setenv','PATH','/usr/bin:/bin','--setenv','LANG','C.UTF-8',
              '--setenv','XDG_DATA_HOME','/p4/xdg','--setenv','XDG_CONFIG_HOME','/p4/config',
              '--setenv','XDG_CACHE_HOME','/p4/cache',
              '/usr/lib/chromium/chromium','--headless','--no-sandbox','--disable-dev-shm-usage',
              '--no-proxy-server','--disable-breakpad','--remote-debugging-address=127.0.0.1',
              '--remote-debugging-port='+str(self.port),'--user-data-dir=/p4/profile',
              '--host-resolver-rules=MAP identity-edge 127.0.0.1:'+binding['HostPort'],'about:blank']
        self.log=(self.root/'startup.log').open('w')
        self.process=subprocess.Popen(args,stdout=self.log,stderr=subprocess.STDOUT)

    def close(self):
        if self.process:
            self.process.terminate()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        if self.log:self.log.close()
        info=self.run(['docker','inspect',self.relay],check=False,capture_output=True,text=True)
        if info.returncode==0:
            assert json.loads(info.stdout)[0]['Config']['Labels'].get('org.florasecure.test-project')==self.project
            self.run(['docker','rm','--force',self.relay],capture_output=True)
