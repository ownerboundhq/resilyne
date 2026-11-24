import express from 'express';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {config,nonce,sha,equal,parseCookies,positiveId,uuid,verifySignature,allowedEndpoint,billable} from './config.mjs';
import {poolFor,one,tx,enqueue,audit,dailyRepair} from './db.mjs';
import {oauthUser,verifyInstallation,appJWT,apiRequest,installationToken,connectRepo,projectGitHub} from './github.mjs';
import {stripeFor,checkout,reconcileBilling} from './billing.mjs';
import {sourcePath} from '../lib/core.mjs';
const cfg=config(),pool=poolFor(cfg),stripe=stripeFor(cfg),app=express();
app.disable('x-powered-by');
app.use((req,res,next)=>{
 res.set({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"});
 if(cfg.secure)res.set('Strict-Transport-Security','max-age=31536000');
 next();
});
const cookieOptions={httpOnly:true,secure:cfg.secure,sameSite:'lax',path:'/'};
const limit=new Map();
function rate(req,res,next){
 const key=req.ip,now=Date.now();let x=limit.get(key);
 if(!x||now-x.start>=60000){x={start:now,n:0};limit.set(key,x);}
 if(++x.n>120)return res.status(429).json({error:'Too many requests'});
 if(limit.size>10000)for(const [k,v] of limit)if(now-v.start>60000)limit.delete(k);
 next();
}
app.get('/healthz',async(req,res)=>{try{await pool.query('SELECT 1');res.json({ok:true});}catch{res.status(503).json({ok:false});}});
app.post('/webhooks/github',express.raw({type:'application/json',limit:'1mb'}),async(req,res)=>{
 if(!Buffer.isBuffer(req.body)||!verifySignature(cfg.webhookSecret,req.body,req.get('x-hub-signature-256')))return res.sendStatus(401);
 const delivery=req.get('x-github-delivery'),type=req.get('x-github-event');
 if(!delivery||delivery.length>100)return res.sendStatus(400);
 const payload=JSON.parse(req.body.toString('utf8'));
 await tx(pool,async c=>{
   if(!await one(c,'INSERT INTO deliveries(id) VALUES($1) ON CONFLICT DO NOTHING RETURNING id',['github:'+delivery]))return;
   const installation=payload.installation?.id;
   if(type==='installation'&&['deleted','suspend'].includes(payload.action)&&installation){
      await c.query('UPDATE projects SET enabled=false WHERE installation_id=$1',[installation]);return;
   }
   if(type==='installation_repositories'&&installation){
      for(const repo of payload.repositories_removed||[])await c.query('UPDATE projects SET enabled=false WHERE installation_id=$1 AND repository_id=$2',[installation,repo.id]);return;
   }
   if(!installation||!payload.repository?.id||!['workflow_run','check_run','deployment_status','dependabot_alert','push','pull_request'].includes(type))return;
   if(type==='workflow_run'&&payload.action!=='completed')return;
   const projects=(await c.query('SELECT id FROM projects WHERE installation_id=$1 AND repository_id=$2 AND enabled',[installation,payload.repository.id])).rows;
   for(const p of projects)await enqueue(c,p.id,'scan','webhook-scan:'+p.id+':'+Math.floor(Date.now()/60000));
 });
 res.sendStatus(202);
});
app.post('/webhooks/stripe',express.raw({type:'application/json',limit:'256kb'}),async(req,res)=>{
 if(!stripe||!cfg.stripeWebhook||!Buffer.isBuffer(req.body))return res.sendStatus(503);
 let event;try{event=stripe.webhooks.constructEvent(req.body,req.get('stripe-signature'),cfg.stripeWebhook);}catch{return res.sendStatus(400);}
 await reconcileBilling(pool,stripe,cfg,event);res.sendStatus(200);
});
app.use(rate);
app.use(express.json({limit:'16kb'}));
app.get('/auth/login',(req,res)=>{
 const state=nonce();res.cookie('resilyne_oauth',state,{...cookieOptions,maxAge:600000});
 const q=new URLSearchParams({client_id:cfg.clientId,redirect_uri:cfg.origin+'/auth/callback',state});
 res.redirect('https://github.com/login/oauth/authorize?'+q);
});
app.get('/auth/callback',async(req,res)=>{
 const state=parseCookies(req.headers.cookie).resilyne_oauth;
 res.clearCookie('resilyne_oauth',cookieOptions);
 if(!state||typeof req.query.state!=='string'||!equal(state,req.query.state)||typeof req.query.code!=='string')return res.status(400).send('Authorization state invalid. Return to the dashboard and sign in again.');
 const user=await oauthUser(cfg,req.query.code),id=positiveId(user.id);
 await pool.query('INSERT INTO accounts(id,login) VALUES($1,$2) ON CONFLICT(id) DO UPDATE SET login=excluded.login',[id,user.login]);
 const old=parseCookies(req.headers.cookie).resilyne_session;
 if(old)await pool.query('DELETE FROM sessions WHERE hash=$1',[sha(old)]);
 const session=nonce();await pool.query("INSERT INTO sessions(hash,account_id,expires_at) VALUES($1,$2,now()+interval '8 hours')",[sha(session),id]);
 res.cookie('resilyne_session',session,{...cookieOptions,maxAge:8*3600000});res.redirect('/');
});
app.use('/api',async(req,res,next)=>{
 if(req.method!=='GET'&&req.get('origin')!==cfg.origin)return res.status(403).json({error:'Origin rejected'});
 const raw=parseCookies(req.headers.cookie).resilyne_session;
 req.account=raw?await one(pool,'SELECT a.* FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.hash=$1 AND s.expires_at>now()',[sha(raw)]):null;
 if(!req.account){if(req.path==='/me')return res.json({account:null});return res.status(401).json({error:'Sign in required'});}
 next();
});
app.get('/api/me',(req,res)=>res.json({account:{id:req.account.id,login:req.account.login,billing:req.account.billing_status},appSlug:/^[a-zA-Z0-9-]+$/.test(cfg.appSlug)?cfg.appSlug:null,billingConfigured:!!(stripe&&cfg.priceId),billingRequired:cfg.billingRequired,mergeEnabled:cfg.autoMerge,autoDraftEnabled:cfg.autoDraft,aiConfigured:!!cfg.apiKey,allowlist:cfg.allowlist,limits:{projects:cfg.maxProjects,dailyAI:cfg.maxDailyAI}}));
app.post('/api/logout',async(req,res)=>{await pool.query('DELETE FROM sessions WHERE hash=$1',[sha(parseCookies(req.headers.cookie).resilyne_session)]);res.clearCookie('resilyne_session',cookieOptions);res.json({ok:true});});
app.post('/api/billing',async(req,res)=>res.json({url:await checkout(pool,stripe,cfg,req.account.id)}));
function entitled(req,res,next){if(!billable(req.account.billing_status,cfg.billingRequired))return res.status(402).json({error:'Active subscription required'});next();}
app.post('/api/installations/inspect',entitled,async(req,res)=>{
 const id=positiveId(req.body.installationId);
 await verifyInstallation(cfg,req.account.id,id);
 const token=(await apiRequest('/app/installations/'+id+'/access_tokens',appJWT(cfg),'POST',{})).token;
 const data=await apiRequest('/installation/repositories?per_page=100',token);
 res.json({repositories:data.repositories.filter(r=>String(r.owner.id)===String(req.account.id)&&!r.archived&&!r.disabled).map(r=>({id:r.id,name:r.full_name})),truncated:data.total_count>100});
});
app.post('/api/installations/workflows',entitled,async(req,res)=>{
 const id=positiveId(req.body.installationId),repo=positiveId(req.body.repositoryId);
 await verifyInstallation(cfg,req.account.id,id);
 const token=await installationToken(cfg,id,repo);
 const m=await apiRequest('/repositories/'+repo,token);
 if(String(m.owner.id)!==String(req.account.id))throw Error('Repository not owned by this account');
 const data=await apiRequest('/repos/'+m.full_name+'/actions/workflows?per_page=100',token);
 res.json({workflows:data.workflows.filter(w=>w.state==='active').map(w=>({id:w.id,name:w.name})),truncated:data.total_count>100});
});
app.get('/api/projects',async(req,res)=>{
 res.json({projects:(await pool.query('SELECT * FROM projects WHERE account_id=$1 ORDER BY repo',[req.account.id])).rows});
});
app.post('/api/projects',entitled,async(req,res)=>{
 const installation=positiveId(req.body.installationId),repository=positiveId(req.body.repositoryId),workflow=positiveId(req.body.workflowId);
 const health=allowedEndpoint(req.body.healthUrl,cfg.allowlist);
 const meta=await connectRepo(cfg,req.account.id,installation,repository,workflow);
 const id=randomUUID();
 await tx(pool,async c=>{
   await one(c,'SELECT id FROM accounts WHERE id=$1 FOR UPDATE',[req.account.id]);
   const n=await one(c,'SELECT count(*)::int AS n FROM projects WHERE account_id=$1',[req.account.id]);
   if(n.n>=cfg.maxProjects)throw Error('Project limit reached');
   await c.query('INSERT INTO projects(id,account_id,installation_id,repository_id,repo,base_branch,workflow_id,health_url,auto_propose) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)',[id,req.account.id,installation,repository,meta.repo,meta.branch,workflow,health,req.body.autoPropose===true]);
   await enqueue(c,id,'scan','initial:'+id);
   await audit(c,req.account.id,id,'project_connected',{repository:meta.repo});
 });
 res.status(201).json({id});
});
async function owned(req,res,next){
 const id=uuid(req.params.id);
 req.project=await one(pool,'SELECT * FROM projects WHERE id=$1 AND account_id=$2',[id,req.account.id]);
 if(!req.project)return res.status(404).json({error:'Project not found'});next();
}
app.get('/api/projects/:id',owned,async(req,res)=>{
 const id=req.project.id;
 const [incidents,proposals,jobs,logs]=await Promise.all([
   pool.query('SELECT * FROM incidents WHERE project_id=$1 ORDER BY last_seen DESC LIMIT 100',[id]),
   pool.query('SELECT * FROM proposals WHERE project_id=$1 ORDER BY created_at DESC LIMIT 30',[id]),
   pool.query('SELECT id,kind,status,error,payload,attempts,created_at FROM jobs WHERE project_id=$1 ORDER BY created_at DESC LIMIT 50',[id]),
   pool.query('SELECT action,detail,created_at FROM audit WHERE project_id=$1 ORDER BY created_at DESC LIMIT 30',[id])
 ]);
 res.json({project:req.project,incidents:incidents.rows,proposals:proposals.rows,jobs:jobs.rows,audit:logs.rows});
});
app.post('/api/projects/:id/settings',owned,async(req,res)=>{
 if(req.body.enabled===true){
   if(!billable(req.account.billing_status,cfg.billingRequired))return res.status(402).json({error:'Subscription required'});
   await projectGitHub(cfg,req.project);
 }
 const enabled=typeof req.body.enabled==='boolean'?req.body.enabled:req.project.enabled;
 const auto=typeof req.body.autoPropose==='boolean'?req.body.autoPropose:req.project.auto_propose;
 const draft=auto&&cfg.autoDraft&&(typeof req.body.autoDraft==='boolean'?req.body.autoDraft:req.project.auto_draft);
 await tx(pool,async c=>{
   await c.query('UPDATE projects SET enabled=$2,auto_propose=$3,auto_draft=$4,next_scan=now() WHERE id=$1',[req.project.id,enabled,auto,draft]);
   await audit(c,req.account.id,req.project.id,'settings_changed',{enabled,autoPropose:auto,autoDraft:draft});
 });res.json({ok:true});
});
app.post('/api/projects/:id/scan',owned,entitled,async(req,res)=>{
 if(!req.project.enabled)throw Error('Project paused');
 await enqueue(pool,req.project.id,'scan','manual-scan:'+req.project.id+':'+Math.floor(Date.now()/60000));res.json({ok:true});
});
app.post('/api/projects/:id/propose',owned,entitled,async(req,res)=>{
 if(!cfg.apiKey||!req.project.enabled)throw Error('AI unavailable or project paused');
 const incidentId=uuid(req.body.incidentId),path=req.body.path?sourcePath(req.body.path):null;
 await tx(pool,async c=>{
   await one(c,'SELECT id FROM accounts WHERE id=$1 FOR UPDATE',[req.account.id]);
   if(!await one(c,"SELECT id FROM incidents WHERE id=$1 AND project_id=$2 AND status='open'",[incidentId,req.project.id]))throw Error('Open incident not found');
   await dailyRepair(c,req.project,incidentId,path,cfg.maxDailyAI);
   await audit(c,req.account.id,req.project.id,'repair_requested',{incidentId,path});
 });res.json({ok:true});
});
app.post('/api/projects/:id/proposals/:proposal/action',owned,entitled,async(req,res)=>{
 const proposal=uuid(req.params.proposal),action=req.body.action;
 if(!req.project.enabled)throw Error('Project paused');
 await tx(pool,async c=>{
   const row=await one(c,'SELECT * FROM proposals WHERE id=$1 AND project_id=$2 FOR UPDATE',[proposal,req.project.id]);
   if(!row)throw Error('Proposal not found');
   if(action==='reject'&&row.status==='proposed')await c.query("UPDATE proposals SET status='rejected' WHERE id=$1",[proposal]);
   else if(action==='approve'&&['proposed','approved'].includes(row.status)){
     await c.query("UPDATE proposals SET status='approved' WHERE id=$1",[proposal]);
     const dedupe='open-pr:'+proposal;
     const old=await one(c,'SELECT * FROM jobs WHERE dedupe=$1',[dedupe]);
     if(old?.status==='failed'&&old.attempts<3)await c.query("UPDATE jobs SET status='queued',error=NULL,updated_at=now() WHERE id=$1",[old.id]);
     else if(old?.status==='failed')throw Error('Retry limit reached');
     else if(!old)await enqueue(c,req.project.id,'open_pr',dedupe,{proposalId:proposal});
   }else if(action==='merge'&&row.status==='pr_opened'&&cfg.autoMerge&&row.verification?.ready){
     await c.query("UPDATE proposals SET status='merge_queued' WHERE id=$1",[proposal]);
     await enqueue(c,req.project.id,'merge','merge:'+proposal+':'+randomUUID(),{proposalId:proposal,head:row.verification.head});
   }else if(action==='rollback'&&row.status==='merged'){
     await enqueue(c,req.project.id,'rollback','rollback:'+proposal,{proposalId:proposal});
   }else throw Error('Action not available');
   await audit(c,req.account.id,req.project.id,'proposal_'+action,{proposal});
 });res.json({ok:true});
});
app.use(express.static(fileURLToPath(new URL('./public/',import.meta.url)),{index:'index.html',dotfiles:'deny'}));
app.use((req,res)=>res.status(404).json({error:'Not found'}));
app.use((err,req,res,next)=>{
 console.error('Request failed:',err.code||err.status||'request_error');
 if(res.headersSent)return next(err);
 res.status(400).json({error:err.code?'Request could not be completed':String(err.message||'Request failed').slice(0,300)});
});
app.listen(cfg.port,process.env.BIND_HOST||(cfg.secure?'0.0.0.0':'127.0.0.1'),()=>console.log('Resilyne web listening on '+cfg.port));
