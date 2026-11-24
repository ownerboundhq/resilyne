import test from 'node:test';
import assert from 'node:assert/strict';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {fileURLToPath} from 'node:url';
test('MCP negotiates stdio and serves local readiness without cloud credentials',{timeout:15000},async()=>{
 const env={...process.env,RESILYNE_PROJECT_ROOT:fileURLToPath(new URL('../',import.meta.url)),RESILYNE_URL:'',RESILYNE_TOKEN:''};
 const transport=new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../connect/mcp.mjs',import.meta.url))],env});
 const client=new Client({name:'resilyne-test',version:'1.0.0'});
 try{
  await client.connect(transport);
  const {tools}=await client.listTools();
  assert.deepEqual(tools.map(x=>x.name),['scan_local_project']);
  const result=await client.callTool({name:'scan_local_project',arguments:{}});
  assert.notEqual(result.isError,true);
  const report=JSON.parse(result.content[0].text);
  assert.equal(report.source,'local');
  assert.equal(report.checks.find(x=>x.id==='manifest').state,'pass');
 }finally{await client.close();}
});
