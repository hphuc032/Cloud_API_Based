import Keycloak from 'keycloak-js';
import { createSession } from './session.js';
const url = import.meta.env.VITE_OIDC_URL || 'https://localhost:9443';
const parsed = new URL(url);
if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.search || parsed.hash) {
  throw new Error('An explicit HTTPS identity provider origin is required');
}
const keycloak = new Keycloak({ url, realm:'florasecure', clientId:'florasecure-spa' });
const issuer=url.replace(/\/$/,'')+'/realms/florasecure';
async function checkReady() {
  // Detect an unavailable/misconfigured IdP before top-level SSO navigation
  // would replace the SPA with a browser connection-error page.
  const response=await fetch(issuer+'/.well-known/openid-configuration',{
    credentials:'omit',redirect:'error',cache:'no-store',signal:AbortSignal.timeout(5000)});
  if(!response.ok)throw new Error('Identity provider unavailable');
  const metadata=await response.json();
  if(metadata.issuer!==issuer || metadata.authorization_endpoint!==issuer+'/protocol/openid-connect/auth' ||
     metadata.jwks_uri!==issuer+'/protocol/openid-connect/certs')throw new Error('Untrusted identity configuration');
}
const listeners = new Set();
export const identity = createSession(keycloak, { origin:window.location.origin, storage:localStorage,
  checkReady,
  href: () => window.location.href,
  notify: event => listeners.forEach(listener => listener(event)) });
export function subscribeIdentity(listener) { listeners.add(listener);return () => listeners.delete(listener); }
