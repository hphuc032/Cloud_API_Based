// P3 preparation only: not imported by the app or used for authentication.
// P4 must supply cryptographically verified ID-token claims, never decoded claims.
export function validateAuthorizationResponse(callback, expectedState, expectedRedirectUri) {
  const url = new URL(callback)
  const expected = new URL(expectedRedirectUri)
  if (url.origin !== expected.origin || url.pathname !== expected.pathname) {
    throw new Error('Unexpected callback URI')
  }
  const states = url.searchParams.getAll('state')
  if (!expectedState || states.length !== 1 || states[0] !== expectedState) {
    throw new Error('OIDC state mismatch')
  }
  if (url.hash || url.searchParams.has('error')) throw new Error('OIDC response rejected')
  const codes = url.searchParams.getAll('code')
  if (codes.length !== 1 || !codes[0]) throw new Error('Missing authorization code')
  return codes[0]
}

export function validateVerifiedIDTokenClaims(claims, { nonce, issuer, clientId, now }) {
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud]
  if (!nonce || claims.nonce !== nonce || claims.iss !== issuer ||
      !audiences.includes(clientId) || (audiences.length > 1 && claims.azp !== clientId) ||
      !Number.isFinite(claims.exp) || claims.exp <= now || !claims.sub) {
    throw new Error('OIDC ID-token claims rejected')
  }
  return claims.sub
}
