import http from 'node:http';
import { readFile, mkdir, writeFile, rename } from 'node:fs/promises';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { GitHub } from './lib/github.mjs';
import { upsertIncident } from './lib/core.mjs';
import { propose } from './lib/repair.mjs';

const env=process.env, port=Number(env.PORT||3000), origin='http://127.0.0.1:'+port;
const token=randomBytes(32).toString('hex');
const repo=env.GITHUB_REPO||'';
const github=repo?new GitHub(repo,env.GITHUB_TOKEN):null;
const config={apiKey:env.OPENAI_API_KEY,model:env.OPENAI_MODEL||'gpt-4.1-mini'};
const dir=new URL('./.data/',import.meta.url), db=new URL('state.json',dir);
await mkdir(dir,{recursive:true,mode:0o700});
let state={incidents:[],proposals:[],lastScan:null,monitorError:null,health:null,ci:null};
try{state=JSON.parse(await readFile(db,'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
const stateRepo=repo||null;
if(state.repository!==undefined&&state.repository!==stateRepo)throw Error('Existing data belongs to another repository. Move .data aside before switching.');
state.repository=stateRepo;
async function save(){const temp=new URL('state.tmp',dir);await writeFile(temp,JSON.stringify(state,null,2),{mode:0o600});await rename(temp,db);}
let pending=false;
async function exclusive(fn){if(pending)throw Error('Another operation is running');pending=true;try{return await fn();}finally{pending=false;}}
async function scan(){
  return exclusive(async()=>{
    const errors=[];
    if(github&&env.GITHUB_TOKEN){
      try{
        const meta=await github.metadata(), data=await github.runs(meta.default_branch);
        const latest=new Map();
        for(const run of data.workflow_runs||[])if(!latest.has(run.workflow_id))latest.set(run.workflow_id,run);
        state.ci=[...latest.values()].map(r=>({name:r.name,status:r.status,conclusion:r.conclusion,url:r.html_url,updatedAt:r.updated_at}));
        for(const run of latest.values()){
          
          if(['failure','timed_out','action_required'].includes(run.conclusion)){
            const incident=upsertIncident(state,'ci',String(run.id)+':'+run.run_attempt,{title:'CI failed: '+run.name,detail:'Workflow '+run.name+' concluded '+run.conclusion+' at commit '+run.head_sha+'. Inspect the linked run for details.',workflowId:run.workflow_id,url:run.html_url});
            for(const i of state.incidents)if(i.kind==='ci'&&i.workflowId===run.workflow_id&&i.status==='open'&&i.id!==incident.id)i.status='superseded';
          }else if(run.conclusion==='success'){
            for(const i of state.incidents)if(i.kind==='ci'&&i.workflowId===run.workflow_id&&i.status==='open')i.status='recovered';
          }
        }
      }catch(e){errors.push(e.message);}
    }else errors.push('GitHub not configured');
    if(env.HEALTH_URL){
      try{
        const url=new URL(env.HEALTH_URL);
        if(url.protocol!=='https:'||url.username||url.password)throw Error('HEALTH_URL must be trusted HTTPS');
        const start=Date.now(), response=await fetch(url,{redirect:'error',signal:AbortSignal.timeout(10000)});
        await response.body?.cancel();
        state.health={ok:response.ok,status:response.status,latency:Date.now()-start,at:new Date().toISOString()};
        if(!response.ok)throw Error('Health endpoint returned '+response.status);
        for(const i of state.incidents)if(i.kind==='health'&&i.status==='open')i.status='recovered';
      }catch(e){
        state.health={ok:false,at:new Date().toISOString()};
        const active=state.incidents.find(i=>i.kind==='health'&&i.status==='open');
        const key=active?.key||new Date().toISOString();
        upsertIncident(state,'health',key,{key,title:'Application health check failed',detail:e.message});
      }
    }
    state.lastScan=new Date().toISOString();state.monitorError=errors.join('; ')||null;await save();
  });
}
const page=await readFile(new URL('./public/index.html',import.meta.url),'utf8');
function send(res,status,body,type='application/json'){res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"});res.end(type==='application/json'?JSON.stringify(body):body);}
async function body(req){let value='';for await(const chunk of req){value+=chunk;if(value.length>8192)throw Error('Request too large');}return JSON.parse(value||'{}');}
function authorized(req){const supplied=Buffer.from(String(req.headers['x-resilyne-token']||''));const expected=Buffer.from(token);return supplied.length===expected.length&&timingSafeEqual(supplied,expected);}
const server=http.createServer(async(req,res)=>{
  try{
    if(req.headers.host!=='127.0.0.1:'+port){send(res,403,{error:'Use the local address'});return;}
    if(req.method==='GET'&&req.url==='/'){send(res,200,page.replace('__LOCAL_TOKEN__',token),'text/html; charset=utf-8');return;}
    if(!authorized(req)){send(res,403,{error:'Unauthorized'});return;}
    if(req.method==='GET'&&req.url==='/api/state'){send(res,200,{...state,busy:pending,configured:!!(github&&env.GITHUB_TOKEN),aiConfigured:!!config.apiKey});return;}
    if(req.method!=='POST'||req.headers.origin!==origin){send(res,403,{error:'Invalid origin or method'});return;}
    const data=await body(req);
    if(req.url==='/api/scan')await scan();
    else if(req.url==='/api/propose')await exclusive(async()=>{
      if(!github)throw Error('GitHub not configured');
      const incident=state.incidents.find(i=>i.id===data.incidentId&&i.status==='open');
      if(!incident)throw Error('Open incident not found');
      const p=await propose(github,incident,data.path,config);state.proposals.unshift(p);await save();
    });
    else if(req.url==='/api/approve')await exclusive(async()=>{
      const p=state.proposals.find(p=>p.id===data.id&&p.status==='proposed');
      if(!p||!github)throw Error('Pending proposal not found');
      const pr=await github.openRepair(p);p.status='pr_opened';p.prUrl=pr.html_url;await save();
    });
    else if(req.url==='/api/reject')await exclusive(async()=>{
      const p=state.proposals.find(p=>p.id===data.id&&p.status==='proposed');
      if(!p)throw Error('Pending proposal not found');p.status='rejected';await save();
    });
    else {send(res,404,{error:'Not found'});return;}
    send(res,200,{ok:true});
  }catch(e){send(res,400,{error:e.message});}
});
server.listen(port,'127.0.0.1',()=>console.log('Resilyne pilot: '+origin));
const interval=Math.max(60,Number(env.POLL_SECONDS)||300)*1000;
setInterval(()=>{if(!pending)scan().catch(console.error);},interval).unref();
scan().catch(console.error);
