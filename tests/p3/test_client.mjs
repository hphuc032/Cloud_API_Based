import assert from 'node:assert/strict'
import { validateAuthorizationResponse, validateVerifiedIDTokenClaims } from '../../frontend/src/identity/oidcPreparation.js'
const redirect = 'https://localhost:5173/oidc/callback'
const callback = 'https://localhost:5173/oidc/callback?code=one&state=expected'
assert.equal(validateAuthorizationResponse(callback, 'expected', redirect), 'one')
for (const response of [callback.replace('expected', 'attacker'), callback.replace('&state=expected', ''), callback+'&state=expected', callback+'&code=two', callback+'&error=access_denied', callback+'#access_token=x', callback.replace('localhost', 'evil.example'), callback.replace('/oidc/callback','/wrong')]) {
  assert.throws(() => validateAuthorizationResponse(response, 'expected', redirect))
}
assert.throws(() => validateAuthorizationResponse(callback, null, redirect))
const expected = {nonce:'fresh',issuer:'https://id.example/realms/florasecure',clientId:'florasecure-spa',now:100}
const claims = {nonce:'fresh',iss:expected.issuer,aud:expected.clientId,sub:'identity-id',exp:101}
assert.equal(validateVerifiedIDTokenClaims(claims, expected), 'identity-id')
for (const change of [{nonce:'replayed'}, {nonce:undefined}, {iss:'https://evil.example'}, {aud:'other'}, {exp:100}, {exp:undefined}, {sub:''}, {aud:[expected.clientId,'other'],azp:'other'}]) {
  assert.throws(() => validateVerifiedIDTokenClaims({...claims,...change}, expected))
}
console.log('PASS: 19 client assertions for valid responses and state/nonce/issuer/audience/expiry rejection')
