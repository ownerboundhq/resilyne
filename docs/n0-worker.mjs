import {createModel} from './n0-engine.mjs';
let model=null;
self.onmessage=({data:m})=>{try{if(m.type==='load'){model=createModel(m.pack);self.postMessage({type:'ready',hash:m.pack.checkpoint_sha256,score:m.pack.development_score});}else if(m.type==='generate'){if(!model)throw Error('Model not loaded');const answer=model.generate(m.turns,text=>self.postMessage({type:'token',text}));self.postMessage({type:'done',text:answer});}}catch(e){self.postMessage({type:'error',text:e.message});}};
