import AppLayout from '../components/AppLayout';
const configured=import.meta.env.VITE_GRAFANA_URL;
let target;
if(configured){try{const url=new URL(configured);if(url.protocol==='https:'&&!url.username&&!url.password)target=url.href;}catch{}}
export default function Monitoring(){return <AppLayout><h1 className="text-xl font-bold">Monitoring &amp; Logs</h1><div className="card my-4 p-5"><p>This page does not query Loki and does not display fabricated request counts. Inspect actual logs and rejection events through the reviewed monitoring deployment.</p>{target?<a className="btn-secondary mt-4" href={target} target="_blank" rel="noreferrer">Open configured Grafana</a>:<p className="mt-4">No approved HTTPS Grafana URL is configured. Ask the operator for the monitoring access path.</p>}</div></AppLayout>;}
