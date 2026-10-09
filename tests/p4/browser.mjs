import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const require=createRequire(new URL('../../frontend/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const config=JSON.parse(readFileSync(process.env.P4_BROWSER_CONFIG));
const data=JSON.parse(readFileSync(config.fixtures));
const account=data.users.customer,origin='https://localhost:5174';
const results=[];
function sanitized(error) {
 return String(error?.message||error?.name||error).replaceAll(account.password,'[redacted]')
  .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[redacted JWT]')
  .replace(/([?&](?:code|state|nonce|id_token_hint|session_state|code_challenge|session_code)=)[^&\s]+/g,'$1[redacted]');
}
const browser=await chromium.connectOverCDP(config.cdp);
const context=browser.contexts()[0];
// Optional typography must not turn the authentication suite into a Google DNS
// availability check. IdP/API requests and all mandatory SSRF DNS tests remain real.
await context.route(/^https:\/\/fonts\.(?:googleapis|gstatic)\.com\//,
 route=>route.abort('blockedbyclient'));
const networkFailures=[];
context.on('requestfailed',request=>{const u=new URL(request.url());networkFailures.push({host:u.hostname,path:u.pathname,error:request.failure()?.errorText});});
const page=await context.newPage();page.setDefaultTimeout(20000);
async function login(p=page) {
 await p.goto(origin+'/login',{waitUntil:'domcontentloaded'});await p.getByRole('button',{name:'Sign in',exact:true}).click();
 await p.locator('#username').fill(account.username);await p.locator('#password').fill(account.password);
 await p.locator('#kc-login').click();await p.getByRole('button',{name:'Logout',exact:true}).waitFor();
}
async function storage(p=page) {
 const items=await p.evaluate(()=>({local:{...localStorage},session:{...sessionStorage}}));
 for(const [key,value] of Object.entries({...items.local,...items.session})){
  assert.ok(!key.startsWith('fs_'));assert.ok(!/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\./.test(value));
 }
}
async function test(name,fn) {
 try{await fn();results.push({name,status:'passed'});console.log('PASS: '+name);}
 catch(error){
  const current=context.pages().filter(p=>!p.isClosed()).at(-1);
  let diagnostic;
  if(current)diagnostic={path:new URL(current.url()).pathname,query_keys:[...new URL(current.url()).searchParams.keys()],
   visible_text:sanitized((await current.locator('body').innerText().catch(()=>'' )).slice(0,1200))};
  results.push({name,status:'failed',error:error.name,message:sanitized(error),diagnostic});console.log('FAIL: '+name);throw error;
 }
}
try {
 await test('real browser PKCE login, legacy cleanup and memory-only tokens',async()=>{
  await context.addInitScript(()=>{if(location.origin==='https://localhost:5174'){
   for(const k of ['fs_access_token','fs_refresh_token','fs_expires_at','fs_role','fs_user'])localStorage.setItem(k,'obsolete');
  }});
  await login();await storage();
  const me=await page.evaluate(async()=>{const {identity}=await import('/src/identity/runtime.js');
   const r=await fetch('/api/v1/auth/me',{headers:{Authorization:'Bearer '+await identity.token()}});return {status:r.status,user:await r.json()};});
  assert.equal(me.status,200);assert.equal(me.user.id,data.application_id);assert.equal(me.user.role,'customer');
 });
 await test('reload recovers identity through Keycloak SSO without persistent tokens',async()=>{
  await page.reload({waitUntil:'domcontentloaded'});await page.getByRole('button',{name:'Logout',exact:true}).waitFor();await storage();
 });
 await test('single-flight refresh with real Keycloak token endpoint',async()=>{
  await page.clock.install();const expires=await page.evaluate(async()=>{const {identity}=await import('/src/identity/runtime.js');return identity.expiresAt();});
  await page.clock.setSystemTime(expires-1000);let refreshes=0;
  const count=request=>{if(request.url().endsWith('/protocol/openid-connect/token')&&request.postData()?.includes('grant_type=refresh_token'))refreshes++;};
  page.on('request',count);
  const ok=await page.evaluate(async()=>{const {identity}=await import('/src/identity/runtime.js');const values=await Promise.all([identity.token(),identity.token(),identity.token()]);return values.every(v=>v&&v===values[0]);});
  page.off('request',count);assert.equal(ok,true);assert.equal(refreshes,1);await storage();
 });
 await test('IdP session expiration clears application authentication on refresh',async()=>{
  execFileSync(config.compose[0],[...config.compose.slice(1),'run','--rm','--no-deps','-T','tests','python','/tests/p4/browser_setup.py','expire'],{env:process.env,stdio:'pipe'});
  const expires=await page.evaluate(async()=>{const {identity}=await import('/src/identity/runtime.js');return identity.expiresAt();});
  await page.clock.setSystemTime(expires+1000);
  const cleared=await page.evaluate(async()=>{const {identity}=await import('/src/identity/runtime.js');try{await identity.token();}catch{}return !identity.currentToken();});
  assert.equal(cleared,true);await page.getByRole('button',{name:'Sign in',exact:true}).waitFor();
 });
 await page.close();const fresh=await context.newPage();fresh.setDefaultTimeout(20000);
 await test('logout ends SSO and returns to exact configured redirect',async()=>{
  await login(fresh);await fresh.getByRole('button',{name:'Logout',exact:true}).click();
  await fresh.getByRole('button',{name:'Sign in',exact:true}).waitFor();assert.ok(fresh.url().startsWith(origin+'/login'));
  await fresh.reload({waitUntil:'domcontentloaded'});await fresh.getByRole('button',{name:'Sign in',exact:true}).waitFor();await storage(fresh);
 });
 await test('invalid callback state cannot establish authenticated identity',async()=>{
  // Redirect-target routing is not a reliable interception point in CDP. Change
  // the real callback URL at document initialization, before the SPA/SDK loads.
  await fresh.addInitScript(()=>{
   if(location.origin==='https://localhost:5174' && location.pathname==='/oidc/callback' &&
      new URL(location.href).searchParams.has('code') && sessionStorage.getItem('p4-state-probe')==='once'){
    sessionStorage.removeItem('p4-state-probe');const url=new URL(location.href);
    url.searchParams.set('state','invalid-untrusted-state');history.replaceState(history.state,'',url);
    sessionStorage.setItem('p4-state-probe-result','changed');
   }
  });
  await fresh.goto(origin+'/login',{waitUntil:'domcontentloaded'});await fresh.getByRole('button',{name:'Sign in',exact:true}).waitFor();
  await fresh.evaluate(()=>sessionStorage.setItem('p4-state-probe','once'));
  let exchanges=0;
  const count=request=>{if(request.url().endsWith('/protocol/openid-connect/token') && request.postData()?.includes('grant_type=authorization_code'))exchanges++;};
  fresh.on('request',count);await fresh.getByRole('button',{name:'Sign in',exact:true}).click();
  await fresh.locator('#username').fill(account.username);await fresh.locator('#password').fill(account.password);await fresh.locator('#kc-login').click();
  await fresh.getByRole('alert').waitFor();assert.equal(await fresh.getByRole('button',{name:'Logout',exact:true}).count(),0);
  assert.equal(await fresh.evaluate(()=>sessionStorage.getItem('p4-state-probe-result')),'changed');
  fresh.off('request',count);assert.equal(exchanges,0);
  await fresh.evaluate(()=>sessionStorage.removeItem('p4-state-probe-result'));await context.clearCookies();
 });
 await test('cancelled authorization leaves the application signed out',async()=>{
  await fresh.goto(origin+'/login',{waitUntil:'domcontentloaded'});await fresh.getByRole('button',{name:'Sign in',exact:true}).click();
  await fresh.locator('#username').waitFor();const state=new URL(fresh.url()).searchParams.get('state');assert.ok(state);
  await fresh.goto(origin+'/oidc/callback?error=access_denied&state='+encodeURIComponent(state),{waitUntil:'domcontentloaded'});
  await fresh.getByRole('alert').waitFor();assert.equal(await fresh.getByRole('button',{name:'Logout',exact:true}).count(),0);
  await context.clearCookies();
 });
 await test('invalid nonce in one-time SDK transaction rejects a genuine IdP response',async()=>{
  await fresh.goto(origin+'/login',{waitUntil:'domcontentloaded'});await fresh.getByRole('button',{name:'Sign in',exact:true}).click();
  // Change only this disposable client's saved transaction nonce; keep the genuine signed ID token.
  await fresh.evaluate(()=>{});
  await context.addInitScript(()=>{if(location.origin==='https://localhost:5174'){
   for(const key of Object.keys(localStorage)){if(key.startsWith('kc-callback-')){
    const value=JSON.parse(localStorage.getItem(key));value.nonce='tampered-nonce';localStorage.setItem(key,JSON.stringify(value));
   }}
  }});
  await fresh.locator('#username').fill(account.username);await fresh.locator('#password').fill(account.password);await fresh.locator('#kc-login').click();
  await fresh.getByRole('alert').waitFor();assert.equal(await fresh.getByRole('button',{name:'Logout',exact:true}).count(),0);await storage(fresh);
 });
 await test('Keycloak unavailable does not fall back to local password login',async()=>{
  await context.clearCookies();await fresh.route('https://identity-edge:8443/**',route=>route.abort('connectionrefused'));
  await fresh.goto(origin+'/login',{waitUntil:'domcontentloaded'});await fresh.getByRole('alert').waitFor();
  assert.equal(await fresh.locator('input[type=password]').count(),0);assert.equal(await fresh.getByRole('button',{name:'Logout',exact:true}).count(),0);
 });
} catch(error) {
 console.error('Browser validation failed: '+error.name);process.exitCode=1;
} finally {
 writeFileSync(config.results,JSON.stringify({tls_verification:'Chromium verified CA and SAN; no ignoreHTTPSErrors',private_alias_resolution:'actual Compose identity-edge address only',navigation_readiness:'DOMContentLoaded then application assertions; external font load is not auth readiness',optional_fonts:'Google typography requests explicitly blocked in test browser only; no IdP/API/DNS assertion substituted',network_failures:networkFailures,tests:results},null,2));
 await context.close();
 await browser.close();
}
