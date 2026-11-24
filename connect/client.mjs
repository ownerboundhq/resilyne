export function makeClient({origin,token,fetcher=fetch}){
 const u=new URL(origin);
 if((u.protocol!=='https:'&&!(u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname)))||u.username||u.password||u.pathname!=='/'||u.hash||u.search)throw Error('RESILYNE_URL must be an HTTPS origin or localhost');
 if(typeof token!=='string'||!/^rsl_[A-Za-z0-9_-]{43}$/.test(token))throw Error('A project-scoped Resilyne token is required');
 async function request(path,data){
  const response=await fetcher(u.origin+'/connect/v1/'+path,{method:data===undefined?'GET':'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),redirect:'error',signal:AbortSignal.timeout(15000)});
  if(!response.ok)throw Error('Resilyne API returned '+response.status);
  return response.json();
 }
 return {status:()=>request('status'),report:()=>request('report'),incidents:()=>request('incidents'),repairs:()=>request('repairs'),scan:()=>request('scan',{}),telemetry:event=>request('telemetry',event)};
}
