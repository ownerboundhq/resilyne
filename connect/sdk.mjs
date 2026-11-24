import {makeClient} from './client.mjs';
import {validateTelemetry} from './telemetry.mjs';
export function createTelemetry({origin,token,onError=()=>{}}){
 const client=makeClient({origin,token});let pending=0;
 async function send(event){
  try{validateTelemetry(event);if(pending>=4)return {accepted:false,reason:'busy'};pending++;
   try{return await client.telemetry(event);}finally{pending--;}
  }catch(e){try{onError(e);}catch{}return {accepted:false,reason:'unavailable'};}
 }
 return {heartbeat:()=>send({kind:'heartbeat'}),error:(code,count=1)=>send({kind:'error',code,count}),usage:(service,units,quantity,costMicrosUsd)=>send({kind:'usage',service,units,quantity,...(costMicrosUsd===undefined?{}:{costMicrosUsd})})};
}
