"""Opt-in Docker Desktop/WSL adapter for real project-only, read-only log mounts.

Windows Docker CLI addresses engine paths; the WSL CLI translates those same
paths into Ubuntu bind sources. Inherit engine-created mounts through a no-network
holder, without exposing the Docker API or unrelated log directories to collectors.
Native Linux uses ordinary bind mounts. No log records are read/copied here.
"""
import json
import os
from pathlib import Path
import re
import subprocess


class ProjectLogs:
    def __init__(self, project):
        if not re.fullmatch(r'cloud-api-(?:p[1-7]|remediation)-[a-f0-9]{10,12}', project):
            raise ValueError('Disposable project name required')
        self.project = project
        self.name = project + '-log-source'
        self.desktop = os.environ.get('CLOUD_API_DESKTOP_LOGS') == '1'
        self.created = False

    def overlay(self, run, collector, mount_root):
        if collector not in ('alloy', 'promtail'):
            raise ValueError('Unreviewed collector')
        root = '/var/log/project' if collector == 'alloy' else '/var/log/docker'
        ids = run(['docker','ps','-aq','--filter','label=com.docker.compose.project='+self.project],
                  capture_output=True,text=True).stdout.split()
        records = json.loads(run(['docker','inspect',*ids],capture_output=True,text=True).stdout)
        mounts = []; seen = set()
        for c in records:
            labels = c['Config'].get('Labels', {})
            if labels.get('com.docker.compose.project') != self.project:
                raise ValueError('Project mismatch')
            service = labels.get('com.docker.compose.service')
            if service not in {'backend','kong','keycloak'}: continue
            cid = c['Id']; path = Path(c['LogPath'])
            if service in seen or path.name != cid+'-json.log' or path.parent.name != cid or not path.is_absolute():
                raise ValueError('Unexpected log source or replicas')
            seen.add(service)
            mounts.append(dict(type='bind',source=str(path.parent),target=root+'/'+service,read_only=True))
        if seen != {'backend','kong','keycloak'}:
            raise ValueError('Required real log sources absent')
        mount_root.mkdir(parents=True,exist_ok=True); mount_root.chmod(0o755)
        # Child mountpoints must exist before the parent is mounted read-only.
        for service in seen:
            (mount_root/service).mkdir(mode=0o755,exist_ok=True)
            (mount_root/service).chmod(0o755)
        if not self.desktop:
            return {'services':{collector:{'volumes':mounts}}}
        cli = os.environ.get('CLOUD_API_DESKTOP_DOCKER', '/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe')
        if not Path(cli).is_file(): raise RuntimeError('Windows Docker CLI unavailable')
        if self.created:
            self.close(run)
        # A separate ownership label keeps this adapter outside Compose's service
        # inventory. It has no network, capabilities, writable root or secrets.
        args = [cli,'create','--name',self.name,'--label','org.florasecure.test-project='+self.project,
                '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true']
        for m in mounts:
            args += ['--mount','type=bind,source='+m['source']+',target='+m['target']+',readonly']
        # Use a cached image without Dockerfile VOLUME declarations: inheriting
        # an image-declared anonymous volume would grant unrelated writable data.
        args += ['--entrypoint','/bin/true','python:3.11-slim']
        run(args,capture_output=True,text=True)
        self.created = True
        holder=json.loads(run(['docker','inspect',self.name],capture_output=True,text=True).stdout)[0]
        expected={(m['source'],m['target']) for m in mounts}
        actual={(m['Source'],m['Destination']) for m in holder['Mounts']}
        if (actual != expected or any(m['RW'] for m in holder['Mounts']) or
                holder['HostConfig']['Privileged'] or holder['HostConfig']['NetworkMode'] != 'none'):
            raise RuntimeError('Log holder grants unexpected mounts or privileges; collector refused')
        # The caller replaces its single overlay after recreation; Compose must
        # never append duplicate volumes_from entries from another overlay.
        return {'services':{collector:{'volumes_from':['container:'+self.name+':ro']}}}

    def close(self, run):
        if self.created:
            raw=run(['docker','inspect',self.name],capture_output=True,text=True)
            c=json.loads(raw.stdout)[0]
            if c['Config'].get('Labels',{}).get('org.florasecure.test-project') != self.project:
                raise RuntimeError('Refusing cleanup of unrelated holder')
            run(['docker','rm','--volumes',self.name],capture_output=True,text=True)
            self.created=False
