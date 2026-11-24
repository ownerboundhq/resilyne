const fields={error:['kind','code','count'],usage:['kind','service','units','quantity','costMicrosUsd'],heartbeat:['kind']};
const tag=/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$/;
export function validateTelemetry(event){
 if(!event||typeof event!=='object'||Array.isArray(event)||!Object.hasOwn(fields,event.kind)||Object.keys(event).some(k=>!fields[event.kind].includes(k)))throw Error('Invalid telemetry shape; do not send logs or personal data');
 const integer=(v,max)=>Number.isSafeInteger(v)&&v>=0&&v<=max;
 if(event.kind==='heartbeat')return {kind:'heartbeat',label:'heartbeat',unit:'count',quantity:1,cost:null};
 if(event.kind==='error'){
  if(typeof event.code!=='string'||!tag.test(event.code)||!integer(event.count,10000)||event.count<1)throw Error('Invalid error code or count');
  return {kind:'error',label:event.code,unit:'count',quantity:event.count,cost:null};
 }
 if(typeof event.service!=='string'||!tag.test(event.service)||!['requests','tokens','bytes','seconds','units'].includes(event.units)||!integer(event.quantity,1000000000)||(event.costMicrosUsd!==undefined&&!integer(event.costMicrosUsd,1000000000)))throw Error('Invalid usage event');
 return {kind:'usage',label:event.service,unit:event.units,quantity:event.quantity,cost:event.costMicrosUsd??null};
}
