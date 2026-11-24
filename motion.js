(()=>{
'use strict';
const reduced=matchMedia('(prefers-reduced-motion: reduce)'),canvas=document.querySelector('#field'),ctx=canvas?.getContext('2d');
if(ctx){
 let w=0,h=0,frame=0,visible=true,mouseX=0,mouseY=0,targetX=0,targetY=0;
 const lines=54,points=180;
 const color=(r,g,b,a)=>'rgba('+r+','+g+','+b+','+Math.max(0,Math.min(1,a))+')';
 function project(u,v,t){
  const ring=1.52+.38*Math.cos(3*u+t*.18),tube=.54+.08*Math.sin(2*u-t*.24);
  let x=(ring+tube*Math.cos(v))*Math.cos(u),z=(ring+tube*Math.cos(v))*Math.sin(u),y=tube*Math.sin(v)+.19*Math.sin(3*u+t*.26);
  const tilt=.66,ang=.34+t*.14;
  const xx=x*Math.cos(ang)-z*Math.sin(ang);z=x*Math.sin(ang)+z*Math.cos(ang);x=xx;
  const yy=y*Math.cos(tilt)-z*Math.sin(tilt);z=y*Math.sin(tilt)+z*Math.cos(tilt);y=yy;
  const yaw=-.22,xxx=x*Math.cos(yaw)-y*Math.sin(yaw);y=x*Math.sin(yaw)+y*Math.cos(yaw);x=xxx;
  const scale=1/(1-z*.12),r=Math.min(w,h)*.192;
  return {x:w*.5+x*r*scale+mouseX,y:h*.48+y*r*scale+mouseY,z};
 }
 function draw(ms=0){
  if(!w||!h)return;const t=reduced.matches?0:ms*.00028;mouseX+=(targetX-mouseX)*.06;mouseY+=(targetY-mouseY)*.06;
  ctx.clearRect(0,0,w,h);
  const glow=ctx.createRadialGradient(w*.52,h*.48,0,w*.52,h*.48,Math.min(w,h)*.48);glow.addColorStop(0,'#bce7ab14');glow.addColorStop(.5,'#7ea78b12');glow.addColorStop(1,'#151b1800');ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
  ctx.lineWidth=.65;for(let i=0;i<lines;i++){
   const offset=i/lines*Math.PI*2;
   let prev=null;
   for(let j=0;j<=points;j++){
    const u=j/points*Math.PI*2,v=offset+u*2.0+.28*Math.sin(u*3+t*.45);
    const p=project(u,v,t);
    if(prev){const depth=(p.z+2.7)/5.4,light=Math.pow(Math.max(0,Math.sin(u*2-offset+t*.7)),3),a=.05+depth*.25+light*.20;
     ctx.strokeStyle=color(185,231,173,a);ctx.beginPath();ctx.moveTo(prev.x,prev.y);ctx.lineTo(p.x,p.y);ctx.stroke();}
    prev=p;
   }
  }
  for(let k=0;k<30;k++){
   const offset=(k*17%lines)/lines*Math.PI*2,u=(k*.83+t*(.36+(k%3)*.07))%(Math.PI*2),v=offset+u*2+.28*Math.sin(u*3+t*.45),p=project(u,v,t);
   ctx.fillStyle=color(222,255,210,.35+(p.z+2.7)/7);ctx.beginPath();ctx.arc(p.x,p.y,1.1+(p.z+2.7)*.15,0,Math.PI*2);ctx.fill();
  }
  ctx.strokeStyle='#c7f4b02a';ctx.lineWidth=.7;const margin=19,len=15;for(const [x,y,sx,sy] of [[margin,margin,1,1],[w-margin,margin,-1,1],[margin,h-margin,-1,-1],[w-margin,h-margin,1,-1]]){ctx.beginPath();ctx.moveTo(x+sx*len,y);ctx.lineTo(x,y);ctx.lineTo(x,y+sy*len);ctx.stroke();}
  canvas.parentElement.classList.add('rendered');
 }
 function resize(){const rect=canvas.getBoundingClientRect(),dpr=Math.min(window.devicePixelRatio||1,1.8);w=rect.width;h=rect.height;canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);draw(performance.now());}
 let last=0;function loop(t){frame=0;if(visible&&!document.hidden&&!reduced.matches){if(t-last>=32){draw(t);last=t;}frame=requestAnimationFrame(loop);}}
 function sync(){if(frame)cancelAnimationFrame(frame);frame=0;if(visible&&!document.hidden&&!reduced.matches)frame=requestAnimationFrame(loop);else draw(0);}
 if(typeof ResizeObserver!=='undefined')new ResizeObserver(resize).observe(canvas);else window.addEventListener('resize',resize);
 if(typeof IntersectionObserver!=='undefined')new IntersectionObserver(e=>{visible=e[0].isIntersecting;sync();}).observe(canvas);
 document.addEventListener('visibilitychange',sync);reduced.addEventListener?.('change',sync);
 if(matchMedia('(pointer:fine)').matches){canvas.parentElement.addEventListener('pointermove',e=>{if(!reduced.matches){const b=canvas.getBoundingClientRect();targetX=((e.clientX-b.left)/b.width-.5)*15;targetY=((e.clientY-b.top)/b.height-.5)*12;}},{passive:true});canvas.parentElement.addEventListener('pointerleave',()=>{targetX=targetY=0;});}
 resize();sync();
}
const $=id=>document.getElementById(id),run=$('run'),reset=$('reset'),terminal=$('terminal'),diff=$('diff'),title=$('incident-title'),status=$('signal-text'),dot=$('signal-dot'),note=$('patch-note'),steps=[...document.querySelectorAll('#pipeline li')];
let generation=0;
const timeline=[
 {title:'Checkout total is incorrect.',status:'Example failure detected',lines:[['00:01','CI test: expected $113.00, received $87.00.','warn'],['00:02','Failure recorded against the example revision.','']]},
 {title:'Investigating the calculation.',status:'Reviewing source evidence',lines:[['00:03','Relevant file: src/cart.ts.',''],['00:04','Tax is subtracted rather than added.','']]},
 {title:'A targeted patch is ready.',status:'Example patch generated',lines:[['00:05','Proposed change: replace subtraction with addition.',''],['00:06','Original source retained for review.','']]},
 {title:'Example tests passed.',status:'Simulated verification complete',lines:[['00:07','Simulated calculation test: passed.','ok'],['00:08','Simulated regression tests: passed.','ok']]},
 {title:'Ready for your review.',status:'Awaiting approval · no changes deployed',lines:[['00:09','Proposed fix and illustrative test results ready.','ok'],['00:10','No merge or deployment performed.','']]}
];
function line(time,msg,kind=''){const p=document.createElement('p'),stamp=document.createElement('time');stamp.textContent=time;p.className=kind;p.append(stamp,document.createTextNode(msg));terminal.append(p);terminal.scrollTop=terminal.scrollHeight;}
function setSteps(){steps.forEach((el,i)=>{el.className=i===0?'active':'';el.querySelector('b').textContent=i===0?'●':'○';});}
function clear(){generation++;run.disabled=false;run.textContent='Run example ▶';terminal.replaceChildren();line('00:00','Select Run example to begin.');setSteps();diff.classList.remove('show');title.textContent='Checkout total is incorrect.';status.textContent='Ready to run walkthrough';dot.classList.remove('success');note.textContent='Patch preview appears during the walkthrough.';}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
run.addEventListener('click',async()=>{if(run.disabled)return;clear();const current=generation;run.disabled=true;run.textContent='Running example…';terminal.replaceChildren();try{for(let i=0;i<timeline.length;i++){if(current!==generation)return;const stage=timeline[i];steps[i].classList.add('active');steps[i].querySelector('b').textContent='●';title.textContent=stage.title;status.textContent=stage.status;if(i===2){diff.classList.add('show');note.textContent='Example correction to the cart calculation.';}for(const item of stage.lines){if(current!==generation)return;line(...item);if(!reduced.matches)await wait(520);}if(current!==generation)return;steps[i].classList.remove('active');steps[i].classList.add('done');steps[i].querySelector('b').textContent='✓';if(i===3)dot.classList.add('success');if(!reduced.matches)await wait(180);} }finally{if(current===generation){run.disabled=false;run.textContent='Replay example ↻';}}});
reset.addEventListener('click',clear);
})();