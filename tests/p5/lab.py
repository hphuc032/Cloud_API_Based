"""Offline signing only for an explicitly acknowledged disposable lab.

Writes short-lived delivery material to a NEW private file; never prints the key.
This is not an HTTP signature helper and performs no network requests.
"""
import argparse,hashlib,hmac,json,os,time
from pathlib import Path
from uuid import uuid4


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--disposable-lab',action='store_true',required=True)
 p.add_argument('--secret-file',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True)
 args=p.parse_args()
 if os.environ.get('APP_ENV')!='test' or os.environ.get('P0_ISOLATED')!='1':
  p.error('Requires APP_ENV=test and P0_ISOLATED=1; never use production keys')
 key=args.secret_file.read_text().strip()
 if len(key)<32:p.error('Lab secret must have at least 32 characters')
 body=json.dumps({'event':'payment.success','event_id':'p5-lab-'+uuid4().hex,'order_id':'disposable-ack-only'},separators=(',',':'))
 timestamp=str(int(time.time()))
 signature='sha256='+hmac.new(key.encode(),timestamp.encode()+b'.'+body.encode(),hashlib.sha256).hexdigest()
 fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as stream:json.dump({'body':body,'timestamp':timestamp,'signature':signature},stream)
 print('Private short-lived lab delivery file created; paste fields into the disposable Security Center.')


if __name__=='__main__':main()
