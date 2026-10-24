"""Render a dedicated verified HTTPS SPA boundary, without secrets in config."""
import argparse, json, subprocess
from pathlib import Path
from urllib.parse import urlsplit

def render(identity_origin):
    parsed=urlsplit(identity_origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise ValueError('An exact HTTPS identity origin is required')
    root=Path(__file__).resolve().parents[1]
    code="import {browserHeaders} from './security-policy.js'; console.log(JSON.stringify(browserHeaders(process.argv[1])));"
    headers=json.loads(subprocess.run(['node','--input-type=module','-e',code,identity_origin],cwd=root/'frontend',check=True,capture_output=True,text=True).stdout)
    directives='\n'.join('    add_header '+name+' '+json.dumps(value)+' always;' for name,value in headers.items())
    return '''# Do not put OAuth callback codes/state or other query values in access logs.
log_format p5_spa '$request_method $uri $status';
server {
    access_log /dev/stdout p5_spa;
    error_log /dev/null;
    listen 8443 ssl;
    server_name localhost;
    ssl_certificate /run/tls/spa.pem;
    ssl_certificate_key /run/tls/spa.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    root /usr/share/nginx/html;
    index index.html;
'''+directives+'''
    location / { try_files $uri $uri/ /index.html; }
    location ~ ^/(api/|health) {
        # Preserve the pre-1.29.7 proxy defaults across the image update.
        proxy_http_version 1.0;
        proxy_set_header Connection close;
        proxy_pass https://kong:8443;
        proxy_ssl_verify on;
        proxy_ssl_trusted_certificate /run/tls/edge-ca.pem;
        proxy_ssl_server_name on;
        proxy_ssl_name kong;
        proxy_set_header Host kong;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_hide_header Content-Security-Policy;
        proxy_hide_header Strict-Transport-Security;
        proxy_hide_header X-Frame-Options;
        proxy_hide_header X-Content-Type-Options;
        proxy_hide_header Permissions-Policy;
        proxy_hide_header Referrer-Policy;
    }
}
'''

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--issuer-origin',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    Path(args.output).write_text(render(args.issuer_origin))
