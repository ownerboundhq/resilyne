// Deterministic utilities, not language-model output.
export function calculate(input){
 let s=input.trim().toLowerCase().replace(/^(?:please\s+)?(?:what is|what's|calculate|compute)\s+/,'').replace(/[?=]\s*$/,'').replace(/(?<=\d),(?=\d{3}(?:\D|$))/g,'').replace(/multiplied by|times|×/g,'*').replace(/divided by|÷/g,'/').replace(/\bplus\b/g,'+').replace(/\bminus\b/g,'-').trim();
 s=s.replace(/(\d+(?:\.\d+)?)\s*%\s+of\s+/g,'($1/100)*');
 if(s.length>180||!/\d/.test(s)||!/^[\d.\s()+*/%\-]+$/.test(s))return null;
 if(!/[+*/%()-]/.test(s))return null;
 const t=s.match(/\d+(?:\.\d*)?|\.\d+|[()+*/%\-]/g)||[];
 if(t.join('')!==s.replace(/\s/g,''))return null;
 let i=0;
 const error=()=>{throw Error('Invalid expression');};
 function atom(){const x=t[i++];if(x==='+')return atom();if(x==='-')return -atom();if(x==='('){const y=expression();if(t[i++]!==')')error();return y;}if(!x||!/^(?:\d+\.?\d*|\.\d+)$/.test(x))error();return Number(x);}
 function product(){let v=atom();while(['*','/','%'].includes(t[i])){const op=t[i++],r=atom();if((op==='/'||op==='%')&&r===0)throw Error('Division by zero is undefined');v=op==='*'?v*r:op==='/'?v/r:v%r;}return v;}
 function expression(){let v=product();while(t[i]==='+'||t[i]==='-'){const op=t[i++],r=product();v=op==='+'?v+r:v-r;}return v;}
 try{const n=expression();if(i!==t.length)error();if(!Number.isFinite(n)||Math.abs(n)>1e15)throw Error('Result outside supported range');return {text:String(Number(n.toPrecision(12))),expression:s};}catch(e){return {error:e.message};}
}
export function convert(input){
 const aliases={mm:['length',.001,'mm'],cm:['length',.01,'cm'],m:['length',1,'m'],km:['length',1000,'km'],in:['length',.0254,'in'],inch:['length',.0254,'in'],inches:['length',.0254,'in'],ft:['length',.3048,'ft'],feet:['length',.3048,'ft'],foot:['length',.3048,'ft'],yd:['length',.9144,'yd'],yards:['length',.9144,'yd'],mi:['length',1609.344,'mi'],miles:['length',1609.344,'mi'],g:['mass',.001,'g'],kg:['mass',1,'kg'],lb:['mass',.45359237,'lb'],lbs:['mass',.45359237,'lb'],pounds:['mass',.45359237,'lb'],oz:['mass',.028349523125,'oz'],ml:['volume',.001,'mL'],l:['volume',1,'L'],litres:['volume',1,'L'],liters:['volume',1,'L'],'us gal':['volume',3.785411784,'US gal'],'us cup':['volume',.2365882365,'US cup'],c:['temp',1,'°C'],celsius:['temp',1,'°C'],f:['temp',1,'°F'],fahrenheit:['temp',1,'°F'],k:['temp',1,'K']};
 const s=input.trim().toLowerCase().replace(/^convert\s+/,'').replace(/[?]$/,'').replace(/°\s*/g,'');
 const m=s.match(/^(-?(?:\d+(?:\.\d*)?|\.\d+))\s+?([a-z ]+?)\s+(?:to|in|into)\s+([a-z ]+)$/);
 if(!m)return null;
 const n=Number(m[1]),from=aliases[m[2].trim()],to=aliases[m[3].trim()];
 if(!from||!to)return null;
 if(from[0]!==to[0])return {error:'These units measure different quantities.'};
 let value;
 if(from[0]==='temp'){const c=from[2]==='°F'?(n-32)*5/9:from[2]==='K'?n-273.15:n;if(c< -273.150000001)return {error:'Temperature cannot be below absolute zero.'};value=to[2]==='°F'?c*9/5+32:to[2]==='K'?c+273.15:c;}else value=n*from[1]/to[1];
 if(!Number.isFinite(value)||Math.abs(value)>1e15)return {error:'Result outside supported range.'};
 return {text:`${Number(value.toPrecision(10))} ${to[2]}`,expression:`${n} ${from[2]} → ${to[2]}`};
}
export function textStats(input){const text=String(input);const trimmed=text.trim();const words=trimmed?trimmed.split(/\s+/u).length:0;return {words,characters:Array.from(text).length,lines:text?text.split(/\r\n|\n|\r/).length:0,readingMinutes:words/200};}
export function utilityAnswer(s){const c=calculate(s);if(c)return {...c,kind:'Calculator'};const u=convert(s);if(u)return {...u,kind:'Unit converter'};return null;}
