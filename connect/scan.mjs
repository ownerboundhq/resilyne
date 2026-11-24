import {readdir,lstat,realpath,open} from 'node:fs/promises';
import {constants} from 'node:fs';
import {resolve,join,relative,sep} from 'node:path';
const ignored=new Set(['.git','node_modules','dist','build','.next','coverage','.turbo','.cache','.data','vendor']);
const testName=/(?:^|\/)(?:test|tests|__tests__)(?:\/|$)|\.(?:test|spec)\.[cm]?[jt]sx?$/i;
const locks=['package-lock.json','pnpm-lock.yaml','yarn.lock','bun.lock','bun.lockb'];
const check=(id,title,state,detail)=>({id,title,state,detail});
export function readiness({paths,manifest,manifestState='unknown',truncated=false,ci=null,security=null,health=null}){
 const p=new Set(paths),has=(re)=>paths.some(x=>re.test(x));
 const checks=[
 check('manifest','Node project manifest',manifestState==='ok'?'pass':manifestState==='missing'&&!truncated?'attention':'unknown',manifestState==='ok'?'Root package.json is readable.':'Root package.json missing, unreadable or not assessed.'),
 check('lock','Dependency lockfile',locks.some(x=>p.has(x))?'pass':truncated?'unknown':'attention','A committed lockfile helps reproduce installs.'),
 check('tests','Test setup',manifest?.scripts?.test&&has(testName)?'pass':truncated?'unknown':'attention','Checks for a test script and conventional test files; does not execute tests.'),
 check('ci','CI configuration',has(/^\.github\/workflows\/[^/]+\.ya?ml$/)?'pass':truncated?'unknown':'attention','Checks for GitHub workflow files, not their correctness.'),
 check('ignore','Git ignore file',p.has('.gitignore')?'pass':truncated?'unknown':'attention','Review secret and build-output exclusions separately.'),
 check('env','Potential environment files',has(/(?:^|\/)\.env(?:\.(?!example$|sample$|template$)[^/]+)?$/)?'attention':truncated?'unknown':'pass','Checks filenames only; no secret contents read. Local files may be intentionally ignored.'),
 check('workflow','Latest selected CI result',ci?.conclusion==='success'?'pass':ci?.conclusion==='failure'||ci?.conclusion==='timed_out'?'attention':'unknown',ci?.conclusion||'No completed selected CI result supplied.'),
 check('security','Dependency alerts',security?.available?(security.open===0?'pass':'attention'):'unknown',security?.available?String(security.open)+' open alerts (may be incomplete)':'No provider alert data available.'),
 check('health','HTTP health probe',health?.ok===true?'pass':health?.ok===false?'attention':'unknown',health?.ok===true?'Last configured probe passed.':health?.ok===false?'Last configured probe failed.':'No configured probe result.')
 ];
 return {version:1,generatedAt:new Date().toISOString(),checks,counts:Object.fromEntries(['pass','attention','unknown'].map(s=>[s,checks.filter(c=>c.state===s).length])),truncated,scope:'Readiness indicators only. Not a security audit, runtime test or reliability guarantee.'};
}
export async function localScan(root,{maxEntries=8000}={}){
 const base=await realpath(resolve(root)),paths=[];let truncated=false,manifest=null,manifestState='unknown',visited=0;
 async function walk(dir,depth){
  if(depth>15){truncated=true;return;}
  let entries;try{entries=await readdir(dir,{withFileTypes:true});}catch{truncated=true;return;}
  for(const item of entries){
   if(++visited>maxEntries){truncated=true;return;}
   if(ignored.has(item.name)||item.isSymbolicLink())continue;
   const path=join(dir,item.name),rel=relative(base,path).split(sep).join('/');
   if(item.isDirectory())await walk(path,depth+1);else if(item.isFile())paths.push(rel);
   if(visited>maxEntries)return;
  }
 }
 await walk(base,0);
 const target=join(base,'package.json');
 try{const info=await lstat(target);if(info.isFile()&&!info.isSymbolicLink()&&info.size<=100000){
   const f=await open(target,constants.O_RDONLY|(constants.O_NOFOLLOW||0));try{const stat=await f.stat();if(stat.size>100000||!stat.isFile())throw Error('Invalid manifest');const buf=Buffer.alloc(100001);const {bytesRead}=await f.read(buf,0,buf.length,0);if(bytesRead>100000)throw Error('Manifest too large');manifest=JSON.parse(buf.subarray(0,bytesRead).toString('utf8'));manifestState='ok';}finally{await f.close();}
 }}catch(e){if(e.code==='ENOENT')manifestState='missing';}
 return {...readiness({paths,manifest,manifestState,truncated}),source:'local',filesExamined:paths.length};
}
export async function repositoryScan(github,project){
 const sha=(await github.head(project.base_branch)).object.sha;
 const commit=await github.request('/commits/'+sha),tree=await github.request('/git/trees/'+commit.commit.tree.sha+'?recursive=1');
 const paths=(tree.tree||[]).filter(e=>e.type==='blob'&&e.mode!=='120000').map(e=>e.path);
 let manifest,manifestState='unknown';
 if(!paths.includes('package.json'))manifestState=tree.truncated?'unknown':'missing';
 else try{manifest=JSON.parse((await github.file('package.json',sha)).text);manifestState='ok';}catch{}
 const signals=project.scan_result||{};
 const ci=signals.ci?.sha===sha?signals.ci:null;
 return {...readiness({paths,manifest,manifestState,truncated:!!tree.truncated,ci,security:signals.security,health:signals.health}),source:'github',revision:sha,signalObservedAt:project.last_scan||null,filesExamined:paths.length};
}
