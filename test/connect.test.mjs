import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,mkdir,symlink,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {localScan,readiness,repositoryScan} from '../connect/scan.mjs';
import {makeClient} from '../connect/client.mjs';
import {validateTelemetry} from '../connect/telemetry.mjs';
test('local scan is read-only, ignores dependencies and symlinks, and returns no source or secret values',async()=>{
 const root=await mkdtemp(join(tmpdir(),'resilyne-scan-'));
 try{
  await mkdir(join(root,'test'));await mkdir(join(root,'node_modules'));
  await writeFile(join(root,'package.json'),JSON.stringify({scripts:{test:'DO_NOT_RUN_ME'},secret:'DO_NOT_DISCLOSE'}));
  await writeFile(join(root,'test','cart.test.js'),'throw Error("DO_NOT_RUN_ME")');
  await writeFile(join(root,'.env'),'SECRET=DO_NOT_DISCLOSE');
  await writeFile(join(root,'package-lock.json'),'{}');
  await writeFile(join(root,'node_modules','.env'),'ignored');
  await symlink('/etc/passwd',join(root,'link.js'));
  const r=await localScan(root);
  assert.equal(r.filesExamined,4);assert.equal(r.checks.find(x=>x.id==='tests').state,'pass');
  assert.equal(r.checks.find(x=>x.id==='env').state,'attention');
  assert.equal(JSON.stringify(r).includes('DO_NOT'),false);
 }finally{await rm(root,{recursive:true,force:true});}
});
test('truncation and missing signals do not fabricate healthy status',()=>{
 const r=readiness({paths:[],truncated:true});assert.equal(r.checks.find(x=>x.id==='env').state,'unknown');assert.equal(r.checks.find(x=>x.id==='security').state,'unknown');
});
test('repository scan is pinned to revision and rejects stale CI data',async()=>{
 const g={head:async()=>({object:{sha:'new'}}),request:async p=>p.startsWith('/commits/')?{commit:{tree:{sha:'tree'}}}:{tree:[{path:'package.json',type:'blob',mode:'100644'}]},file:async(p,sha)=>{assert.equal(sha,'new');return {text:'{}'};}};
 const r=await repositoryScan(g,{base_branch:'main',scan_result:{ci:{sha:'old',conclusion:'success'}}});
 assert.equal(r.revision,'new');assert.equal(r.checks.find(x=>x.id==='workflow').state,'unknown');
});
test('connect client uses a scoped bearer and refuses insecure remote origin',async()=>{
 const token='rsl_'+'a'.repeat(43);assert.throws(()=>makeClient({origin:'http://example.com',token}));
 const c=makeClient({origin:'https://example.com',token,fetcher:async(url,opts)=>{assert.equal(url,'https://example.com/connect/v1/status');assert.equal(opts.headers.Authorization,'Bearer '+token);assert.equal(opts.redirect,'error');return {ok:true,json:async()=>({ok:true})};}});
 assert.deepEqual(await c.status(),{ok:true});
});
test('telemetry accepts bounded counters, rejects payloads and negative costs',()=>{
 assert.equal(validateTelemetry({kind:'usage',service:'openai',units:'tokens',quantity:100,costMicrosUsd:2}).cost,2);
 for(const x of [{kind:'error',code:'E1',count:1,stack:'secret'},{kind:'usage',service:'x',units:'tokens',quantity:1,costMicrosUsd:-1},{kind:'heartbeat',email:'private@example.com'},{kind:'error',code:'abc',count:0}])assert.throws(()=>validateTelemetry(x));
});
