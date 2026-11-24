import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const ctx=vm.createContext({});
vm.runInContext(readFileSync(new URL('../beta/sheets/Code.gs',import.meta.url),'utf8'),ctx);
test('health URLs are bounded and reject obvious unsafe or unsupported destinations',()=>{
 for(const x of ['http://example.com','https://127.0.0.1','https://foo.local','https://foo.internal','https://user@example.com','https://example.com:8080','https://example.com/?key=secret','https://[::1]'])assert.equal(ctx.validHealthUrl_(x),null);
 assert.equal(ctx.validHealthUrl_('https://ownerboundhq.github.io/resilyne/'),'https://ownerboundhq.github.io/resilyne/');
});
test('two failures establish DOWN and two successes establish recovery',()=>{
 let s=ctx.transition_('UP',0,2,false);assert.equal(s.state,'SUSPECT');
 s=ctx.transition_(s.state,s.failures,s.successes,false);assert.equal(s.state,'DOWN');
 s=ctx.transition_(s.state,s.failures,s.successes,true);assert.equal(s.state,'DOWN');
 s=ctx.transition_(s.state,s.failures,s.successes,true);assert.equal(s.state,'UP');
});
test('no token never implies zero security alerts',()=>{
 ctx.UrlFetchApp={fetch:()=>({getResponseCode:()=>200,getContentText:()=>JSON.stringify({workflow_runs:[{conclusion:'success'}]})})};
 let s=ctx.signals_('ownerboundhq/resilyne','');assert.equal(s.ci,'SUCCESS');assert.equal(s.alerts,'');assert.equal(s.coverage,'NOT ASSESSED');
});
