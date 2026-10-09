export const LEGACY_KEYS = ['fs_access_token','fs_refresh_token','fs_expires_at','fs_role','fs_user'];
export function cleanupLegacy(storage) { for (const key of LEGACY_KEYS) storage.removeItem(key); }

// Keycloak's supported adapter owns PKCE, one-time callback state and nonce checks.
// This wrapper owns application lifecycle and single-flight refresh, never token persistence.
export function createSession(keycloak, { origin, storage, href = () => origin, notify = () => {}, checkReady = async () => {} }) {
  let initial, refreshing, closing = false;
  const expiry = () => keycloak.tokenParsed?.exp ?
    (keycloak.tokenParsed.exp + (keycloak.timeSkew || 0))*1000 : null;
  const fail = () => { keycloak.clearToken(); notify('expired'); };
  keycloak.onAuthLogout = () => notify('logout');
  keycloak.onTokenExpired = () => refresh(-1).catch(() => {});
  function init() {
    if (!initial) {
      cleanupLegacy(storage);
      const location=new URL(href());
      const callback=location.pathname==='/oidc/callback' && (location.searchParams.has('code')||location.searchParams.has('error'));
      // A rejected callback must not be hidden by automatically starting a fresh
      // SSO transaction. The adapter still verifies/consumes state and nonce.
      initial = Promise.resolve().then(checkReady).then(() => keycloak.init({ onLoad:callback?undefined:'check-sso', pkceMethod:'S256', flow:'standard', useNonce:true,
        responseMode:'query', checkLoginIframe:false, enableLogging:false, logoutMethod:'POST',
        redirectUri: origin+'/oidc/callback' })).then(authenticated => {
          if(callback && location.searchParams.has('code') && !authenticated)notify('rejected');
          return authenticated;
        });
    }
    return initial;
  }
  async function refresh(validity = 30) {
    if (closing || !keycloak.authenticated) return null;
    if (!refreshing) {
      refreshing = Promise.resolve().then(() => keycloak.updateToken(validity))
        .catch(error => { fail(); throw error; }).finally(() => { refreshing = null; });
    }
    await refreshing;
    if (!keycloak.token || !Number.isFinite(keycloak.tokenParsed?.exp) || expiry()<=Date.now()) {
      fail(); throw new Error('Identity session expired');
    }
    return keycloak.token;
  }
  return {
    init,
    async token() { await init(); return refresh(); },
    currentToken: () => closing ? '' : keycloak.token || '',
    expiresAt: expiry,
    async login() { await init(); await checkReady(); closing=false; return keycloak.login({redirectUri:origin+'/oidc/callback'}); },
    logout() {
      closing=true; notify('logout');
      // The adapter captures its ID-token hint before in-memory cleanup.
      const result=keycloak.logout({redirectUri:origin+'/login'});keycloak.clearToken();return result;
    },
    expire: fail,
  };
}
