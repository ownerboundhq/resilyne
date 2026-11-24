import {randomUUID} from 'node:crypto';
import {config,billable,allowedEndpoint,verificationGate} from './config.mjs';
import {poolFor,one,tx,enqueue,audit,incident,dailyRepair} from './db.mjs';
import {projectGitHub,alerts,deployment,verification} from './github.mjs';
import {sourcePath} from '../lib/core.mjs';
import {propose} from '../lib/repair.mjs';
const cfg=config(), pool=poolFor(cfg);
const failure=new Set(['failure','timed_out','action_required']);
function redact(s){return String(s||'').replace(/(?:sk-proj-|ghp_|github_pat_|sk_live_|sk_test_)[A-Za-z0-9_-]+/g,'[REDACTED]').replace(/(?:password|token|secret|api[_ -]?key)\s*[:=]\s*\S+/gi,'[REDACTED]').slice(0,1200);}
async function evidence(g,r){
 const jobs=(await g.request('/actions/runs/'+r.id+'/jobs?per_page=30')).jobs||[];
 const bad=jobs.filter(j=>failure.has(j.conclusion));
 const steps=bad.flatMap(j=>(j.steps||[]).filter(s=>failure.has(s.conclusion)).map(s=>redact(j.name)+' / '+redact(s.name))).slice(0,10);
 for(const job of bad){
   const id=String(job.check_run_url||'').match(/\/check-runs\/(\d+)$/)?.[1];if(!id)continue;
   try{
     const annotations=await g.request('/check-runs/'+id+'/annotations?per_page=30');
     for(const a of annotations){
       if(a.annotation_level!=='failure')continue;
       try{return {steps,path:sourcePath(a.path),message:redact(a.message),line:a.start_line};}catch{}
     }
   }catch{}
 }
 return {steps};
}
async function autoProposal(p,i,path){
 if(!p.auto_propose||!cfg.apiKey||!path)return;
 await tx(pool,async c=>{
   const a=await one(c,'SELECT * FROM accounts WHERE id=$1 FOR UPDATE',[p.account_id]);
   const current=await one(c,'SELECT * FROM projects WHERE id=$1 AND enabled=true',[p.id]);
   if(!current?.auto_propose||!billable(a.billing_status,cfg.billingRequired))return;
   if(await one(c,"SELECT id FROM jobs WHERE project_id=$1 AND kind='propose' AND payload->>'incidentId'=$2",[p.id,i.id]))return;
   try{await dailyRepair(c,p,i.id,path,cfg.maxDailyAI);}catch(e){if(e.message!=='Daily repair budget exhausted')throw e;}
 });
}
async function scan(p,g){
 const result={errors:[]}, runs=await g.request('/actions/workflows/'+p.workflow_id+'/runs?branch='+encodeURIComponent(p.base_branch)+'&per_page=10');
 const run=runs.workflow_runs?.[0];
 if(run){
   result.ci={name:run.name,conclusion:run.conclusion,status:run.status,sha:run.head_sha,url:run.html_url};
   if(failure.has(run.conclusion)){
     const details=await evidence(g,run);
     const i=await incident(pool,p.id,'ci:'+run.id+':'+run.run_attempt,'ci','CI workflow failed',{...details,runId:run.id,sha:run.head_sha,url:run.html_url});
     await pool.query("UPDATE incidents SET status='superseded' WHERE project_id=$1 AND kind='ci' AND status='open' AND id<>$2",[p.id,i.id]);
     await autoProposal(p,i,details.path);
   }else if(run.conclusion==='success')await pool.query("UPDATE incidents SET status='recovered' WHERE project_id=$1 AND kind='ci' AND status='open'",[p.id]);
 }
 if(p.health_url){
   try{
     const url=allowedEndpoint(p.health_url,cfg.allowlist),start=Date.now();
     const r=await fetch(url,{redirect:'error',signal:AbortSignal.timeout(10000)});
     await r.body?.cancel();result.health={ok:r.ok,status:r.status,latencyMs:Date.now()-start};
     if(!r.ok)throw Error('HTTP '+r.status);
     await pool.query("UPDATE incidents SET status='recovered' WHERE project_id=$1 AND kind='health' AND status='open'",[p.id]);
   }catch(e){result.health={ok:false};await incident(pool,p.id,'health','health','Endpoint health check failed',{message:redact(e.message)});}
 }
 try{
   const a=await alerts(g);result.security={available:a.available,open:a.items.length};
   if(a.available)for(const x of a.items){
     await incident(pool,p.id,'dependabot:'+x.number,'security','Dependency vulnerability: '+redact(x.dependency?.package?.name),{severity:x.security_advisory?.severity,package:x.dependency?.package?.name,url:x.html_url});
   }
   // Only close when the response is complete, not when pagination may hide an alert.
   if(a.available&&a.items.length<100)await pool.query("UPDATE incidents SET status='recovered' WHERE project_id=$1 AND kind='security' AND status='open' AND NOT(fingerprint=ANY($2::text[]))",[p.id,a.items.map(x=>'dependabot:'+x.number)]);
 }catch(e){result.errors.push('Security alerts: '+redact(e.message));}
 try{
   result.deployment=await deployment(g);
   if(['failure','error'].includes(result.deployment?.state))await incident(pool,p.id,'deployment:'+result.deployment.sha,'deployment','Deployment failed',result.deployment);
   else if(result.deployment?.state==='success')await pool.query("UPDATE incidents SET status='recovered' WHERE project_id=$1 AND kind='deployment' AND status='open'",[p.id]);
 }catch(e){result.errors.push('Deployment: '+redact(e.message));}
 await pool.query("UPDATE projects SET scan_result=$2,last_scan=now() WHERE id=$1",[p.id,result]);
 const prs=(await pool.query("SELECT * FROM proposals WHERE project_id=$1 AND status IN ('pr_opened','merge_queued') AND pr_number IS NOT NULL",[p.id])).rows;
 for(const row of prs){
   try{
     const {pr,run,head}=await verification(g,row.pr_number,p.workflow_id);
     const ready=verificationGate(pr,p.workflow_id,run,head,p.repo,p.base_branch);
     await pool.query('UPDATE proposals SET verification=$2 WHERE id=$1',[row.id,{head,ready,conclusion:run?.conclusion||null,runUrl:run?.html_url||null,prState:pr.state,draft:pr.draft}]);
     if(pr.merged)await pool.query("UPDATE proposals SET status='merged' WHERE id=$1",[row.id]);
     else if(pr.state==='closed')await pool.query("UPDATE proposals SET status='closed' WHERE id=$1",[row.id]);
   }catch(e){result.errors.push('PR verification: '+redact(e.message));}
 }
 await pool.query("UPDATE projects SET scan_result=$2 WHERE id=$1",[p.id,result]);
}
async function processJob(j,p,g){
 if(j.kind==='scan')return scan(p,g);
 if(j.kind==='propose'){
   const existing=await one(pool,'SELECT id FROM proposals WHERE id=$1',[j.id]);if(existing)return;
   const i=await one(pool,"SELECT * FROM incidents WHERE id=$1 AND project_id=$2 AND status='open'",[j.payload.incidentId,p.id]);if(!i)throw Error('Incident no longer open');
   const patch=await propose(g,{id:i.id,title:i.title,detail:JSON.stringify(i.evidence)},j.payload.path,{apiKey:cfg.apiKey,model:cfg.model});
   patch.id=j.id;
   await pool.query('INSERT INTO proposals(id,project_id,incident_id,patch) VALUES($1,$2,$3,$4) ON CONFLICT(id) DO NOTHING',[j.id,p.id,i.id,patch]);
   await audit(pool,p.account_id,p.id,'proposal_created',{proposal:j.id});return;
 }
 const row=await one(pool,'SELECT * FROM proposals WHERE id=$1 AND project_id=$2',[j.payload.proposalId,p.id]);
 if(!row)throw Error('Proposal not found');
 const patch=row.patch;
 if(j.kind==='open_pr'){
   if(row.pr_number)return;
   if(row.status!=='approved')throw Error('Proposal not approved');
   const pr=await g.openRepair(patch);
   await pool.query("UPDATE proposals SET status='pr_opened',pr_number=$2,pr_url=$3 WHERE id=$1",[row.id,pr.number,pr.html_url]);return;
 }
 if(j.kind==='merge'){
   if(!cfg.autoMerge||row.status!=='merge_queued')throw Error('Merge not enabled or approved');
   const {pr,run,head}=await verification(g,row.pr_number,p.workflow_id);
   if(pr.merged){await pool.query("UPDATE proposals SET status='merged' WHERE id=$1",[row.id]);return;}
   if(head!==j.payload.head||!verificationGate(pr,p.workflow_id,run,head,p.repo,p.base_branch))throw Error('Verification gate failed; refresh CI and approve again');
   if((await g.head(p.base_branch)).object.sha!==patch.baseSha)throw Error('Base changed; create a fresh proposal');
   const comparison=await g.request('/compare/'+patch.baseSha+'...'+head);
   if(comparison.files?.length!==1||comparison.files[0].filename!==patch.path)throw Error('Unexpected changed files');
   if((await g.file(patch.path,head)).text!==patch.replacement)throw Error('Reviewed source changed');
   const merged=await g.request('/pulls/'+row.pr_number+'/merge','PUT',{sha:head,merge_method:'squash'});
   if(!merged.merged)throw Error('GitHub rejected merge');
   await pool.query("UPDATE proposals SET status='merged' WHERE id=$1",[row.id]);return;
 }
 if(j.kind==='rollback'){
   if(row.status!=='merged')throw Error('Only merged proposals can be reverted');
   if(await one(pool,'SELECT id FROM proposals WHERE id=$1',[j.id]))return;
   const baseSha=(await g.head(p.base_branch)).object.sha,file=await g.file(patch.path,baseSha);
   if(file.text!==patch.replacement)throw Error('File has changed; manual rollback required');
   const revert={id:j.id,incidentId:row.incident_id,path:patch.path,baseBranch:p.base_branch,baseSha,blobSha:file.sha,original:file.text,replacement:patch.original,summary:'Revert previously merged repair '+row.id};
   await pool.query("INSERT INTO proposals(id,project_id,incident_id,patch) VALUES($1,$2,$3,$4) ON CONFLICT(id) DO NOTHING",[j.id,p.id,row.incident_id,revert]);return;
 }
 throw Error('Unsupported job');
}
let stopping=false;
async function tick(){
 const lock=await pool.connect();let held=false;
 try{
   held=(await one(lock,'SELECT pg_try_advisory_lock(92817421) AS held')).held;
   if(!held)return;
   // Global singleton worker. A crashed process loses its DB session lock; unfinished jobs become visible.
   await pool.query("UPDATE jobs SET status=CASE WHEN attempts>=3 THEN 'failed' ELSE 'queued' END,error='Interrupted worker',updated_at=now() WHERE status='running'");
   await pool.query("DELETE FROM sessions WHERE expires_at<now()");
   await pool.query("DELETE FROM deliveries WHERE received_at<now()-interval '30 days'");
   await pool.query("DELETE FROM jobs WHERE kind='scan' AND status IN ('done','failed') AND updated_at<now()-interval '7 days'");
   const due=(await pool.query("SELECT p.* FROM projects p JOIN accounts a ON a.id=p.account_id WHERE p.enabled AND p.next_scan<=now() AND ($1::boolean=false OR a.billing_status IN ('active','trialing')) ORDER BY p.next_scan LIMIT 30",[cfg.billingRequired])).rows;
   for(const p of due)await tx(pool,async c=>{
     await enqueue(c,p.id,'scan','scan:'+p.id+':'+Math.floor(Date.now()/300000));
     await c.query("UPDATE projects SET next_scan=now()+interval '5 minutes' WHERE id=$1",[p.id]);
   });
   for(let n=0;n<15&&!stopping;n++){
     const j=await one(pool,"UPDATE jobs SET status='running',attempts=attempts+1,updated_at=now() WHERE id=(SELECT id FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *");
     if(!j)break;
     try{
       const p=await one(pool,'SELECT p.*,a.billing_status FROM projects p JOIN accounts a ON a.id=p.account_id WHERE p.id=$1',[j.project_id]);
       if(!p?.enabled||!billable(p.billing_status,cfg.billingRequired))throw Error('Project paused or billing inactive');
       await processJob(j,p,await projectGitHub(cfg,p));
       await pool.query("UPDATE jobs SET status='done',updated_at=now(),error=NULL WHERE id=$1",[j.id]);
     }catch(e){
       // Do not automatically repeat costly AI calls or ambiguous external writes on ordinary failures.
       await pool.query("UPDATE jobs SET status='failed',error=$2,updated_at=now() WHERE id=$1",[j.id,redact(e.message)]);
       if(j.kind==='merge')await pool.query("UPDATE proposals SET status='pr_opened' WHERE id=$1 AND status='merge_queued'",[j.payload.proposalId]);
       if(j.kind==='open_pr')await pool.query("UPDATE proposals SET status='approved' WHERE id=$1 AND status='approved'",[j.payload.proposalId]);
     }
   }
 }finally{if(held)await lock.query('SELECT pg_advisory_unlock(92817421)').catch(()=>{});lock.release();}
}
process.on('SIGTERM',()=>{stopping=true;});process.on('SIGINT',()=>{stopping=true;});
while(!stopping){try{await tick();}catch(e){console.error('Worker tick failed:',redact(e.message));}if(process.env.WORKER_ONCE==='true')break;if(!stopping)await new Promise(r=>setTimeout(r,15000));}
await pool.end();
