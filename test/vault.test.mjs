import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm,stat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {backup} from '../connect/vault.mjs';
test('Vault creates a verified bundle of committed Git history',{timeout:20000},async()=>{
 const tmp=await mkdtemp(join(tmpdir(),'resilyne-vault-')),repo=join(tmp,'repo'),dest=join(tmp,'backups');
 try{
  await mkdir(repo);
  const git=(...args)=>execFileSync('git',['-C',repo,...args],{stdio:'pipe'});
  git('init');await writeFile(join(repo,'app.js'),'export const value=1;');
  git('add','app.js');git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','initial');
  await assert.rejects(backup(repo,join(repo,'backup')),/outside/);
  const b=await backup(repo,dest);assert.ok((await stat(b.path)).size>0);git('bundle','verify',b.path);
 }finally{await rm(tmp,{recursive:true,force:true});}
});
