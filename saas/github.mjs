import {createSign} from 'node:crypto';
import {GitHub} from '../lib/github.mjs';
import {positiveId} from './config.mjs';
const api='https://api.github.com';
export async function apiRequest(path,token,method='GET',body){
 const r=await fetch(api+path,{method,headers:{Authorization:'Bearer '+token,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Resilyne','Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),redirect:'error',signal:AbortSignal.timeout(20000)});
 if(!r.ok){const e=Error('GitHub API '+r.status);e.status=r.status;throw e;}return r.status===204?null:r.json();
}
export function appJWT(cfg,now=Math.floor(Date.now()/1000)){
 const enc=x=>Buffer.from(JSON.stringify(x)).toString('base64url');
 const data=enc({alg:'RS256',typ:'JWT'})+'.'+enc({iat:now-60,exp:now+540,iss:cfg.appId});
 return data+'.'+createSign('RSA-SHA256').update(data).end().sign(cfg.privateKey,'base64url');
}
export async function oauthUser(cfg,code){
 const r=await fetch('https://github.com/login/oauth/access_token',{method:'POST',headers:{Accept:'application/json','Content-Type':'application/json'},body:JSON.stringify({client_id:cfg.clientId,client_secret:cfg.clientSecret,code,redirect_uri:cfg.origin+'/auth/callback'}),signal:AbortSignal.timeout(20000),redirect:'error'});
 const data=await r.json();if(!r.ok||!data.access_token)throw Error('GitHub authorization failed');
 return apiRequest('/user',data.access_token);
}
export async function verifyInstallation(cfg,account,installation){
 const i=await apiRequest('/app/installations/'+positiveId(installation),appJWT(cfg));
 if(i.suspended_at||i.account?.type!=='User'||String(i.account?.id)!==String(account))throw Error('Only active personal GitHub installations owned by this account are supported');
 return i;
}
export async function installationToken(cfg,installation,repository){
 const data=await apiRequest('/app/installations/'+positiveId(installation)+'/access_tokens',appJWT(cfg),'POST',{repository_ids:[Number(positiveId(repository))]});
 return data.token;
}
export async function connectRepo(cfg,account,installation,repo,workflow){
 await verifyInstallation(cfg,account,installation);
 const token=await installationToken(cfg,installation,repo);
 const meta=await apiRequest('/repositories/'+positiveId(repo),token);
 if(String(meta.id)!==String(repo)||String(meta.owner?.id)!==String(account)||meta.archived||meta.disabled)throw Error('Repository is not an active personal repository owned by this account');
 const github=new GitHub(meta.full_name,token);
 const flow=await github.request('/actions/workflows/'+positiveId(workflow));
 if(flow.state!=='active')throw Error('Selected workflow is not active');
 return {repo:meta.full_name,branch:meta.default_branch,workflow:flow.id};
}
export async function projectGitHub(cfg,p){
 await verifyInstallation(cfg,p.account_id,p.installation_id);
 const token=await installationToken(cfg,p.installation_id,p.repository_id);
 const meta=await apiRequest('/repositories/'+positiveId(p.repository_id),token);
 if(String(meta.owner?.id)!==String(p.account_id)||meta.full_name!==p.repo||meta.default_branch!==p.base_branch||meta.archived||meta.disabled)throw Error('Repository ownership, name or default branch changed; reconnect before continuing');
 return new GitHub(p.repo,token);
}
export async function alerts(github){
 try{return {available:true,items:await github.request('/dependabot/alerts?state=open&per_page=100')};}
 catch(e){if(/GitHub (403|404)/.test(e.message))return {available:false,items:[]};throw e;}
}
export async function deployment(github){
 const list=await github.request('/deployments?per_page=1');
 if(!list.length)return null;
 const d=list[0],states=await github.request('/deployments/'+positiveId(d.id)+'/statuses?per_page=1');
 return {environment:d.environment,sha:d.sha,state:states[0]?.state||'unknown',createdAt:d.created_at};
}
export async function verification(github,number,workflow){
 const pr=await github.request('/pulls/'+positiveId(number));
 const result=await github.request('/actions/workflows/'+positiveId(workflow)+'/runs?head_sha='+encodeURIComponent(pr.head.sha)+'&per_page=10');
 const run=result.workflow_runs?.[0];
 return {pr,run,head:pr.head.sha};
}
