"""Optional disposable Python probe worker: each check remains a fresh process.

Avoid copying the same 600-MB vfs filesystem for every TLS probe. Only Python -c
checks and the existing persistence helper use the worker; pytest always gets its
normal fresh container. No authentication, TLS, DNS or assertions are replaced.
"""
class ProbeWorker:
    def __init__(self,compose):
        self.compose=compose
        self.container=None

    def start(self,run,project):
        self.container=run(self.compose+['run','-d','--no-deps','--name',project+'-probe-worker',
            'tests','python','-c','import time; time.sleep(36000)'],capture_output=True,text=True).stdout.strip()
        if not self.container:raise RuntimeError('Disposable probe worker did not start')

    def command(self,args):
        if self.container and args[:len(self.compose)]==self.compose:
            tail=args[len(self.compose):]
            prefix=['run','--rm','--no-deps','-T','tests','python']
            if tail[:6]==prefix and len(tail)>6 and tail[6] in ('-c','/tests/p3/persistence.py'):
                return ['docker','exec','-i',self.container,*tail[5:]]
        return args

    def close(self,run):
        if self.container:
            run(['docker','rm','--force',self.container],check=False,capture_output=True)
            self.container=None
