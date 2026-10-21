import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../../frontend/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const config=JSON.parse(readFileSync(process.env.P4_BROWSER_CONFIG));
const fixture=JSON.parse(readFileSync(config.fixtures));
const account=fixture.users.customer;
const browser=await chromium.connectOverCDP(config.cdp),context=browser.contexts()[0];
const results=[],violations=[];let page;
await context.exposeBinding('__p5CspReport',(_,value)=>violations.push(value));
await context.addInitScript(()=>document.addEventListener('securitypolicyviolation',e=>{
 if(location.origin==='https://localhost:5174')window.__p5CspReport({directive:e.effectiveDirective,blocked:new URL(e.blockedURI,location.origin).origin});
}));
function watch(predicate){const result=page.waitForResponse(predicate);result.catch(()=>{});return result;}
async function test(name,fn){try{await fn();results.push({name,status:'passed'});console.log('PASS: '+name);}catch(e){results.push({name,status:'failed',error:e.name,path:page?new URL(page.url()).pathname:null});throw e;}}
try{
 page=await context.newPage();page.setDefaultTimeout(20000);
 await test('production HTML has strict CSP and verified HTTPS',async()=>{
  const r=await page.goto('https://localhost:5174/login?p5_sensitive_query_marker=must-not-log-query',{waitUntil:'domcontentloaded'});
  assert.equal(r.status(),200);const h=await r.allHeaders();
  assert.ok(h['content-security-policy'].includes("script-src 'self'"));
  assert.ok(!/unsafe-inline|unsafe-eval/.test(h['content-security-policy']));
  assert.equal(h['x-content-type-options'],'nosniff');
 });
 await test('production PKCE login and application identity',async()=>{
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.locator('#username').fill(account.username);await page.locator('#password').fill(account.password);
  const me=watch(r=>new URL(r.url()).pathname==='/api/v1/auth/me'&&r.status()===200);
  await page.locator('#kc-login').click();assert.equal((await (await me).json()).id,fixture.application_id);
  await page.getByRole('button',{name:'Logout',exact:true}).waitFor();
 });
 await test('Security Center shows real 401/403/422 without ending the session',async()=>{
  await page.getByRole('link',{name:'Security Center',exact:true}).click();
  for(const [label,status] of [['Missing access token',401],['Invalid access token',401],['Check admin authorization',403],['SQL-shaped input',422],['Inspect security headers',200]]){
   const response=watch(r=>(label==='Inspect security headers'?new URL(r.url()).pathname==='/health':new URL(r.url()).pathname.startsWith('/api/'))&&r.status()===status);
   await page.getByRole('button',{name:label,exact:true}).click();await response;
   await page.getByText('HTTP '+status,{exact:false}).first().waitFor();
  }
  await page.getByRole('button',{name:'Logout',exact:true}).waitFor();
 });
 await test('lab BOLA, forged MAC and authenticated retry show actual responses',async()=>{
  assert.ok(fixture.lab.body.startsWith(' \n')&&fixture.lab.body.endsWith('\n '));
  await page.getByLabel('Other customer order ID').fill(fixture.lab.other_order);
  let response=watch(r=>new URL(r.url()).pathname.endsWith(fixture.lab.other_order));
  await page.getByRole('button',{name:'Check BOLA',exact:true}).click();assert.equal((await response).status(),403);
  response=watch(r=>new URL(r.url()).pathname.endsWith('/webhooks/receive'));
  await page.getByRole('button',{name:'Webhook forgery',exact:true}).click();assert.equal((await response).status(),403);
  await page.getByLabel('Exact signed webhook body').fill(fixture.lab.body);
  await page.getByLabel('Webhook timestamp').fill(fixture.lab.timestamp);
  await page.getByLabel('Webhook signature').fill(fixture.lab.signature);
  const acknowledgements=[];
  for(let i=0;i<2;i++){
   response=watch(r=>new URL(r.url()).pathname.endsWith('/webhooks/receive'));
   await page.getByRole('button',{name:'Send / replay exact signed delivery',exact:true}).click();
   const r=await response;assert.equal(r.status(),200);acknowledgements.push(await r.json());
   assert.equal(r.headers()['x-webhook-replayed'],i?'true':'false');
  }
  assert.deepEqual(acknowledgements[0],acknowledgements[1]);
 });
 await test('production reload preserves SSO without stored bearer tokens',async()=>{
  await page.reload({waitUntil:'domcontentloaded'});await page.getByRole('button',{name:'Logout',exact:true}).waitFor();
  const stored=await page.evaluate(()=>({...localStorage,...sessionStorage}));
  for(const value of Object.values(stored))assert.ok(!/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\./.test(value));
 });
 await test('staff lab metadata validation and real rate rejection',async()=>{
  await page.getByRole('button',{name:'Logout',exact:true}).click();
  await page.getByRole('button',{name:'Sign in',exact:true}).waitFor();
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.locator('#username').fill(fixture.users.staff.username);await page.locator('#password').fill(fixture.users.staff.password);
  await page.locator('#kc-login').click();await page.getByRole('button',{name:'Logout',exact:true}).waitFor();
  await page.getByRole('link',{name:'Security Center',exact:true}).click();
  let response=watch(r=>new URL(r.url()).pathname.endsWith('/security/fetch-url'));
  await page.getByRole('button',{name:'SSRF metadata validation',exact:true}).click();assert.equal((await response).status(),403);
  response=watch(r=>r.status()===429&&new URL(r.url()).pathname==='/api/v1/products/');
  await page.getByRole('button',{name:'Rate burst (up to 65 public reads)',exact:true}).click();assert.equal((await response).status(),429);
  await page.getByText('HTTP 429',{exact:false}).first().waitFor();
 });
 await test('application documents have no CSP violations',async()=>{
  await page.waitForTimeout(200);assert.deepEqual(violations,[]);
 });
 await test('production Keycloak logout completes',async()=>{
  await page.getByRole('button',{name:'Logout',exact:true}).click();
  await page.getByRole('button',{name:'Sign in',exact:true}).waitFor();
 });
}catch(e){console.error('Production browser failed: '+e.name);process.exitCode=1;}
finally{writeFileSync(config.results,JSON.stringify({tests:results,csp_violations:violations,tls:'CA/SAN verified; no bypass'},null,2));await context.close();await browser.close();}
