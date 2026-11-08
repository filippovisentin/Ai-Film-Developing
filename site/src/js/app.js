import { makeCompare, tr, lang } from "./common.js";

const $ = (s) => document.querySelector(s), files = {}, names = {}, urls = [], imgs = {}, sampleFiles = new Set();
let profiles = [], sr = 2, results = {}, current = "originale", busy = false, loadingSample = false, ready = false, userChoice = false, stale = false;
const LABELS = { originale: { it: "Sviluppo base", en: "Base development" }, migliorata: { it: "Migliorata", en: "Enhanced" }, ai: { it: "Ingrandita AI", en: "AI upscale" } };
const NOTES = {
 originale: { it: "Conversione del negativo, senza pulizia o ingrandimento AI.", en: "Negative conversion, without clean-up or AI upscaling." },
 migliorata: { it: "Polvere e rumore ridotti. Trascina il cursore per confrontare con lo sviluppo base.", en: "Reduced dust and noise. Drag the handle to compare with base development." },
 ai: { it: "Questa versione può contenere dettagli inventati dall'AI. Confrontala con lo sviluppo base.", en: "This version may contain AI-invented detail. Compare it with base development." },
};
const STAGES = {
 engine: { it: "Preparazione del motore. La prima volta scarica circa 10 MB…", en: "Preparing the engine. The first time downloads about 10 MB…" },
 decode: { it: "Lettura delle foto…", en: "Reading your photos…" },
 develop: { it: "Sviluppo della foto…", en: "Developing your photo…" },
 "enhance-polvere": { it: "Riduzione della polvere…", en: "Reducing dust…" },
 "enhance-rumore": { it: "Riduzione del rumore…", en: "Reducing noise…" },
 "enhance-nitidezza": { it: "Preparazione della versione Migliorata…", en: "Preparing the Enhanced version…" },
 "ai-load": { it: "Caricamento del modello AI…", en: "Loading the AI model…" },
 ai: { it: "Ingrandimento AI…", en: "AI upscaling…" },
};
const cmp = makeCompare($("#cmp"));
makeCompare($("#previewCmp"));
const worker = new Worker("js/worker.js");
let lastStage = "engine", lastFraction = 0;
function updateControls() {
 $("#controls").disabled = busy || loadingSample;
 $("#sample").disabled = busy || loadingSample;
 $("#quickOpen").disabled = busy || loadingSample;
 $("#quickSample").disabled = busy || loadingSample;
 $("#profilo").disabled = !profiles.length;
 $("#go").disabled = busy || loadingSample || !files.negativo || !profiles.length;
 document.querySelectorAll("#sr button").forEach((b) => b.disabled = !$("#ai").checked);
 $(".result").setAttribute("aria-busy", String(busy));
}
function engineState() {
 $("#engineState").className = "engine-state" + (ready ? " ready" : "");
 $("#engineState").textContent = tr(ready ? { it: "Elaborazione locale pronta", en: "Local processing ready" } : { it: "Elaborazione locale", en: "Local processing" });
}
worker.onmessage = ({ data: m }) => {
 if (m.type === "ready") { ready = true; engineState(); }
 else if (m.type === "progress") setProgress(m.stage, m.frac);
 else if (m.type === "partial") {
  results[m.key] = wrap(m.result); if (m.warnings) showWarnings(m.warnings);
  show(userChoice && results[current] ? current : m.key);
 } else if (m.type === "done") {
  for (const [k,r] of Object.entries(m.results)) if (!results[k]) results[k] = wrap(r);
  busy = false; ready = true; engineState(); updateControls(); showWarnings(m.warnings);
  $("#viewerStatus").textContent = tr({ it: `Sviluppo completato in ${(m.ms/1000).toFixed(1)} s.`, en: `Development completed in ${(m.ms/1000).toFixed(1)} s.` });
  show(userChoice && results[current] ? current : results.migliorata ? "migliorata" : "originale");
 } else if (m.type === "error") fail(m.message);
};
worker.onerror = (e) => fail(e.message || tr({it:"Il motore non si è avviato. Ricarica la pagina.",en:"The engine could not start. Reload the page."}));

function renderProfiles() {
 const sel = $("#profilo"), prev = sel.value || "generic_color";
 sel.replaceChildren();
 const groups = { color_negative:{it:"Negativo colore",en:"Colour negative"}, bw_negative:{it:"Bianco e nero",en:"Black and white"}, slide:{it:"Diapositiva",en:"Slide"} };
 for (const [type,label] of Object.entries(groups)) {
  const list = profiles.filter(p=>p.type===type); if (!list.length) continue;
  const group = document.createElement("optgroup"); group.label = tr(label);
  for (const p of list) group.append(new Option(lang()==="en" && p.name_en ? p.name_en : p.name,p.id,false,p.id===prev));
  sel.append(group);
 }
 sel.setAttribute("aria-label",tr({it:"Pellicola",en:"Film stock"}));
 updateControls();
}
const profilesReady = (async()=>{
 try { const response = await fetch("data/profiles.json"); if (!response.ok) throw new Error("profiles"); profiles = await response.json(); if (!profiles.length) throw new Error("profiles"); renderProfiles(); }
 catch { fail(tr({it:"Profili non caricati. Ricarica la pagina per riprovare.",en:"Film profiles could not load. Reload the page to retry."})); }
})();
function resetResults() {
 results = {}; userChoice = false; stale = false; urls.splice(0).forEach(u=>URL.revokeObjectURL(u));
 for (const key of Object.keys(imgs)) delete imgs[key];
 $("#out").hidden = true; $("#empty").hidden = false; $("#warns").replaceChildren();
 $("#viewerStatus").textContent = ""; $("#viewTitle").textContent = tr({it:"Anteprima",en:"Preview"});
}
function previewInput() {
 $("#previewCmp").hidden = !!files.negativo; $("#inputStage").hidden = !files.negativo;
 $("#previewCaption").textContent = files.negativo ? names.negativo : tr({it:"Esempio incluso: Fuji 100, Tokyo 1994.",en:"Included sample: Fuji 100, Tokyo 1994."});
}
function markDirty() {
 if (!Object.keys(results).length || busy) return;
 stale = true;
 $("#viewerStatus").textContent = tr({it:"Impostazioni cambiate. Premi Sviluppa foto per aggiornare il risultato.",en:"Settings changed. Press Develop photo to update the result."});
 document.querySelectorAll('#dl a').forEach(a=>{a.removeAttribute('href');a.setAttribute('aria-disabled','true');});
}
function setFile(drop,file,name,{fromSample=false}={}) {
 if (busy || (loadingSample && !fromSample)) return;
 const key = drop.dataset.key, im = drop.querySelector("img");
 if (key === 'negativo' && sampleFiles.has(key) && !fromSample) {
  for (const ref of ['luce','bordo']) if (sampleFiles.has(ref)) setFile(document.querySelector(`.drop[data-key="${ref}"]`),null);
 }
 if (fromSample && file) sampleFiles.add(key); else sampleFiles.delete(key);
 if (im.src.startsWith("blob:")) URL.revokeObjectURL(im.src);
 files[key] = file; names[key] = name || file?.name || key;
 drop.querySelector(".ok").textContent = file ? names[key] : "";
 drop.classList.toggle("has",!!file);
 if (file) { im.src = URL.createObjectURL(file); im.hidden = false; im.onerror = ()=>im.hidden=true; }
 else { im.removeAttribute("src"); im.hidden = true; }
 let clear = drop.querySelector(".clear");
 if (file && !clear) {
  clear = document.createElement("button"); clear.type="button"; clear.className="clear"; clear.textContent="×";
  clear.addEventListener("click",()=>{setFile(drop,null);drop.querySelector("input").value="";}); drop.append(clear);
 } else if (!file && clear) clear.remove();
 if (file) clear.setAttribute("aria-label",tr({it:"Rimuovi foto",en:"Remove photo"}));
 if (key==="negativo") { resetResults(); $("#inputPreview").hidden=false;$("#inputUnreadable").hidden=true; if (file) $("#inputPreview").src=im.src; else $("#inputPreview").removeAttribute("src"); previewInput(); }
 else markDirty();
 $("#msg").textContent=""; updateControls();
}
document.querySelectorAll(".drop").forEach(drop=>{
 const input=drop.querySelector("input");
 input.addEventListener("change",()=>input.files[0] && setFile(drop,input.files[0]));
 drop.addEventListener("dragover",e=>{e.preventDefault();if(!busy)drop.classList.add("over");});
 drop.addEventListener("dragleave",()=>drop.classList.remove("over"));
 drop.addEventListener("drop",e=>{e.preventDefault();drop.classList.remove("over");if(e.dataTransfer.files[0])setFile(drop,e.dataTransfer.files[0]);});
});
$("#quickOpen").addEventListener('click',()=>$("#negativeInput").click());
$("#quickSample").addEventListener('click',()=>$("#sample").click());
$("#inputPreview").addEventListener('error',()=>{if(files.negativo){$("#inputPreview").hidden=true;$("#inputUnreadable").hidden=false;}});
$("#sample").addEventListener("click",async()=>{
 loadingSample=true; updateControls(); $("#viewerStatus").textContent=tr({it:"Caricamento dell'esempio…",en:"Loading the sample…"});
 try {
  const fetched=await Promise.all([['negativo','negativo.jpg'],['luce','luce.jpg'],['bordo','bordo.jpg']].map(async([key,file])=>{
   const response=await fetch(`img/esempio/${file}`); if(!response.ok)throw new Error("sample"); return [key,await response.blob(),file];
  }));
  await profilesReady;
  if (!profiles.length) throw new Error("profiles");
  for(const [key,blob,name] of fetched) setFile(document.querySelector(`.drop[data-key="${key}"]`),blob,name,{fromSample:true});
  $("#profilo").value="generic_color";
  loadingSample=false;updateControls();$("#form").requestSubmit();
 } catch { loadingSample=false;fail(tr({it:"L'esempio non è stato caricato. Riprova oppure apri una tua foto.",en:"The sample could not load. Retry or open your own photo."})); }
});
$("#ai").addEventListener("change",()=>{updateControls();markDirty();});
$("#profilo").addEventListener("change",markDirty);
$("#migliora").addEventListener("change",markDirty);
document.querySelectorAll("#sr button").forEach(b=>b.addEventListener("click",()=>{
 sr=+b.dataset.sr; document.querySelectorAll("#sr button").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));
 markDirty();
}));
$("#form").addEventListener("submit",e=>{
 e.preventDefault(); if(!files.negativo || busy || loadingSample || !profiles.length)return;
 resetResults();busy=true;updateControls();$("#msg").textContent="";$("#msg").className="msg";setProgress("engine",0);
 if(matchMedia('(max-width:760px)').matches)$(".result").scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});
 worker.postMessage({type:"develop",lang:lang(),profile:profiles.find(p=>p.id===$("#profilo").value),files:{negativo:files.negativo,luce:files.luce||null,bordo:files.bordo||null},migliora:$("#migliora").checked,ai:$("#ai").checked?sr:0});
});
function setProgress(stage,frac) {
 lastStage=stage;lastFraction=frac;
 const pct=stage==="ai"?` ${Math.max(0,Math.min(100,Math.round((frac-.6)/.38*100)))}%`:"";
 $("#viewerStatus").textContent=tr(STAGES[stage]||{it:"Elaborazione…",en:"Processing…"})+pct;
}
function fail(message) {
 busy=false;updateControls();
 const text=message==="decode"?tr({it:"Il browser non apre questo formato. Prova JPEG o PNG; per HEIC serve Safari.",en:"This browser cannot open that format. Try JPEG or PNG; HEIC requires Safari."}):message;
 $("#msg").className="msg err";$("#msg").textContent=text;
 $("#viewerStatus").textContent=tr({it:"Elaborazione interrotta. Controlla l'avviso nelle impostazioni.",en:"Processing stopped. Check the message in the settings."});
}
function showWarnings(list) {
 $("#warns").replaceChildren();for(const warning of list||[]){const li=document.createElement("li");li.textContent=warning;$("#warns").append(li);}
}
function wrap(r) { const jpg=URL.createObjectURL(r.jpg),tif=URL.createObjectURL(r.tif);urls.push(jpg,tif);return {jpg,tif,w:r.w,h:r.h}; }
function show(key) {
 current=key;$("#empty").hidden=true;$("#out").hidden=false;$("#viewTitle").textContent=tr({it:"Risultato",en:"Result"});
 const tabs=$("#tabs");
 for (const b of [...tabs.children]) if (!results[b.dataset.version]) b.remove();
 for(const k of Object.keys(LABELS))if(results[k]){
  let b=[...tabs.children].find(b=>b.dataset.version===k);
  if(!b){b=document.createElement("button");b.type="button";b.dataset.version=k;b.addEventListener("click",()=>{userChoice=true;show(k);});tabs.append(b);}
  b.textContent=tr(LABELS[k]);b.setAttribute("aria-pressed",String(k===key));
 }
 $("#imgA").src=results.originale.jpg;$("#imgB").src=results[key].jpg;
 $("#cmp").classList.toggle("single",key==="originale");
 $("#cmp").setAttribute("role",key==="originale"?'img':'slider');
 $("#cmp").tabIndex=key==="originale"?-1:0;
 $("#cmp").setAttribute("aria-label",key==="originale"?tr(LABELS.originale):tr({it:"Confronto con lo sviluppo base",en:"Compare with base development"}));
 $("#lblA").textContent=tr(LABELS.originale);$("#lblB").textContent=tr(LABELS[key]);
 $("#note").textContent=tr(NOTES[key]);$("#note").className="note"+(key==="ai"?" ai":"");
 const r=results[key],dl=$("#dl");dl.replaceChildren();
 for(const [format,label]of [['jpg','JPEG'],['tif','TIFF 16 bit']]){
  const a=document.createElement("a");if(!stale)a.href=r[format];else a.setAttribute('aria-disabled','true');a.download=`negativo_${key}${format==='tif'?'_16bit':''}.${format}`;a.textContent=label;if(format==='tif')a.className='tif';dl.append(a);
 }
 $("#meta").textContent=`${r.w} × ${r.h} px`;
 $("#detailPanel").hidden=key==="originale";
 if(key!=="originale"){$("#capA").textContent=tr(LABELS.originale);$("#capB").textContent=tr(LABELS[key]);lensAt(.5,.5);}
 cmp.set(50);
 if(key==='originale')for(const attr of ['aria-valuemin','aria-valuemax','aria-valuenow'])$("#cmp").removeAttribute(attr);
 else{$("#cmp").setAttribute('aria-valuemin','0');$("#cmp").setAttribute('aria-valuemax','100');}
}
function load(src){if(!imgs[src]){imgs[src]=new Image();imgs[src].src=src;}return imgs[src];}
function draw(canvas,src,fx,fy,side){
 const im=load(src),paint=()=>{
  if(!im.naturalWidth||!results.originale)return;
  const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;
  const s=Math.min(side*(im.naturalWidth/results.originale.w),im.naturalWidth,im.naturalHeight);
  const x=Math.min(Math.max(fx*im.naturalWidth-s/2,0),im.naturalWidth-s),y=Math.min(Math.max(fy*im.naturalHeight-s/2,0),im.naturalHeight-s);
  ctx.drawImage(im,x,y,s,s,0,0,canvas.width,canvas.height);
 };im.complete&&im.naturalWidth?paint():im.addEventListener('load',paint,{once:true});
}
function lensAt(fx,fy){if(current==='originale'||!results[current])return;const side=Math.max(24,Math.round(results.originale.w/12));draw($("#lensA"),results.originale.jpg,fx,fy,side);draw($("#lensB"),results[current].jpg,fx,fy,side);}
$("#cmp").addEventListener('pointermove',e=>{
 if(!$("#detailPanel").open||!results.originale)return;
 const im=$("#imgB"),r=im.getBoundingClientRect(),ar=im.naturalWidth/im.naturalHeight||1.5;
 const w=r.width/r.height>ar?r.height*ar:r.width,h=r.width/r.height>ar?r.height:r.width/ar;
 lensAt(Math.min(Math.max((e.clientX-r.left-(r.width-w)/2)/w,0),1),Math.min(Math.max((e.clientY-r.top-(r.height-h)/2)/h,0),1));
});
let lensX=.5,lensY=.5;
$("#lens").addEventListener('keydown',e=>{
 if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(e.key))return;
 e.preventDefault();
 if(e.key==='Home'){lensX=.5;lensY=.5;}
 if(e.key==='ArrowLeft')lensX=Math.max(0,lensX-.1);if(e.key==='ArrowRight')lensX=Math.min(1,lensX+.1);
 if(e.key==='ArrowUp')lensY=Math.max(0,lensY-.1);if(e.key==='ArrowDown')lensY=Math.min(1,lensY+.1);
 lensAt(lensX,lensY);
});
document.addEventListener('langchange',()=>{engineState();if(profiles.length)renderProfiles();previewInput();if(busy)setProgress(lastStage,lastFraction);if(results[current])show(current);if(stale)markDirty();});
engineState();updateControls();
