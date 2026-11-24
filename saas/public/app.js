const $=id=>document.getElementById(id);
const el=(tag,text='',cls='')=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
const date=x=>x?new Date(x).toLocaleString():'Never';
let me,selected,loading=false;
function notice(message){$('notice').hidden=!message;$('notice').textContent=message||'';}
async function api(path,data){
 const r=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
 const result=await r.json();if(!r.ok)throw Error(result.error||'Request failed');return result;
}
function btn(label,fn,primary=false){const b=el('button',label,primary?'primary':'secondary');b.type='button';b.onclick=()=>act(fn);return b;}
function ghLink(url,text){try{const u=new URL(url);if(u.protocol!=='https:'||u.hostname!=='github.com')return el('span',text);const a=el('a',text);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{return el('span',text);}}
async function act(fn){if(loading)return;loading=true;notice('');try{await fn();}catch(e){notice(e.message);}finally{loading=false;}}
function panel(title){const p=el('section','','panel');p.append(el('h2',title));return p;}
function badge(value){return el('div',String(value).replaceAll('_',' ').toUpperCase(),'status '+(['success','recovered','merged','done'].includes(value)?'good':['failed','failure','open'].includes(value)?'bad':''));}
async function refresh(){
 me=await api('me');$('account').replaceChildren();$('landing').hidden=!!me.account;$('workspace').hidden=!me.account;if(!me.account)return;
 $('account').append(el('span',me.account.login),btn('Sign out',async()=>{await api('logout',{});location.reload();}));
 $('billing').replaceChildren();
 if(me.billingConfigured){
   const p=el('div','','panel heading');p.append(el('span','Subscription: '+me.account.billing),btn('Manage subscription',async()=>{
     const result=await api('billing',{});const u=new URL(result.url);
     if(u.protocol!=='https:'||!['checkout.stripe.com','billing.stripe.com'].includes(u.hostname))throw Error('Unexpected billing URL');location.assign(u.href);
   },true));$('billing').append(p);
 }
 const {projects}=await api('projects');$('projects').replaceChildren();
 if(!projects.some(p=>p.id===selected))selected=projects[0]?.id;
 for(const p of projects){const b=btn(p.repo,async()=>{selected=p.id;await refresh();});b.className='project '+(p.id===selected?'active':'');$('projects').append(b);}
 if(selected)await detail();else{$('detail').replaceChildren();const p=panel('Connect your first application');p.append(el('p','Install Resilyne on a personal GitHub repository with an active CI workflow.'));$('detail').append(p);}
}
function metric(name,value,sub){const p=el('div','','panel');p.append(el('div',name,'eyebrow'),el('div',String(value),'metric'),el('small',sub));return p;}
async function detail(){
 const s=await api('projects/'+selected),p=s.project,root=$('detail');root.replaceChildren();
 const base='projects/'+p.id+'/';
 const head=panel(p.repo);head.append(el('p','Branch: '+p.base_branch+' · '+(p.enabled?'Monitoring enabled':'Paused')+' · Last scan: '+date(p.last_scan)));
 const controls=el('div','','actions');controls.append(btn('Run scan',async()=>{await api(base+'scan',{});await detail();},true),btn(p.enabled?'Pause':'Resume',async()=>{await api(base+'settings',{enabled:!p.enabled});await detail();}),btn(p.auto_propose?'Disable automatic proposals':'Enable automatic proposals',async()=>{
   if(!p.auto_propose&&!confirm('Allow Resilyne to send eligible source files and redacted CI annotations to the AI provider?'))return;
   await api(base+'settings',{autoPropose:!p.auto_propose});await detail();
 }));head.append(controls);root.append(head);
 const m=el('div','','metrics'),r=p.scan_result||{};
 m.append(metric('Endpoint health',r.health?(r.health.ok?'Healthy':'Failed'):'Not configured',r.health?.latencyMs!==undefined?r.health.latencyMs+' ms':'HTTP probe'),metric('CI status',r.ci?.conclusion||r.ci?.status||'Unknown','Selected workflow'),metric('Open incidents',s.incidents.filter(i=>i.status==='open').length,'Latest 100 incidents'));root.append(m);
 const monitors=panel('Infrastructure signals');
 monitors.append(el('p','Dependency alerts: '+(r.security?.available?r.security.open:'Unavailable or not scanned')),el('p','GitHub deployment: '+(r.deployment?.state||'Unknown')));
 if(r.ci?.url)monitors.append(ghLink(r.ci.url,'View CI run'));
 for(const e of r.errors||[])monitors.append(el('p',e));root.append(monitors);
 const incidents=panel('Incidents');if(!s.incidents.length)incidents.append(el('p','No recorded incidents. Monitoring results will appear after a scan.'));
 for(const i of s.incidents){
   const row=el('div','','line');row.append(badge(i.status),el('h3',i.title),el('small',date(i.last_seen)));
   const evidence=el('details');evidence.append(el('summary','Evidence'),el('pre',JSON.stringify(i.evidence,null,2)));row.append(evidence);
   if(i.evidence.url)row.append(ghLink(i.evidence.url,'View source'));
   if(i.status==='open'&&me.aiConfigured&&p.enabled){
     const c=el('div','','actions'),input=el('input');input.placeholder='src/example.ts';input.value=i.evidence.path||'';input.setAttribute('aria-label','Source file path');
     c.append(input,btn('Propose repair',async()=>{if(!confirm('Send the selected source file and incident evidence to the AI provider?'))return;await api(base+'propose',{incidentId:i.id,path:input.value});await detail();}));row.append(c);
   }
   incidents.append(row);
 }root.append(incidents);
 const repairs=panel('Repair review');repairs.append(el('p','Draft pull requests require explicit approval. Source changes are not verified until the selected CI workflow passes. Before opening a PR, ensure the repository’s workflows cannot expose production secrets to proposed code.'));
 if(!s.proposals.length)repairs.append(el('p','No repair proposals.'));
 for(const row of s.proposals){
   const item=el('div','','line'),patch=row.patch;
   item.append(badge(row.status),el('h3',patch.path),el('p',patch.summary),el('small','Base '+patch.baseSha.slice(0,12)));
   for(const [label,code] of [['Original source',patch.original],['Proposed source',patch.replacement]]){const d=el('details');d.append(el('summary',label),el('pre',code));item.append(d);}
   if(row.pr_url)item.append(ghLink(row.pr_url,'Open pull request'));
   if(row.verification){item.append(el('p','CI gate: '+(row.verification.ready?'Passed':row.verification.conclusion||'Not ready')+(row.verification.draft?' · Mark ready for review in GitHub':'')));if(row.verification.runUrl)item.append(ghLink(row.verification.runUrl,'View verification run'));}
   const c=el('div','','actions');
   const action=(label,name,confirmation)=>btn(label,async()=>{if(confirmation&&!confirm(confirmation))return;await api(base+'proposals/'+row.id+'/action',{action:name});await detail();},name==='approve');
   if(['proposed','approved'].includes(row.status))c.append(action(row.status==='approved'?'Retry opening draft PR':'Approve draft PR','approve','Authorize a draft PR containing this exact proposed source? GitHub workflows may run.'));
   if(row.status==='proposed')c.append(action('Reject','reject'));
   if(row.status==='pr_opened'&&row.verification?.ready&&me.mergeEnabled)c.append(action('Approve merge','merge','Merge this verified source change? Your existing deployment workflows may run.'));
   if(row.status==='merged')c.append(action('Prepare revert','rollback','Prepare a reverse patch for review? It will not change production yet.'));
   item.append(c);repairs.append(item);
 }root.append(repairs);
 const jobs=panel('Activity and jobs');if(!s.jobs.length)jobs.append(el('p','No jobs recorded.'));
 for(const j of s.jobs){const item=el('div','','line');item.append(badge(j.status),el('h3',j.kind.replaceAll('_',' ')),el('small',date(j.created_at)+' · Attempts: '+j.attempts));if(j.error)item.append(el('p',j.error));jobs.append(item);}root.append(jobs);
 const audit=panel('Audit trail');for(const a of s.audit){const item=el('div','','line');item.append(el('h3',a.action.replaceAll('_',' ')),el('small',date(a.created_at)));audit.append(item);}root.append(audit);
}
$('refresh').onclick=()=>act(refresh);
$('connect').onclick=()=>act(async()=>{
 const dlg=$('setup'),link=$('install-link');link.replaceChildren();
 if(me.appSlug)link.append(ghLink('https://github.com/apps/'+me.appSlug+'/installations/new','Install Resilyne GitHub App'));
 $('health').replaceChildren(new Option('None',''));for(const u of me.allowlist||[])$('health').append(new Option(u,u));
 const id=new URLSearchParams(location.search).get('installation_id');if(id&&/^\d+$/.test(id))$('installation').value=id;
 dlg.showModal();
});
$('close').onclick=()=>$('setup').close();
$('inspect').onclick=()=>act(async()=>{
 const {repositories}=await api('installations/inspect',{installationId:$('installation').value});$('repo').replaceChildren(new Option('Select repository',''));$('workflow').replaceChildren();
 for(const r of repositories)$('repo').append(new Option(r.name,String(r.id)));
});
$('repo').onchange=()=>act(async()=>{
 $('workflow').replaceChildren(new Option('Select workflow',''));if(!$('repo').value)return;
 const {workflows}=await api('installations/workflows',{installationId:$('installation').value,repositoryId:$('repo').value});
 for(const w of workflows)$('workflow').append(new Option(w.name,String(w.id)));
});
$('setup-form').onsubmit=e=>{e.preventDefault();act(async()=>{
 const result=await api('projects',{installationId:$('installation').value,repositoryId:$('repo').value,workflowId:$('workflow').value,healthUrl:$('health').value,autoPropose:$('auto').checked});
 selected=result.id;$('setup').close();await refresh();
});};
act(refresh);
