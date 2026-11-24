import test from 'node:test';
import assert from 'node:assert/strict';
import {repoName,sourcePath,upsertIncident,validateProposal,assertFresh} from '../lib/core.mjs';
test('repository identifiers are constrained',()=>{assert.equal(repoName('owner/repo'),'owner/repo');for(const x of ['../repo','https://evil.com/a','owner/repo?x'])assert.throws(()=>repoName(x))});
test('source path allowlist rejects traversal and infrastructure',()=>{assert.equal(sourcePath('src/components/Button.tsx'),'src/components/Button.tsx');for(const x of ['src/../a.js','.github/workflows/a.js','src/.env','src/auth.ts','src/config.js','src/a.json','/src/a.js'])assert.throws(()=>sourcePath(x))});
test('incident upsert deduplicates',()=>{const state={incidents:[]};upsertIncident(state,'ci','1',{title:'A'},'t1');upsertIncident(state,'ci','1',{title:'B'},'t2');assert.equal(state.incidents.length,1);assert.equal(state.incidents[0].firstSeen,'t1');assert.equal(state.incidents[0].lastSeen,'t2')});
test('proposal requires changed source',()=>{assert.throws(()=>validateProposal({summary:'fix',replacement:'x'},'x'));assert.throws(()=>validateProposal({summary:'fix',replacement:''},'x'));assert.equal(validateProposal({summary:'fix',replacement:'y'},'x').replacement,'y')});
test('stale bases are rejected',()=>{assert.throws(()=>assertFresh('a','b'));assert.doesNotThrow(()=>assertFresh('a','a'))});
