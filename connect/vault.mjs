import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {realpath,lstat,mkdir,chmod,unlink} from 'node:fs/promises';
import {resolve,join,relative,isAbsolute,sep} from 'node:path';
import {pathToFileURL} from 'node:url';
import {randomUUID} from 'node:crypto';
const exec=promisify(execFile);
export async function backup(root,destination){
 const base=await realpath(resolve(root)),out=resolve(destination);
 await mkdir(out,{recursive:true,mode:0o700});
 const target=await realpath(out),rel=relative(base,target);
 if(!rel||(rel!=='..'&&!rel.startsWith('..'+sep)&&!isAbsolute(rel)))throw Error('Backup destination must be outside the repository');
 const {stdout:top}=await exec('git',['-C',base,'rev-parse','--show-toplevel'],{timeout:10000});
 if(await realpath(top.trim())!==base)throw Error('Select the repository root');
 const name='resilyne-'+new Date().toISOString().replace(/[:.]/g,'-')+'-'+randomUUID()+'.bundle',path=join(target,name);
 try{
  await exec('git',['-C',base,'bundle','create',path,'--all'],{timeout:120000,maxBuffer:1024*1024});
  await chmod(path,0o600);
  await exec('git',['-C',base,'bundle','verify',path],{timeout:30000,maxBuffer:1024*1024});
  const info=await lstat(path);return {path,bytes:info.size,scope:'Git commits and refs only. No uncommitted files, external LFS objects, databases or cloud state.'};
 }catch(e){await unlink(path).catch(()=>{});throw e;}
}
if(process.argv[1]&&pathToFileURL(resolve(process.argv[1])).href===import.meta.url){
 if(!process.env.RESILYNE_VAULT_DIR){console.error('Set RESILYNE_VAULT_DIR to a private directory outside the repository');process.exitCode=1;}
 else try{console.log(JSON.stringify(await backup(process.env.RESILYNE_PROJECT_ROOT||process.cwd(),process.env.RESILYNE_VAULT_DIR),null,2));}catch(e){console.error('Backup failed: '+e.message);process.exitCode=1;}
}
