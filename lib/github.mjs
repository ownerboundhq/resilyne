import { repoName, gitPath } from './core.mjs';
export class GitHub {
  constructor(repo,token) { this.repo=repoName(repo); this.token=token; }
  async request(path, method='GET', body) {
    if (!this.token) throw Error('GITHUB_TOKEN is not configured');
    const response=await fetch('https://api.github.com/repos/'+this.repo+path,{
      method, headers:{Authorization:'Bearer '+this.token,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Resilyne/0.1','Content-Type':'application/json'},
      body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(20000),redirect:'error'
    });
    if(!response.ok) throw Error('GitHub '+response.status+' for '+method+' '+path.split('?')[0]);
    return response.json();
  }
  metadata(){return this.request('');}
  runs(branch){return this.request('/actions/runs?per_page=30&branch='+encodeURIComponent(branch));}
  head(branch){return this.request('/git/ref/heads/'+gitPath(branch));}
  async file(path,ref){
    const data=await this.request('/contents/'+gitPath(path)+'?ref='+encodeURIComponent(ref));
    if(data.type!=='file'||data.encoding!=='base64'||data.size>60000) throw Error('Unsupported file or file exceeds 60 KB');
    return {sha:data.sha,text:Buffer.from(data.content,'base64').toString('utf8')};
  }
  async openRepair(p){
    const branch='resilyne/repair-'+p.id;
    // Deterministic branch and PR identity make retries after interruptions safe.
    const existing=await this.request('/pulls?state=all&head='+encodeURIComponent(this.repo.split('/')[0]+':'+branch));
    if(existing.length){
      const pr=existing[0];
      if(pr.head?.repo?.full_name!==this.repo||pr.base?.ref!==p.baseBranch||pr.head?.ref!==branch)throw Error('Existing repair PR has unexpected refs');
      const diff=await this.request('/compare/'+p.baseSha+'...'+pr.head.sha);
      if(diff.files?.length!==1||diff.files[0].filename!==p.path||(await this.file(p.path,pr.head.sha)).text!==p.replacement)throw Error('Existing repair PR differs from proposal');
      return pr;
    }
    const current=(await this.head(p.baseBranch)).object.sha;
    if(current!==p.baseSha) throw Error('Base branch changed. Generate a new proposal.');
    let ref;
    try{ref=await this.head(branch);}catch(e){
      if(!e.message.startsWith('GitHub 404')) throw e;
      ref=await this.request('/git/refs','POST',{ref:'refs/heads/'+branch,sha:p.baseSha});
    }
    const file=await this.file(p.path,branch);
    if(file.text!==p.replacement){
      if(ref.object.sha!==p.baseSha||file.sha!==p.blobSha) throw Error('Repair branch contains unexpected changes');
      await this.request('/contents/'+gitPath(p.path),'PUT',{message:'Resilyne: proposed repair',content:Buffer.from(p.replacement).toString('base64'),sha:file.sha,branch});
    } else {
      const comparison=await this.request('/compare/'+p.baseSha+'...'+ref.object.sha);
      if(comparison.files?.length!==1||comparison.files[0].filename!==p.path) throw Error('Repair branch contains unexpected changes');
    }
    return this.request('/pulls','POST',{title:'Resilyne: proposed software repair',head:branch,base:p.baseBranch,draft:true,body:'AI-generated proposal, approved for opening this draft PR only. Review the diff and run the application test suite before merging.\n\n'+p.summary+'\n\nIncident: '+p.incidentId});
  }
}
