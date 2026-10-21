import { randomBytes } from 'node:crypto';

export function browserHeaders(identityUrl, {development=false,nonce=''}={}) {
  const parsed=new URL(identityUrl);
  if(parsed.protocol!=='https:' || parsed.username || parsed.password || parsed.search || parsed.hash)
    throw new Error('An exact HTTPS identity origin is required');
  const origin=parsed.origin;
  const scripts="'self'"+(development?` 'nonce-${nonce}'`:'');
  return {
    'Strict-Transport-Security':'max-age=31536000',
    'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
    'Referrer-Policy':'strict-origin-when-cross-origin',
    'Permissions-Policy':'camera=(), microphone=(), geolocation=(), payment=()',
    'Content-Security-Policy':`default-src 'self'; script-src ${scripts}; style-src ${scripts}; style-src-attr 'none'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' ${origin}${development?' wss://localhost:5173 wss://localhost:5174':''}; frame-src ${origin}; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self' ${origin}`,
  };
}
export const developmentNonce=()=>randomBytes(18).toString('base64');
