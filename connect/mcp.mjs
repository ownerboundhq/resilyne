import {McpServer} from '@modelcontextprotocol/sdk/server/mcp.js';
import {StdioServerTransport} from '@modelcontextprotocol/sdk/server/stdio.js';
import {localScan} from './scan.mjs';
import {makeClient} from './client.mjs';
const server=new McpServer({name:'resilyne',version:'0.4.0'});
const root=process.env.RESILYNE_PROJECT_ROOT||process.cwd();
const text=value=>({content:[{type:'text',text:JSON.stringify(value,null,2)}]});
const register=(name,description,handler,readOnly=true)=>server.registerTool(name,{description,inputSchema:{},annotations:{readOnlyHint:readOnly,destructiveHint:false,idempotentHint:readOnly,openWorldHint:name!=='scan_local_project'}},async()=>{
 try{return text(await handler());}catch(e){return {isError:true,content:[{type:'text',text:String(e.message).slice(0,300)}]};}
});
register('scan_local_project','Read-only readiness checks for the configured local project root. Does not run code, send source or scan secret values.',()=>localScan(root));
if(process.env.RESILYNE_URL&&process.env.RESILYNE_TOKEN){
 const client=makeClient({origin:process.env.RESILYNE_URL,token:process.env.RESILYNE_TOKEN});
 register('get_project_status','Get monitoring and maintenance status for the authorized Resilyne project.',client.status);
 register('get_health_report','Read the latest repository readiness report.',client.report);
 register('list_incidents','List incident summaries without source or raw evidence.',client.incidents);
 register('list_repairs','List proposed repairs and verification status. Does not expose source or approve changes.',client.repairs);
 register('request_readiness_scan','Queue a read-only repository readiness report; does not trigger AI repairs or GitHub writes.',client.scan,false);
}
await server.connect(new StdioServerTransport());
