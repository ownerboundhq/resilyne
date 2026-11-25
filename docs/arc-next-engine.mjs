// Neuravale original four-layer decoder, browser CPU inference. No AI API.
export function createArcNext(pack) {
 if(pack.format!=='neuravale.arcnext.f32le.v1'||pack.model!=='Neuravale Arc Next'||pack.checkpoint_sha256!=='93970736d02a48087aaecd33fbdefe9c7bc3d67667de66a75cda3448eff96736')throw Error('Unexpected Arc Next checkpoint');
 const {width:D,heads:H,layers:L,context:T,vocab:V}=pack.config,K=D/H;
 if(D!==256||H!==4||L!==4||T!==128||V!==4096)throw Error('Unsupported Arc Next architecture');
 const {pieces,scores,pad,bos,eos,unk,user,assistant}=pack.tokenizer;
 if(pieces.length!==V||scores.length!==V)throw Error('Tokenizer mismatch');
 const map=new Map(pieces.map((s,i)=>[s,i])),special=new Set([pad,bos,eos,unk,user,assistant]);
 const encoder=new TextEncoder(),decoder=new TextDecoder();
 function encodeText(s){
  s=String(s).replace(/<user>|<assistant>|<s>|<\/s>|<pad>|<unk>/g,'').normalize('NFKC').replace(/\s+/gu,' ').trim();
  if(!s)return [];
  let p=Array.from('▁'+s.replace(/ /g,'▁'));
  // SentencePiece BPE: repeatedly apply the highest scored adjacent merge.
  for(;;){let best=-1,score=-Infinity;for(let i=0;i<p.length-1;i++){const id=map.get(p[i]+p[i+1]);if(id!==undefined&&!special.has(id)&&scores[id]>score){best=i;score=scores[id];}}if(best<0)break;p.splice(best,2,p[best]+p[best+1]);}
  const out=[];for(const x of p){const id=map.get(x);if(id!==undefined&&!special.has(id))out.push(id);else for(const b of encoder.encode(x)){const k=map.get('<0x'+b.toString(16).padStart(2,'0').toUpperCase()+'>');out.push(k??unk);}}
  return out;
 }
 function decode(ids){let s='',bytes=[];const flush=()=>{if(bytes.length){s+=decoder.decode(Uint8Array.from(bytes));bytes=[];}};
  for(const id of ids){const p=pieces[id];const m=/^<0x([0-9A-F]{2})>$/.exec(p);if(m){bytes.push(parseInt(m[1],16));continue;}flush();if(!special.has(id))s+=p;}
  flush();return s.replace(/▁/g,' ').replace(/^ /,'');
 }
 function encode(turns){if(!turns.length||turns.length%2!==1)throw Error('Invalid conversation');const last=encodeText(turns.at(-1)),budget=T-1;if(last.length>budget-3)throw Error('Question too long for Arc Next');let ids=[bos,user,...last,assistant];for(let i=turns.length-3;i>=0;i-=2){const pair=[user,...encodeText(turns[i]),assistant,...encodeText(turns[i+1])];if(ids.length+pair.length>budget)break;ids=[bos,...pair,...ids.slice(1)];}return ids;}
 const W={};let count=0;
 for(const [n,t] of Object.entries(pack.tensors)){const bytes=atob(t.f32),expected=t.shape.reduce((a,b)=>a*b,1);if(bytes.length!==expected*4)throw Error('Invalid tensor '+n);const buf=new Uint8Array(bytes.length);for(let i=0;i<bytes.length;i++)buf[i]=bytes.charCodeAt(i);const view=new DataView(buf.buffer);const f=new Float32Array(expected);for(let i=0;i<expected;i++){f[i]=view.getFloat32(i*4,true);if(!Number.isFinite(f[i]))throw Error('Invalid weight');}W[n]=f;count+=expected;}
 if(count!==4240896)throw Error('Parameter count mismatch');
 function tensor(n,len){const t=W[n];if(!t||t.length!==len)throw Error('Tensor mismatch '+n);return t;}
 const emb=tensor('emb.weight',V*D),pos=tensor('pos.weight',T*D);
 const finW=tensor('norm.weight',D),finB=tensor('norm.bias',D);
 const blocks=Array.from({length:L},(_,i)=>{const p='blocks.'+i+'.';return {n1w:tensor(p+'n1.weight',D),n1b:tensor(p+'n1.bias',D),qkvw:tensor(p+'qkv.weight',3*D*D),qkvb:tensor(p+'qkv.bias',3*D),pw:tensor(p+'proj.weight',D*D),pb:tensor(p+'proj.bias',D),n2w:tensor(p+'n2.weight',D),n2b:tensor(p+'n2.bias',D),f1w:tensor(p+'ff.0.weight',4*D*D),f1b:tensor(p+'ff.0.bias',4*D),f2w:tensor(p+'ff.2.weight',4*D*D),f2b:tensor(p+'ff.2.bias',D)};});
 function norm(x,w,b){let mean=0,variance=0;for(const v of x)mean+=v;mean/=x.length;for(const v of x)variance+=(v-mean)**2;const inv=1/Math.sqrt(variance/x.length+1e-5);const y=new Float32Array(x.length);for(let i=0;i<x.length;i++)y[i]=(x[i]-mean)*inv*w[i]+b[i];return y;}
 function linear(x,w,b,n){const y=new Float32Array(n),d=x.length;for(let j=0;j<n;j++){let s=b?b[j]:0,o=j*d;for(let i=0;i<d;i++)s+=x[i]*w[o+i];y[j]=s;}return y;}
 function erf(x){const sign=x<0?-1:1;const a=Math.abs(x),t=1/(1+0.3275911*a);return sign*(1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-a*a));}
 function gelu(x){for(let i=0;i<x.length;i++){const v=x[i];x[i]=.5*v*(1+erf(v/Math.SQRT2));}return x;}
 function add(x,y){for(let i=0;i<x.length;i++)x[i]+=y[i];}
 function session(){const cache=blocks.map(()=>({k:new Float32Array(T*D),v:new Float32Array(T*D)}));let n=0;
  function step(id){if(n>=T)throw Error('Context full');const x=new Float32Array(D);for(let i=0;i<D;i++)x[i]=emb[id*D+i]+pos[n*D+i];
   for(let l=0;l<L;l++){const b=blocks[l],c=cache[l];const q=linear(norm(x,b.n1w,b.n1b),b.qkvw,b.qkvb,3*D);c.k.set(q.subarray(D,2*D),n*D);c.v.set(q.subarray(2*D),n*D);const a=new Float32Array(D);
    for(let h=0;h<H;h++){const o=h*K,z=new Float64Array(n+1);let max=-Infinity;for(let t=0;t<=n;t++){let s=0;for(let k=0;k<K;k++)s+=q[o+k]*c.k[t*D+o+k];z[t]=s/Math.sqrt(K);if(z[t]>max)max=z[t];}let sum=0;for(let t=0;t<=n;t++){z[t]=Math.exp(z[t]-max);sum+=z[t];}for(let k=0;k<K;k++){let s=0;for(let t=0;t<=n;t++)s+=z[t]*c.v[t*D+o+k];a[o+k]=s/sum;}}
    add(x,linear(a,b.pw,b.pb,D));add(x,linear(gelu(linear(norm(x,b.n2w,b.n2b),b.f1w,b.f1b,4*D)),b.f2w,b.f2b,D));}
   n++;return norm(x,finW,finB);}
  return step;}
 function generate(turns,onToken=()=>{},maxNew=64){const ids=encode(turns),step=session();let x;for(const id of ids)x=step(id);const out=[];const banned=new Set([pad,bos,unk,user,assistant]);const limit=Math.min(maxNew,T-ids.length);for(let j=0;j<limit;j++){const z=linear(x,emb,null,V);let best=-1,m=-Infinity;for(let i=0;i<V;i++)if(!banned.has(i)&&z[i]>m){m=z[i];best=i;}if(best===eos||best<0)break;out.push(best);onToken(decode(out));if(j+1<limit)x=step(best);}return decode(out);}
 return {encode,generate};
}
