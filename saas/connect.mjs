import {randomUUID} from 'node:crypto';
import {nonce,sha,uuid,billable} from './config.mjs';
import {one,tx,enqueue,audit} from './db.mjs';
import {validateTelemetry} from '../connect/telemetry.mjs';
export async function usageSummary(db,projectId){
 const rows=(await db.query("SELECT day,kind,label,unit,quantity,cost_micros_usd,priced_events,events,updated_at FROM telemetry_daily WHERE project_id=$1 AND day>=CURRENT_DATE-6 ORDER BY day DESC,kind,label LIMIT 300",[projectId])).rows;
 return {windowDays:7,rows,limit:300,scope:'Customer-reported aggregates, not reconciled provider invoices. Cost is reported in millionths of USD; missing costs are not zero.',mayBeTruncated:rows.length===300};
}
export function mountConnect(app,pool,cfg){
 // Machine credentials are separate from browser sessions and restricted to a single project.
 app.use('/connect/v1',async(req,res,next)=>{
  const raw=req.get('authorization')||'';
  if(!/^Bearer rsl_[A-Za-z0-9_-]{43}$/.test(raw)||req.get('origin'))return res.status(401).json({error:'Machine credential required'});
  const token=await one(pool,"SELECT t.id AS token_id,t.scope,p.*,a.billing_status FROM connect_tokens t JOIN projects p ON p.id=t.project_id JOIN accounts a ON a.id=p.account_id WHERE t.token_hash=$1 AND t.revoked_at IS NULL AND t.expires_at>now()",[sha(raw.slice(7))]);
  if(!token||!token.enabled)return res.status(401).json({error:'Credential invalid, expired or project paused'});
  req.connected=token;next();
 });
 function scope(name){return (req,res,next)=>req.connected.scope===name?next():res.status(403).json({error:'Insufficient scope'});}
 app.get('/connect/v1/status',scope('agent'),async(req,res)=>{
  const p=req.connected,r=p.scan_result||{};
  res.json({project:p.repo,branch:p.base_branch,enabled:p.enabled,lastScan:p.last_scan,ci:r.ci||null,health:r.health||null,security:r.security||null,reportAvailable:!!p.readiness_report,billing:p.billing_status});
 });
 app.get('/connect/v1/report',scope('agent'),(req,res)=>res.json({report:req.connected.readiness_report||null}));
 app.get('/connect/v1/incidents',scope('agent'),async(req,res)=>{
  const rows=(await pool.query('SELECT id,kind,status,first_seen,last_seen FROM incidents WHERE project_id=$1 ORDER BY last_seen DESC LIMIT 50',[req.connected.id])).rows;
  res.json({incidents:rows});
 });
 app.get('/connect/v1/repairs',scope('agent'),async(req,res)=>{
  const rows=(await pool.query('SELECT id,incident_id,status,pr_url,verification,created_at FROM proposals WHERE project_id=$1 ORDER BY created_at DESC LIMIT 30',[req.connected.id])).rows;
  res.json({repairs:rows.map(({verification,...p})=>({...p,verification:verification?{ready:verification.ready,conclusion:verification.conclusion}:null}))});
 });
 app.post('/connect/v1/scan',scope('agent'),async(req,res)=>{
  const p=req.connected;
  const result=await enqueue(pool,p.id,'readiness','readiness:'+p.id+':'+Math.floor(Date.now()/3600000));
  res.json({queued:!!result,jobId:result?.id||null,limit:'One repository readiness scan per project per hour'});
 });
 app.post('/connect/v1/telemetry',scope('telemetry'),async(req,res)=>{
  const p=req.connected;
  if(!billable(p.billing_status,cfg.billingRequired))return res.status(402).json({error:'Subscription required'});
  const event=validateTelemetry(req.body);
  await tx(pool,async c=>{
   const q=await one(c,"INSERT INTO telemetry_quota(project_id,day,events) VALUES($1,CURRENT_DATE,1) ON CONFLICT(project_id,day) DO UPDATE SET events=telemetry_quota.events+1 WHERE telemetry_quota.events<1000 RETURNING events",[p.id]);
   if(!q)throw Error('Daily telemetry event limit reached');
   await c.query("INSERT INTO telemetry_daily(project_id,day,kind,label,unit,quantity,cost_micros_usd,priced_events,events) VALUES($1,CURRENT_DATE,$2,$3,$4,$5,$6,$7,1) ON CONFLICT(project_id,day,kind,label,unit) DO UPDATE SET quantity=telemetry_daily.quantity+excluded.quantity,cost_micros_usd=telemetry_daily.cost_micros_usd+excluded.cost_micros_usd,priced_events=telemetry_daily.priced_events+excluded.priced_events,events=telemetry_daily.events+1,updated_at=now()",[p.id,event.kind,event.label,event.unit,event.quantity,event.cost??0,event.cost===null?0:1]);
  });
  res.json({accepted:true});
 });
}
export function mountConnectDashboard(app,pool,owned){
 app.get('/api/projects/:id/connect',owned,async(req,res)=>{
  const tokens=(await pool.query('SELECT id,label,scope,created_at,expires_at,revoked_at FROM connect_tokens WHERE project_id=$1 ORDER BY created_at DESC LIMIT 50',[req.project.id])).rows;
  res.json({tokens,report:req.project.readiness_report||null,telemetry:await usageSummary(pool,req.project.id)});
 });
 app.post('/api/projects/:id/connect/token',owned,async(req,res)=>{
  const {scope,label}=req.body;if(!['agent','telemetry'].includes(scope)||typeof label!=='string'||!label.trim()||label.length>60)throw Error('Choose a valid credential label and scope');
  const token='rsl_'+nonce(),id=randomUUID();
  await tx(pool,async c=>{
   await one(c,'SELECT id FROM projects WHERE id=$1 FOR UPDATE',[req.project.id]);
   const n=await one(c,'SELECT count(*)::int AS n FROM connect_tokens WHERE project_id=$1 AND revoked_at IS NULL AND expires_at>now()',[req.project.id]);if(n.n>=10)throw Error('Active credential limit reached');
   await c.query("INSERT INTO connect_tokens(id,project_id,token_hash,label,scope,expires_at) VALUES($1,$2,$3,$4,$5,now()+interval '30 days')",[id,req.project.id,sha(token),label.trim(),scope]);
   await audit(c,req.account.id,req.project.id,'connect_token_created',{id,scope});
  });
  res.status(201).json({id,token,scope,expiresInDays:30});
 });
 app.post('/api/projects/:id/connect/revoke',owned,async(req,res)=>{
  const id=uuid(req.body.tokenId);
  await tx(pool,async c=>{
   const changed=await one(c,'UPDATE connect_tokens SET revoked_at=now() WHERE id=$1 AND project_id=$2 AND revoked_at IS NULL RETURNING id',[id,req.project.id]);if(!changed)throw Error('Active credential not found');
   await audit(c,req.account.id,req.project.id,'connect_token_revoked',{id});
  });res.json({ok:true});
 });
 app.post('/api/projects/:id/readiness',owned,async(req,res)=>{
  if(!req.project.enabled)throw Error('Project paused');
  const result=await enqueue(pool,req.project.id,'readiness','readiness:'+req.project.id+':'+Math.floor(Date.now()/3600000));
  res.json({queued:!!result,jobId:result?.id||null});
 });
}
