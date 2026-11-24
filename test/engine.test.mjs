import test from 'node:test';
import assert from 'node:assert/strict';
import {eligible,selectCandidates,investigate,validateDecision} from '../engine/diagnose.mjs';
import {canDraft,retryEligible,exactRun} from '../engine/policy.mjs';
const file=(path,size=100,mode='100644')=>({path,type:'blob',mode,size});
const tree=[file('src/cart.ts'),file('src/price.ts'),file('src/auth.ts'),file('src/cart.test.ts'),file('src/linked.ts',100,'120000'),file('src/big.ts',20000)];
test('candidate selection is evidence-ranked and rejects protected files and symlinks',()=>{
 assert.deepEqual(selectCandidates(tree,{path:'src/cart.ts',message:'src/auth.ts failed'},['src/price.ts','src/linked.ts','src/big.ts']),['src/cart.ts','src/price.ts']);
 for(const x of ['src/cart.test.ts','src/auth.ts','src/payments.ts','src/../x.ts','.github/workflows/ci.yml'])assert.equal(eligible(x),false);
 assert.throws(()=>selectCandidates(tree,{},[],'src/linked.ts'));
});
function mockGit(base='abc'){
 return {metadata:async()=>({default_branch:'main'}),head:async()=>({object:{sha:base}}),request:async(path)=>path.startsWith('/commits/')?{commit:{tree:{sha:'tree'}},files:[{filename:'src/cart.ts',status:'modified'}]}:{tree,truncated:false},file:async(path)=>({sha:'blob-'+path,text:'export const total = 2 - 1;'} )};
}
const incident={id:'incident-1',kind:'ci',evidence:{sha:'abc',path:'src/cart.ts',message:'Expected 3, received 1'}};
test('engine reads revision-specific evidence and produces reviewable repair',async()=>{
 const patch=await investigate(mockGit(),incident,{}, {decide:async context=>{
  assert.equal(context.baseSha,'abc');assert.equal(context.files[0].path,'src/cart.ts');
  return {decision:'repair',path:'src/cart.ts',summary:'Correct arithmetic',reason:'Expected sum',replacement:'export const total = 2 + 1;'};
 }});
 assert.equal(patch.original,'export const total = 2 - 1;');assert.equal(patch.blobSha,'blob-src/cart.ts');assert.equal(patch.attempt,1);
});
test('engine escalates without fabricating a repair',async()=>{
 const r=await investigate(mockGit(),incident,{}, {decide:async()=>({decision:'escalate',reason:'Insufficient context'})});
 assert.equal(r.decision,'escalate');
});
test('engine refuses stale failure or uninvestigated source',async()=>{
 await assert.rejects(investigate(mockGit('new'),incident,{},{}),/current base/);
 assert.throws(()=>validateDecision({decision:'repair',path:'src/other.ts'},{files:[]}),/not in/);
});
test('draft and retry require explicit authorization and bounded attempts',()=>{
 const project={enabled:true,auto_propose:true,auto_draft:true},patch={decision:'repair',engine:true,autoDraft:true,attempt:1};
 assert.equal(canDraft(project,incident,patch),true);
 assert.equal(canDraft({...project,auto_draft:false},incident,patch),false);
 assert.equal(retryEligible(project,patch,{exact:true,conclusion:'failure'}),true);
 assert.equal(retryEligible(project,{...patch,attempt:2},{exact:true,conclusion:'failure'}),false);
 assert.equal(retryEligible(project,patch,{exact:false,conclusion:'failure'}),false);
});
test('CI verification is tied to exact repair revision and workflow',()=>{
 const repo={full_name:'owner/repo'},pr={state:'open',base:{ref:'main',repo},head:{sha:'abc',ref:'resilyne/repair-x',repo}};
 const run={head_repository:repo,head_branch:pr.head.ref,head_sha:'abc',workflow_id:9,event:'push',status:'completed'};
 assert.equal(exactRun(pr,run,9,'owner/repo','main'),true);
 assert.equal(exactRun(pr,{...run,head_sha:'old'},9,'owner/repo','main'),false);
});
