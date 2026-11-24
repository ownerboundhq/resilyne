import {inspect} from './checks.mjs';
const $=id=>document.getElementById(id);
let report=null,filter='all',generation=0;
const el=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
const statusText={pass:'✓ PASSED',attention:'! ATTENTION',unknown:'— NOT ASSESSED'};
function progress(text){$('progress').hidden=false;$('progress').textContent=text;}
function renderChecks(){
 const root=$('checks');root.replaceChildren();
 const list=report.checks.filter(c=>filter==='all'||c.state===filter);
 for(const c of list){const row=el('article','','check-row'),state=el('div',statusText[c.state],'check-state '+c.state),body=el('div','');body.append(el('h4',c.title),el('p',c.detail));if(c.state!=='pass')body.append(el('p',c.action,'action'));row.append(state,body);root.append(row);}
 if(!list.length)root.append(el('p','No checks in this category.','empty'));
}
function render(r,sample=false){
 report={...r,example:sample};filter='all';
 $('result-label').textContent=sample?'EXAMPLE REPORT':'YOUR REPORT';
 $('result-meta').textContent=r.project+' · '+r.filesExamined.toLocaleString()+' files examined'+(r.truncated?' · Partial scan':'');
 $('passed').textContent=r.counts.pass;$('attention').textContent=r.counts.attention;$('unknown').textContent=r.counts.unknown;
 $('scope').textContent=r.scope+(r.truncated?' File limit reached; missing indicators may be unknown.':'');
 const priority=r.checks.filter(c=>c.state==='attention').sort((a,b)=>Number(b.priority==='high')-Number(a.priority==='high')).slice(0,3);
 $('priority').replaceChildren();
 if(priority.length){const box=el('div','','priority-box'),list=el('ol','');for(const c of priority)list.append(el('li',c.action));box.append(el('h3','Start here.'),list);$('priority').append(box);}
 document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter==='all')));
 renderChecks();$('results').hidden=false;$('result-title').scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
}
async function run(files,sample=false,individual=false){
 const current=++generation;
 if(!files.length){progress('No files selected.');return;}
 progress('Inspecting selected files locally…');$('results').hidden=true;report=null;
 try{
  const r=await inspect(files);
  if(current!==generation)return;
  if(individual){r.truncated=true;r.scope+=' Individual file selection does not preserve directory paths; choose a folder for a complete assessment.';for(const c of r.checks)if(c.state==='attention'&&c.id!=='secrets'){c.state='unknown';}for(const c of r.checks)if(c.id==='secrets'&&c.state==='pass')c.state='unknown';r.counts=Object.fromEntries(['pass','attention','unknown'].map(s=>[s,r.checks.filter(c=>c.state===s).length]));}
  progress(sample?'Example complete. No local files accessed.':'Scan complete. No files uploaded.');render(r,sample);
 }catch{if(current===generation)progress('Unable to read the selected files. Choose your project folder again.');}
}
$('folder').addEventListener('change',e=>{run(e.target.files);e.target.value='';});
$('files').addEventListener('change',e=>{run(e.target.files,false,true);e.target.value='';});
$('sample').addEventListener('click',()=>{
 const entries={'package.json':JSON.stringify({scripts:{build:'vite build'},dependencies:{react:'^19.0.0',pg:'^8.0.0'}}),'src/app.tsx':'','src/cart.ts':'','.env':'','README.md':''};
 run(Object.entries(entries).map(([name,content])=>({name:name.split('/').at(-1),webkitRelativePath:'example-app/'+name,size:content.length,text:async()=>content})),true);
});
document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{if(!report)return;filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));renderChecks();}));
function actionPlan(){return ['Resilyne Scan — '+(report.example?'EXAMPLE':'Readiness action plan'),report.scope,'',...report.checks.filter(c=>c.state!=='pass').map(c=>'- '+c.title+': '+c.action)].join('\n');}
$('download').addEventListener('click',()=>{if(!report)return;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='resilyne-readiness-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('copy').addEventListener('click',async()=>{if(!report)return;try{await navigator.clipboard.writeText(actionPlan());$('copy').textContent='Copied ✓';setTimeout(()=>$('copy').textContent='Copy action plan',2000);}catch{progress('Clipboard unavailable. Download the report instead.');}});
