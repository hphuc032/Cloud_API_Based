"""Operator-side narrow mounts; never put Docker API access in the collector."""
import argparse,json,subprocess
from pathlib import Path


def render(project,mount_root):
 if not project or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in project):
  raise ValueError('Explicit lowercase Compose project required')
 ids=subprocess.check_output(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project],text=True).split()
 if not ids:raise ValueError('No project containers')
 records=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True))
 mount_root.mkdir(parents=True,exist_ok=True)
 mount_root.chmod(0o755)
 mounts=[];seen=set()
 for record in records:
  labels=record['Config'].get('Labels',{})
  if labels.get('com.docker.compose.project')!=project:raise ValueError('Project mismatch')
  service=labels.get('com.docker.compose.service')
  if service not in {'backend','kong','keycloak'}:continue
  if service in seen:raise ValueError('Review multiple replicas before generating mounts')
  seen.add(service);cid=record['Id'];log=Path(record['LogPath'])
  if not log.is_absolute() or log.name!=cid+'-json.log' or log.parent.name!=cid:
   raise ValueError('Expected reviewed json-file log path')
  # Compose merges volumes by target. A stable service target replaces a removed
  # container's source rather than retaining its now-invalid CID bind mount.
  (mount_root/service).mkdir(parents=True,exist_ok=True)
  mounts.append(dict(type='bind',source=str(log.parent),target='/var/log/project/'+service,read_only=True))
 if seen!={'backend','kong','keycloak'}:raise ValueError('Required services missing')
 return {'services':{'alloy':{'volumes':mounts}}}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',required=True);p.add_argument('--mount-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 args.output.write_text(json.dumps(render(args.project,args.mount_root),indent=2)+'\n')
