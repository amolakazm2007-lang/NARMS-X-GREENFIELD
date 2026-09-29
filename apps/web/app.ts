type Status='PASS'|'PARTIAL'|'BLOCKED'|'FAIL'|'UNKNOWN';
const $=<T extends HTMLElement>(q:string)=>document.querySelector(q) as T;
async function health():Promise<void>{try{const r=await fetch('/api/v1/system/health');const j=await r.json() as {status:Status};$('#status').textContent=j.status}catch{$('#status').textContent='UNKNOWN'}}
window.addEventListener('load',()=>{void health()});
