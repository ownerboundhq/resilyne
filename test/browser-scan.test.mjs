import test from 'node:test';
import assert from 'node:assert/strict';
import {inspect,normalizeFiles,MAX_FILES} from '../connect/browser-scan.mjs';
const f=(path,content='',readable=false)=>({name:path.split('/').at(-1),webkitRelativePath:'app/'+path,size:content.length,text:async()=>{if(!readable)throw Error('Unexpected read');return content;}});
const manifest=JSON.stringify({scripts:{test:'node --test',build:'vite build',lint:'eslint .'},engines:{node:'22'},dependencies:{pg:'8'}});
test('browser scan reads only the root manifest, detects real project indicators, leaves live checks unknown',async()=>{
 const reads=[];
 const report=await inspect([f('package.json',manifest,true),f('package-lock.json'),f('tests/cart.test.js'),f('.github/workflows/ci.yml'),f('.gitignore'),f('README.md'),f('.env.example'),f('migrations/001.sql'),f('src/cart.js','secret'),f('node_modules/ignored.js')],{read:async file=>{reads.push(file.name);return file.text();}});
 assert.deepEqual(reads,['package.json']);
 assert.equal(report.counts.pass,12);assert.equal(report.counts.attention,0);assert.equal(report.counts.unknown,5);
 assert.equal(report.filesExamined,9);
 assert.equal(JSON.stringify(report).includes('secret'),true); // generic check label, never source value
});
test('missing lockfile, tests and potential secret filenames generate actions without reading secrets',async()=>{
 const report=await inspect([f('package.json','{"scripts":{"test":"echo no test specified"}}',true),f('.env','NEVER_SEND_VALUE'),f('src/index.js','NEVER_SEND_VALUE')]);
 for(const id of ['lock','tests','secrets','ci'])assert.equal(report.checks.find(x=>x.id===id).state,'attention');
 assert.equal(JSON.stringify(report).includes('NEVER_SEND_VALUE'),false);
 assert.equal(report.checks.find(x=>x.id==='vulnerability').state,'unknown');
});
test('invalid manifest and truncated folder do not claim missing or healthy checks',async()=>{
 const r=await inspect([f('package.json','{',true)]);assert.equal(r.checks.find(x=>x.id==='manifest').state,'unknown');
 const paths=Array.from({length:MAX_FILES+1},(_,i)=>f('src/'+i+'.js'));const partial=await inspect(paths);
 assert.equal(partial.truncated,true);assert.equal(partial.checks.find(x=>x.id==='secrets').state,'unknown');
});
test('rejects traversal paths and skips generated dependencies',()=>{
 const r=normalizeFiles([f('../secret.txt'),f('node_modules/a.js'),f('src/index.js')]);assert.deepEqual(r.list.map(x=>x.path),['src/index.js']);
});
