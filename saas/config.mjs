import {createHash,createHmac,randomBytes,timingSafeEqual} from 'node:crypto';
export const sha=value=>createHash('sha256').update(value).digest('hex');
export const nonce=()=>randomBytes(32).toString('base64url');
export function equal(a,b){const x=Buffer.from(String(a??'')),y=Buffer.from(String(b??''));return x.length===y.length&&timingSafeEqual(x,y);}
export function signature(secret,raw){return 'sha256='+createHmac('sha256',secret).update(raw).digest('hex');}
export function verifySignature(secret,raw,value){return !!secret&&equal(signature(secret,raw),value);}
export function parseCookies(header=''){return Object.fromEntries(header.split(';').map(x=>x.trim().split(/=(.*)/s)).filter(x=>x.length>1).map(([k,v])=>[k,v]));}
export function allowedEndpoint(value,allowlist){if(!value)return null;const u=new URL(value);if(u.protocol!=='https:'||u.username||u.password||u.hash||!allowlist.includes(u.href))throw Error('Endpoint must be an exact administrator-approved HTTPS URL');return u.href;}
export function positiveId(value){const s=String(value);if(!/^[1-9]\d{0,17}$/.test(s))throw Error('Invalid numeric ID');return s;}
export function uuid(value){if(typeof value!=='string'||!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value))throw Error('Invalid identifier');return value;}
export function billable(status,required){return !required||['active','trialing'].includes(status);}
export function verificationGate(pr,workflow,run,head,expectedRepo,expectedBase){
 return pr.state==='open'&&!pr.draft&&pr.mergeable===true&&pr.head.sha===head&&pr.base.repo.full_name===expectedRepo&&pr.base.ref===expectedBase&&pr.head.repo?.full_name===expectedRepo&&run?.head_repository?.full_name===expectedRepo&&run?.head_branch===pr.head.ref&&['push','pull_request'].includes(run?.event)&&String(run?.workflow_id)===String(workflow)&&run?.head_sha===head&&run?.status==='completed'&&run?.conclusion==='success';
}
export function config(env=process.env){
 const origin=new URL(env.PUBLIC_ORIGIN||'http://localhost:3000');
 if(origin.pathname!=='/'||origin.search||origin.hash||origin.username||origin.password||!(origin.protocol==='https:'||(origin.protocol==='http:'&&['localhost','127.0.0.1'].includes(origin.hostname))))throw Error('PUBLIC_ORIGIN must be an HTTPS origin or localhost');
 const required=['DATABASE_URL','GITHUB_APP_ID','GITHUB_APP_PRIVATE_KEY','GITHUB_CLIENT_ID','GITHUB_CLIENT_SECRET','GITHUB_WEBHOOK_SECRET'];
 for(const k of required)if(!env[k])throw Error('Missing '+k);
 if(env.BILLING_REQUIRED==='true'&&(!env.STRIPE_SECRET_KEY||!env.STRIPE_WEBHOOK_SECRET||!env.STRIPE_PRICE_ID))throw Error('Billing required but Stripe is incomplete');
 return {origin:origin.origin,secure:origin.protocol==='https:',port:Number(env.PORT||3000),db:env.DATABASE_URL,appId:positiveId(env.GITHUB_APP_ID),privateKey:env.GITHUB_APP_PRIVATE_KEY.replace(/\\n/g,'\n'),clientId:env.GITHUB_CLIENT_ID,clientSecret:env.GITHUB_CLIENT_SECRET,webhookSecret:env.GITHUB_WEBHOOK_SECRET,appSlug:env.GITHUB_APP_SLUG||'',apiKey:env.OPENAI_API_KEY,model:env.OPENAI_MODEL||'gpt-4.1-mini',stripeKey:env.STRIPE_SECRET_KEY,stripeWebhook:env.STRIPE_WEBHOOK_SECRET,priceId:env.STRIPE_PRICE_ID,billingRequired:env.BILLING_REQUIRED==='true',allowlist:(env.HEALTH_ALLOWLIST||'').split(',').map(x=>x.trim()).filter(Boolean),maxProjects:Math.min(20,Math.max(1,Number(env.MAX_PROJECTS_PER_ACCOUNT)||3)),maxDailyAI:Math.min(50,Math.max(1,Number(env.MAX_DAILY_AI_JOBS)||5)),autoMerge:env.ENABLE_APPROVED_MERGE==='true'};
}
