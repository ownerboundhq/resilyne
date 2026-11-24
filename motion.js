(()=>{
'use strict';
const canvas=document.getElementById('neural'),ctx=canvas?.getContext('2d'),reduced=matchMedia('(prefers-reduced-motion: reduce)');
if(ctx){
 let w=0,h=0,dpr=1,frame=0,visible=true,px=0,py=0,targetX=0,targetY=0;
 const N=260,golden=Math.PI*(3-Math.sqrt(5));
 const nodes=Array.from({length:N},(_,i)=>{const y=1-2*(i+.5)/N,r=Math.sqrt(1-y*y),a=i*golden;return {x:r*Math.cos(a),y,z:r*Math.sin(a)}});
 const edges=[];for(let i=0;i<N;i++)for(let j=i+1;j<N;j++){const a=nodes[i],b=nodes[j],d=(a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2;if(d<.070)edges.push([i,j]);}
 function draw(ms=0){
  if(!w||!h)return;
  const t=reduced.matches?0:ms*.00017,angle=t*.75,co=Math.cos(angle),si=Math.sin(angle),tilt=.22;
  px+=(targetX-px)*.045;py+=(targetY-py)*.045;
  ctx.clearRect(0,0,w,h);const radius=Math.min(w*.38,h*.43)*(1+.035*Math.sin(t*3)),cx=w*.55+px,cy=h*.5+py;
  const pts=nodes.map(n=>{let x=n.x*co+n.z*si,z=-n.x*si+n.z*co,y=n.y;const yy=y*Math.cos(tilt)-z*Math.sin(tilt);z=y*Math.sin(tilt)+z*Math.cos(tilt);const scale=1/(1-z*.19);return {x:cx+x*radius*scale,y:cy+yy*radius*scale,z};});
  for(let k=0;k<edges.length;k++){const [i,j]=edges[k],a=pts[i],b=pts[j],depth=(a.z+b.z+2)/4,flash=Math.pow(Math.max(0,Math.sin(t*4+k*.31)),14);
   ctx.strokeStyle='rgba(128,153,255,'+(.045+depth*.19+flash*.22)+')';ctx.lineWidth=.65+flash*.7;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
   if(k%29===0){const f=(t*.9+k*.071)%1;ctx.fillStyle='rgba(183,208,255,'+(.3+depth*.5)+')';ctx.beginPath();ctx.arc(a.x+(b.x-a.x)*f,a.y+(b.y-a.y)*f,1.8,0,Math.PI*2);ctx.fill();}
  }
  for(let i=0;i<pts.length;i++){const p=pts[i],depth=(p.z+1)/2,flash=Math.pow(Math.max(0,Math.sin(t*5+i*.8)),10);ctx.fillStyle='rgba(173,193,255,'+(.2+depth*.55)+')';ctx.beginPath();ctx.arc(p.x,p.y,.8+depth*1.1+flash*.85,0,Math.PI*2);ctx.fill();}
 }
 function resize(){const b=canvas.getBoundingClientRect();w=b.width;h=b.height;dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);draw(performance.now());}
 function loop(t){frame=0;if(visible&&!document.hidden&&!reduced.matches){draw(t);frame=requestAnimationFrame(loop);}}
 function sync(){if(frame)cancelAnimationFrame(frame);frame=0;if(visible&&!document.hidden&&!reduced.matches)frame=requestAnimationFrame(loop);else draw(0);}
 new ResizeObserver(resize).observe(canvas);new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();}).observe(canvas);
 document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);
 if(matchMedia('(pointer:fine)').matches){window.addEventListener('pointermove',e=>{if(!reduced.matches){targetX=(e.clientX/innerWidth-.5)*22;targetY=(e.clientY/innerHeight-.5)*16;}},{passive:true});}
 resize();sync();
}
const run=document.getElementById('run'),terminal=document.getElementById('terminal'),diff=document.getElementById('diff'),status=document.getElementById('lab-status'),title=document.getElementById('incident-title'),steps=[...document.querySelectorAll('#pipeline li')];
const timeline=[
 {title:'Failure detected.',lines:[['00:01','CI signal: cart calculation test failed.','warn'],['00:02','Example assertion: expected 113, received 87.','warn']]},
 {title:'Investigating source.',lines:[['00:03','Inspecting relevant source at the failed revision.',''],['00:04','Candidate selected: src/cart.ts · tax applied with incorrect operator.','']]},
 {title:'Repair proposed.',lines:[['00:05','Minimal patch prepared: subtract → add.',''],['00:06','Illustrative draft pull request prepared for authorized verification.','']]},
 {title:'Verification result.',lines:[['00:07','Simulated CI: calculation test passes.','ok'],['00:08','Simulated regression suite passes.','ok']]},
 {title:'Ready for human review.',lines:[['00:09','Example verification complete.','ok'],['00:10','Awaiting human merge authorization. No production change made.','']]}
];
function line(time,msg,kind){const p=document.createElement('p'),stamp=document.createElement('span');stamp.className='terminal-time';stamp.textContent=time;p.append(stamp,document.createTextNode(msg));p.className=kind;terminal.append(p);terminal.scrollTop=terminal.scrollHeight;}
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
run.addEventListener('click',async()=>{if(run.disabled)return;run.disabled=true;run.textContent='Simulation running…';terminal.replaceChildren();diff.classList.remove('show');steps.forEach(el=>{el.className='';el.querySelector('b').textContent='○';});
 try{for(let i=0;i<timeline.length;i++){const stage=timeline[i];steps[i].classList.add('active');steps[i].querySelector('b').textContent='◉';title.textContent=stage.title;status.textContent='Simulation · '+stage.title;if(i===2)diff.classList.add('show');for(const item of stage.lines){line(...item);if(!reduced.matches)await wait(560);}steps[i].classList.remove('active');steps[i].classList.add('done');steps[i].querySelector('b').textContent='✓';if(!reduced.matches)await wait(300);}status.textContent='Simulation complete · awaiting review';}finally{run.disabled=false;run.textContent='Replay simulation ↻';}
});
})();