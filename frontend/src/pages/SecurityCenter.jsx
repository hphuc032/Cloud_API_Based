import { useState } from 'react';
import AppLayout from '../components/AppLayout';
import { useAuth } from '../api/AuthContext';
import { api, getTokenStatus } from '../api/api';

const lab=import.meta.env.VITE_SECURITY_LAB==='true';
const headerNames=['strict-transport-security','x-content-type-options','x-frame-options','referrer-policy','permissions-policy','content-security-policy'];
export default function SecurityCenter(){
 const {role}=useAuth();const [results,setResults]=useState([]),[busy,setBusy]=useState(false);
 const [order,setOrder]=useState(''),[body,setBody]=useState(''),[signature,setSignature]=useState(''),[timestamp,setTimestamp]=useState('');
 async function request(label,config){
  let response;
  try{response=await api.request({...config,intentionalSecurityProbe:true});}
  catch(error){response=error.response;if(!response){const row={label,status:null,message:'Network request failed'};setResults(r=>[row,...r]);return row;}}
  const message=JSON.stringify(response.data).slice(0,500);
  const headers=Object.fromEntries(headerNames.map(name=>[name,response.headers[name]||'not present']));
  const row={label,status:response.status,message,headers,replayed:response.headers['x-webhook-replayed'],rateLayer:response.headers['x-ratelimit-layer']||'native/post-auth or not reported'};
  setResults(r=>[row,...r].slice(0,100));return row;
 }
 async function run(label,config){setBusy(true);try{return await request(label,config);}finally{setBusy(false);}}
 async function burst(){setBusy(true);try{for(let i=0;i<65;i++){const row=await request(`Product read ${i+1}`,{url:'/api/v1/products/',skipAuth:true});if(row.status===429||row.status===null)break;}}finally{setBusy(false);}}
 function signedDelivery(){return run('Exact operator-signed delivery / retry',{method:'POST',url:'/api/v1/webhooks/receive',data:body,skipAuth:true,transformRequest:[value=>value],headers:{'Content-Type':'application/json','X-Signature':signature,'X-Timestamp':timestamp}});}
 return <AppLayout><h1 className="text-xl font-bold">Security Center</h1>
  <p className="my-3">Role from /auth/me: {role}. Token: {getTokenStatus()}. Results below are observed HTTP responses, not security pass percentages.</p>
  <div className="card space-y-3 p-5">
   <button className="btn-secondary" disabled={busy} onClick={()=>run('Missing access token',{url:'/api/v1/auth/me',skipAuth:true})}>Missing access token</button>
   <button className="btn-secondary" disabled={busy} onClick={()=>run('Invalid access token',{url:'/api/v1/auth/me',skipAuth:true,headers:{Authorization:'Bearer invalid-lab-token'}})}>Invalid access token</button>
   <button className="btn-secondary" disabled={busy} onClick={()=>run('Admin access with current role',{url:'/api/v1/users/'})}>Check admin authorization</button>
   <button className="btn-secondary" disabled={busy} onClick={()=>run('Observed browser/API security headers',{url:'/health',skipAuth:true})}>Inspect security headers</button>
   <button className="btn-secondary" disabled={busy} onClick={()=>run('SQL-shaped UUID input validation',{url:'/api/v1/products/',params:{category_id:"' OR 1=1 --"},skipAuth:true})}>SQL-shaped input</button>
  </div>
  {lab?<section className="card my-4 space-y-3 p-5"><h2 className="font-bold">Disposable lab only</h2>
   <p>Use fixtures owned by this lab. Rate bursts can throttle other users sharing the gateway peer. No credentials or signing secrets are supplied by this page.</p>
   <input className="input-field" aria-label="Other customer order ID" value={order} onChange={e=>setOrder(e.target.value)} placeholder="Other disposable customer's order UUID"/>
   <button className="btn-secondary" disabled={busy||!order} onClick={()=>run('Order ownership with current role',{url:'/api/v1/orders/'+encodeURIComponent(order)})}>Check BOLA</button>
   <button className="btn-secondary" disabled={busy} onClick={()=>run('Forged webhook MAC',{method:'POST',url:'/api/v1/webhooks/receive',skipAuth:true,data:JSON.stringify({event:'payment.success',event_id:crypto.randomUUID(),order_id:'lab-ack-only'}),headers:{'Content-Type':'application/json','X-Timestamp':String(Math.floor(Date.now()/1000)),'X-Signature':'sha256='+'0'.repeat(64)}})}>Webhook forgery</button>
   <textarea className="input-field" aria-label="Exact signed webhook body" value={body} onChange={e=>setBody(e.target.value)} placeholder="Exact raw JSON from the operator's lab CLI"/>
   <input className="input-field" aria-label="Webhook timestamp" value={timestamp} onChange={e=>setTimestamp(e.target.value)} placeholder="X-Timestamp"/>
   <input className="input-field" aria-label="Webhook signature" value={signature} onChange={e=>setSignature(e.target.value)} placeholder="X-Signature (temporary, not persisted)"/>
   <button className="btn-secondary" disabled={busy||!body||!timestamp||!signature} onClick={signedDelivery}>Send / replay exact signed delivery</button>
   <button className="btn-secondary" disabled={busy||!['staff','admin'].includes(role)} onClick={()=>run('Blocked metadata URL',{method:'POST',url:'/api/v1/security/fetch-url',data:{url:'http://169.254.169.254'}})}>SSRF metadata validation</button>
   <button className="btn-secondary" disabled={busy} onClick={burst}>Rate burst (up to 65 public reads)</button>
   <p>Invalid client certificates cannot be supplied by browser JavaScript. Run the isolated P2 certificate tests and review their actual TLS evidence.</p>
  </section>:<p className="my-4">BOLA fixtures, signed retries and traffic bursts require a separately built disposable lab (VITE_SECURITY_LAB=true).</p>}
  <section aria-live="polite" className="card my-4 p-5"><h2 className="font-bold">Observed responses</h2>{results.length===0?<p>No probes executed.</p>:results.map((r,i)=><article key={i} className="my-3 rounded border p-3"><p>{r.label}: {r.status===null?'network failure':`HTTP ${r.status}`}</p><pre className="whitespace-pre-wrap break-words text-xs">{r.message}</pre>{r.replayed&&<p>Webhook replay: {r.replayed}</p>}{r.status===429&&<p>Limiter: {r.rateLayer}</p>}{r.label.includes('headers')&&<pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(r.headers,null,2)}</pre>}</article>)}</section>
 </AppLayout>;
}
