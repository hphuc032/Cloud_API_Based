import assert from 'node:assert/strict';
import {createSession,LEGACY_KEYS} from '../../frontend/src/identity/session.js';
const data=new Map(LEGACY_KEYS.map(k=>[k,'legacy']));data.set('unrelated','keep');
let calls=0,initCalls=0,release;
const sdk={authenticated:true,token:'memory-only',tokenParsed:{exp:Math.floor(Date.now()/1000)+100},
 init:async options=>{initCalls++;assert.equal(options.pkceMethod,'S256');assert.equal(options.flow,'standard');assert.equal(options.useNonce,true);assert.equal(options.logoutMethod,'POST');return true;},
 updateToken:()=>{calls++;return new Promise(resolve=>{release=resolve;});},
 clearToken(){this.token='';this.authenticated=false;},
 login:async options=>{assert.equal(options.redirectUri,'https://localhost:5174/oidc/callback');},
 logout:options=>{assert.equal(options.redirectUri,'https://localhost:5174/login');assert.equal(sdk.token,'memory-only');return Promise.resolve();}};
const events=[];const session=createSession(sdk,{origin:'https://localhost:5174',storage:{removeItem:k=>data.delete(k)},notify:e=>events.push(e)});
await Promise.all([session.init(),session.init()]);assert.equal(initCalls,1);
for(const k of LEGACY_KEYS)assert.equal(data.has(k),false);assert.equal(data.get('unrelated'),'keep');
const requests=[session.token(),session.token(),session.token()];await new Promise(r=>setTimeout(r,0));assert.equal(calls,1);release(true);
assert.deepEqual(await Promise.all(requests),['memory-only','memory-only','memory-only']);
assert.equal(data.size,1);assert.equal(session.currentToken(),'memory-only');await session.logout();assert.equal(session.currentToken(),'');assert.ok(events.includes('logout'));
const failSdk={...sdk,authenticated:true,token:'short',tokenParsed:{exp:1},init:async()=>true,updateToken:async()=>{throw new Error('IdP unavailable');}};
const failed=createSession(failSdk,{origin:'https://localhost:5174',storage:{removeItem(){}}});await assert.rejects(()=>failed.token());assert.equal(failed.currentToken(),'');
const unavailable=createSession({...failSdk,init:async()=>{throw new Error('unavailable');}},{origin:'https://localhost:5174',storage:{removeItem(){}}});await assert.rejects(()=>unavailable.token());await assert.rejects(()=>unavailable.login());
let redirected=0;
const preflight=createSession({...sdk,init:async()=>{redirected++;return false;}},
 {origin:'https://localhost:5174',storage:{removeItem(){}},checkReady:async()=>{throw new Error('Discovery unavailable');}});
await assert.rejects(()=>preflight.init());await assert.rejects(()=>preflight.login());assert.equal(redirected,0);
console.log('PASS: memory-only lifecycle, exact PKCE/nonce adapter initialization, concurrent refresh, logout, legacy cleanup and fail-closed outage cases');
