import { tr } from './common.js';
import { detailTransform } from './view-geometry.js';

export function createDetailViewer(panel) {
 const canvases=[...panel.querySelectorAll('canvas')],buttons=[...panel.querySelectorAll('[data-zoom-level]')];
 let zoom=1,center=[.5,.5],images=[],data=null,sequence=0,drag=null,frame=0;
 function render(){
  if(!panel.open||!data||images.length!==2)return;
  const box=canvases[1].getBoundingClientRect();if(!box.width||!box.height)return;
  const t=detailTransform(data.w,data.h,box.width,box.height,zoom,center);center=t.center;
  const dpr=window.devicePixelRatio||1;
  canvases.forEach((canvas,i)=>{
   const width=Math.round(box.width*dpr),height=Math.round(box.height*dpr);
   if(canvas.width!==width)canvas.width=width;if(canvas.height!==height)canvas.height=height;
   const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,box.width,box.height);
   ctx.imageSmoothingEnabled=t.scale<1;
   ctx.drawImage(images[i],t.x,t.y,t.width,t.height);
   const percent=Math.round(t.width/images[i].naturalWidth*100);
   panel.querySelector(i===0?'#capA':'#capB').textContent=`${i===0?data.leftLabel:data.rightLabel} · ${percent}%`;
  });
  panel.querySelector('#detailPosition').textContent=`${Math.round(center[0]*100)}%, ${Math.round(center[1]*100)}%`;
  buttons.forEach(b=>b.setAttribute('aria-pressed',String(String(zoom)===b.dataset.zoomLevel)));
 }
 function schedule(){cancelAnimationFrame(frame);frame=requestAnimationFrame(render);}
 function setZoom(value){zoom=value==='fit'?'fit':Number(value);render();}
 buttons.forEach(b=>b.addEventListener('click',()=>setZoom(b.dataset.zoomLevel)));
 panel.querySelector('#detailCenter').addEventListener('click',()=>{center=[.5,.5];render();});
 for(const canvas of canvases){
  canvas.addEventListener('pointerdown',e=>{if(!data||zoom==='fit'||e.button!==0)return;e.preventDefault();canvas.focus({preventScroll:true});canvas.setPointerCapture(e.pointerId);drag={id:e.pointerId,x:e.clientX,y:e.clientY,center:[...center]};canvas.classList.add('dragging');});
  canvas.addEventListener('pointermove',e=>{if(!drag||drag.id!==e.pointerId||!canvas.hasPointerCapture(e.pointerId))return;center=[drag.center[0]-(e.clientX-drag.x)/(data.w*zoom),drag.center[1]-(e.clientY-drag.y)/(data.h*zoom)];render();});
  const end=()=>{drag=null;canvas.classList.remove('dragging');};canvas.addEventListener('lostpointercapture',end);canvas.addEventListener('pointercancel',end);
  canvas.addEventListener('keydown',e=>{
   if(!data)return;
   if(e.key==='Home'){e.preventDefault();center=[.5,.5];render();return;}
   if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
   e.preventDefault();if(zoom==='fit')setZoom(1);
   const step=e.shiftKey?80:20;
   center[0]+=(e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0)/(data.w*zoom);
   center[1]+=(e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0)/(data.h*zoom);render();
  });
 }
 new ResizeObserver(schedule).observe(panel.querySelector('.detail-views'));
 panel.addEventListener('toggle',()=>{if(!panel.open){drag=null;return;}schedule();});
 return {
  update(next){
   if(data?.left===next.left&&data?.right===next.right){data=next;schedule();return;}
   data=next;images=[];const id=++sequence;
   const incoming=[next.left,next.right].map(src=>{const im=new Image();im.src=src;return im;});
   Promise.all(incoming.map(im=>im.decode())).then(()=>{if(id!==sequence)return;images=incoming;render();}).catch(()=>{if(id===sequence)panel.querySelector('#detailPosition').textContent=tr({it:'Anteprima non disponibile',en:'Preview unavailable'});});
  },
  reset(){sequence++;data=null;images=[];center=[.5,.5];zoom=1;drag=null;canvases.forEach(c=>c.getContext('2d').clearRect(0,0,c.width,c.height));},
 };
}
