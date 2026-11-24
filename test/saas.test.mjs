import test from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPairSync,createVerify} from 'node:crypto';
import {allowedEndpoint,billable,equal,positiveId,uuid,signature,verifySignature,verificationGate,config} from '../saas/config.mjs';
import {appJWT} from '../saas/github.mjs';
test('webhook HMAC rejects changed payload and invalid signature',()=>{
 const raw=Buffer.from('{"action":"completed"}'),s=signature('test-secret',raw);
 assert.equal(verifySignature('test-secret',raw,s),true);
 assert.equal(verifySignature('test-secret',Buffer.from('changed'),s),false);
 assert.equal(verifySignature('',raw,s),false);
 assert.equal(verifySignature('test-secret',raw,'bad'),false);
});
test('health endpoint must match approved HTTPS URL',()=>{
 assert.equal(allowedEndpoint('https://example.com/health',['https://example.com/health']),'https://example.com/health');
 for(const url of ['http://example.com/health','https://example.com/other','https://user:secret@example.com/health','https://169.254.169.254/'])assert.throws(()=>allowedEndpoint(url,['https://example.com/health']));
 assert.equal(allowedEndpoint('',[]),null);
});
test('billing and IDs fail closed',()=>{
 assert.equal(billable('active',true),true);assert.equal(billable('past_due',true),false);assert.equal(billable('none',false),true);
 assert.throws(()=>positiveId('1/2'));assert.throws(()=>uuid('../x'));assert.equal(equal('abc','abcd'),false);
});
test('configuration rejects missing secrets and insecure origin',()=>{
 assert.throws(()=>config({PUBLIC_ORIGIN:'http://example.com'}));
 assert.throws(()=>config({PUBLIC_ORIGIN:'https://example.com'}),/DATABASE_URL/);
});
test('GitHub App JWT has valid RSA signature and short expiry',()=>{
 const {privateKey,publicKey}=generateKeyPairSync('rsa',{modulusLength:2048});
 const jwt=appJWT({appId:'1234',privateKey},1000);
 const [h,p,s]=jwt.split('.');assert.equal(JSON.parse(Buffer.from(h,'base64url')).alg,'RS256');
 const claims=JSON.parse(Buffer.from(p,'base64url'));assert.equal(claims.iss,'1234');assert.equal(claims.exp,1540);
 assert.equal(createVerify('RSA-SHA256').update(h+'.'+p).end().verify(publicKey,s,'base64url'),true);
});
test('merge gate requires exact repo, branch, head SHA and selected workflow',()=>{
 const repo={full_name:'owner/repo'};
 const pr={state:'open',draft:false,mergeable:true,head:{sha:'abc',ref:'resilyne/repair-1',repo},base:{ref:'main',repo}};
 const run={workflow_id:9,status:'completed',conclusion:'success',head_sha:'abc',head_branch:'resilyne/repair-1',head_repository:repo,event:'push'};
 const gate=(p,r)=>verificationGate(p,9,r,'abc','owner/repo','main');
 assert.equal(gate(pr,run),true);
 assert.equal(gate({...pr,draft:true},run),false);
 assert.equal(gate(pr,{...run,head_sha:'old'}),false);
 assert.equal(gate(pr,{...run,workflow_id:8}),false);
 assert.equal(gate(pr,{...run,conclusion:'failure'}),false);
 assert.equal(gate(pr,{...run,event:'workflow_dispatch'}),false);
 assert.equal(gate(pr,{...run,head_repository:{full_name:'other/repo'}}),false);
});
