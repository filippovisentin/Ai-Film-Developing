import { createDetailViewer } from "./detail-viewer.js";
import { createCropEditor } from "./crop-editor.js";
import { makeCompare, tr, lang } from "./common.js";

const $ = (s) => document.querySelector(s), files = {}, names = {}, urls = [], sampleFiles = new Set();
let profiles = [], sr = 2, results = {}, current = "originale", busy = false, loadingSample = false, ready = false, userChoice = false, stale = false;
let sourceId=0, requestId=0, manualCorners=null, edited={}, colorRevision=0, pendingEdit=0, editTimer, picking=false, point=[.5,.5];
const defaultSettings=()=>({exposure:0,contrast:0,temperature:0,tint:0,gains:[1,1,1]});
let settings=defaultSettings(),adjustmentPreview=null;
const adjustmentKeys=["exposure","contrast","temperature","tint"];
const detailViewer=createDetailViewer($("#detailPanel"));
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
 $("#cropOpen").disabled=busy||loadingSample||!files.negativo;
 $("#colorPanel").hidden=!results.originale;
 $("#colorControls").disabled=busy||stale;
 $(".result").setAttribute("aria-busy", String(busy));
}
function engineState() {
 $("#engineState").className = "engine-state" + (ready ? " ready" : "");
 $("#engineState").textContent = tr(ready ? { it: "Elaborazione locale pronta", en: "Local processing ready" } : { it: "Elaborazione locale", en: "Local processing" });
}
worker.onmessage = ({ data: m }) => {
 if(m.sourceId!==undefined && m.sourceId!==sourceId)return;
 if(handleEdit(m))return;
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
 sourceId++;detailViewer.reset();clearPreview();$("#comparisonSource").value="base";clearTimeout(editTimer);pendingEdit=0;edited={};settings=defaultSettings();colorRevision++;stopPicking();syncColorInputs();
 results = {}; userChoice = false; stale = false; urls.splice(0).forEach(u=>URL.revokeObjectURL(u));
 $("#out").hidden = true; $("#empty").hidden = false; $("#warns").replaceChildren();
 $("#viewerStatus").textContent = ""; $("#viewTitle").textContent = tr({it:"Anteprima",en:"Preview"});
}
function previewInput() {
 $("#previewCmp").hidden = !!files.negativo; $("#inputStage").hidden = !files.negativo;
 $("#previewCaption").textContent = files.negativo ? names.negativo : tr({it:"Esempio incluso: Fuji 100, Tokyo 1994.",en:"Included sample: Fuji 100, Tokyo 1994."});
}
function markDirty() {
 if (!Object.keys(results).length || busy) return;
 stale = true;stopPicking();updateControls();
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
 if (key==="negativo") { manualCorners=null;cropLabel();resetResults(); $("#inputPreview").hidden=false;$("#inputUnreadable").hidden=true; if (file) $("#inputPreview").src=im.src; else $("#inputPreview").removeAttribute("src"); previewInput(); }
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
 worker.postMessage({type:"develop",sourceId,manualCorners,lang:lang(),profile:profiles.find(p=>p.id===$("#profilo").value),files:{negativo:files.negativo,luce:files.luce||null,bordo:files.bordo||null},migliora:$("#migliora").checked,ai:$("#ai").checked?sr:0});
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
function show(key,resetCompare=true) {
 current=key;$("#empty").hidden=true;$("#out").hidden=false;$("#viewTitle").textContent=tr({it:"Risultato",en:"Result"});
 const tabs=$("#tabs");
 for (const b of [...tabs.children]) if (!results[b.dataset.version]) b.remove();
 for(const k of Object.keys(LABELS))if(results[k]){
  let b=[...tabs.children].find(b=>b.dataset.version===k);
  if(!b){b=document.createElement("button");b.type="button";b.dataset.version=k;b.addEventListener("click",()=>{stopPicking();userChoice=true;show(k);});tabs.append(b);}
  b.textContent=tr(LABELS[k]);b.setAttribute("aria-pressed",String(k===key));
 }
 const changed=hasColor(), preview=adjustmentPreview?.key===key&&adjustmentPreview.revision===colorRevision?adjustmentPreview:null;
 const display=edited[key]?.revision===colorRevision?edited[key]:preview||results[key], comparison=changed||key!=="originale";
 const previous=changed&&$("#comparisonSource").value==="previous",reference=previous?results[key]:results.originale;
 $("#comparisonChoice").hidden=!changed||key==="originale";
 for(const option of $("#comparisonSource").options)option.textContent=option.dataset[lang()];
 $("#imgA").src=reference.jpg;$("#imgB").src=display.jpg;
 $("#cmp").classList.toggle("single",!comparison);
 $("#cmp").setAttribute("role",!comparison?'img':'slider');
 $("#cmp").tabIndex=!comparison?-1:0;
 $("#cmp").setAttribute("aria-label",previous?tr({it:"Confronto prima e dopo le regolazioni",en:"Compare before and after adjustments"}):comparison?tr({it:"Confronto con lo sviluppo base",en:"Compare with base development"}):tr(LABELS.originale));
 $("#lblA").textContent=previous?tr({it:"Prima delle regolazioni",en:"Before adjustments"}):tr(LABELS.originale);$("#lblB").textContent=changed?tr({it:"Versione regolata",en:"Adjusted version"}):tr(LABELS[key]);
 $("#imgA").alt=$("#lblA").textContent;$("#imgB").alt=$("#lblB").textContent;
 $("#note").textContent=changed?(previous?tr({it:"Trascina il cursore per confrontare prima e dopo le regolazioni.",en:"Drag the handle to compare before and after adjustments."}):tr({it:"Trascina il cursore per confrontare la versione regolata con lo sviluppo base.",en:"Drag the handle to compare your adjusted version with base development."})):tr(NOTES[key]);
 if(changed&&key==="ai")$("#note").textContent+=' '+tr({it:"L’AI può inventare dettagli.",en:"AI may invent details."});$("#note").className="note"+(key==="ai"?" ai":"");
 const r=display,dl=$("#dl");dl.replaceChildren();
 for(const [format,label]of [['jpg','JPEG'],['tif','TIFF 16 bit']]){
  const a=document.createElement("a");if(!stale && (!changed||edited[key]?.revision===colorRevision))a.href=r[format];else a.setAttribute('aria-disabled','true');a.download=`negativo_${key}${format==='tif'?'_16bit':''}.${format}`;a.textContent=label;if(format==='tif')a.className='tif';dl.append(a);
 }
 $("#meta").textContent=`${r.w} × ${r.h} px`;
 $("#detailPanel").hidden=false;
 detailViewer.update({left:reference.jpg,right:display.jpg,w:display.w,h:display.h,leftLabel:$("#lblA").textContent,rightLabel:tr(LABELS[key])+(changed?tr({it:" · regolata",en:" · adjusted"}):"")});
 if(resetCompare)cmp.set(50);
 if(!comparison)for(const attr of ['aria-valuemin','aria-valuemax','aria-valuenow'])$("#cmp").removeAttribute(attr);
 else{$("#cmp").setAttribute('aria-valuenow',String(parseFloat($("#cmp").style.getPropertyValue('--pos'))||0));$("#cmp").setAttribute('aria-valuemin','0');$("#cmp").setAttribute('aria-valuemax','100');}
 updateControls();if(changed&&!pendingEdit&&!picking&&edited[key]?.revision!==colorRevision)requestAdjustment();
}
$("#comparisonSource").addEventListener('change',()=>show(current,false));
$("#openDetail").addEventListener('click',()=>{const panel=$("#detailPanel");panel.open=true;panel.querySelector('[data-zoom-level="1"]').click();panel.scrollIntoView({block:'nearest',behavior:'instant'});$("#lensB").focus({preventScroll:true});});

document.addEventListener('langchange',()=>{stopPicking();cropLabel();engineState();if(profiles.length)renderProfiles();previewInput();if(busy)setProgress(lastStage,lastFraction);if(results[current])show(current);if(stale)markDirty();});
const cropEditor=createCropEditor(corners=>{manualCorners=corners;cropLabel();markDirty();});
function cropLabel(){$('#cropState').textContent=tr(manualCorners?{it:'Ritaglio manuale. Verrà usato al prossimo sviluppo.',en:'Manual crop. Used on the next development.'}:{it:'Riconoscimento automatico del fotogramma.',en:'Automatic frame detection.'});}
$('#cropOpen').addEventListener('click',()=>{cropEditor.open(files.negativo,manualCorners);if(!manualCorners)worker.postMessage({type:'detect-crop',sourceId,requestId:++requestId,file:files.negativo});});
function hasColor(){return adjustmentKeys.some(k=>settings[k]!==0)||settings.gains.some(v=>v!==1);}
function adjustmentValue(k){const value=settings[k],number=k==='exposure'?Number(value.toFixed(2)):value;return (value>0?'+':'')+number+(k==='exposure'?' EV':'');}
function clearPreview(){if(adjustmentPreview){URL.revokeObjectURL(adjustmentPreview.jpg);adjustmentPreview=null;}}
function syncColorInputs(){for(const k of adjustmentKeys){$('#'+k).value=settings[k];$('#'+k+'Value').textContent=adjustmentValue(k);$('#'+k).setAttribute('aria-valuetext',adjustmentValue(k));}$('#colorStatus').textContent='';}
function stopPicking(){picking=false;$('#cmp').dataset.pickColor='false';$('#neutralMarker').hidden=true;$('#neutralPick').setAttribute('aria-pressed','false');}
function requestAdjustment(){clearTimeout(editTimer);if(busy||stale||!results[current]||!hasColor())return;const id=++requestId;pendingEdit=id;$('#colorStatus').textContent=tr({it:'Aggiornamento anteprima…',en:'Updating preview…'});worker.postMessage({type:'adjust',sourceId,requestId:id,key:current,settings});}
function discardEdits(){clearPreview();for(const r of Object.values(edited))for(const key of ["jpg","tif"]){URL.revokeObjectURL(r[key]);const i=urls.indexOf(r[key]);if(i>=0)urls.splice(i,1);}edited={};}
function changeColor(){pendingEdit=0;discardEdits();colorRevision++;stopPicking();syncColorInputs();show(current,false);}
for(const k of adjustmentKeys)$('#'+k).addEventListener('input',()=>{stopPicking();settings[k]=Number($('#'+k).value);pendingEdit=0;discardEdits();colorRevision++;$('#'+k+'Value').textContent=adjustmentValue(k);$('#'+k).setAttribute('aria-valuetext',adjustmentValue(k));clearTimeout(editTimer);document.querySelectorAll('#dl a').forEach(a=>{a.removeAttribute('href');a.setAttribute('aria-disabled','true');});editTimer=setTimeout(()=>{if(!hasColor())show(current,false);else requestAdjustment();},180);});
$('#colorReset').addEventListener('click',()=>{clearTimeout(editTimer);settings=defaultSettings();changeColor();});
function marker(){const r=imageRect();$('#neutralMarker').style.left=(r.left-r.outer.left+point[0]*r.w)+'px';$('#neutralMarker').style.top=(r.top-r.outer.top+point[1]*r.h)+'px';}
function imageRect(){const r=$('#imgB').getBoundingClientRect(),im=$('#imgB'),s=Math.min(r.width/im.naturalWidth,r.height/im.naturalHeight),w=im.naturalWidth*s,h=im.naturalHeight*s;return {outer:r,left:r.left+(r.width-w)/2,top:r.top+(r.height-h)/2,w,h};}
function pick(){if(!picking)return;stopPicking();pendingEdit=++requestId;$('#colorStatus').textContent=tr({it:'Campionamento del punto neutro…',en:'Sampling neutral point…'});worker.postMessage({type:'neutral',sourceId,requestId:pendingEdit,x:point[0],y:point[1]});show(current,false);}
$('#neutralPick').addEventListener('click',()=>{if(picking){stopPicking();show(current,false);return;}clearTimeout(editTimer);pendingEdit=0;picking=true;point=[.5,.5];$('#cmp').dataset.pickColor='true';$('#cmp').setAttribute('role','group');$('#cmp').setAttribute('aria-label',tr({it:'Punto neutro: frecce per spostare, Invio per scegliere, Esc per annullare.',en:'Neutral point: arrows to move, Enter to pick, Escape to cancel.'}));$('#cmp').tabIndex=0;$('#neutralMarker').hidden=false;$('#neutralPick').setAttribute('aria-pressed','true');$('#colorStatus').textContent=tr({it:'Scegli una zona grigia, non troppo chiara o scura. Esc annulla.',en:'Pick a grey area, avoiding highlights and shadows. Escape cancels.'});marker();$('#cmp').focus();});
$('#cmp').addEventListener('click',e=>{if(!picking)return;const r=imageRect(),x=(e.clientX-r.left)/r.w,y=(e.clientY-r.top)/r.h;if(x<0||x>1||y<0||y>1)return;point=[x,y];pick();});
$('#cmp').addEventListener('keydown',e=>{if(!picking)return;if(e.key==='Escape'){e.preventDefault();stopPicking();$('#colorStatus').textContent='';show(current,false);$('#neutralPick').focus();return;}if(e.key==='Enter'){e.preventDefault();pick();return;}if(!e.key.startsWith('Arrow'))return;e.preventDefault();const step=e.shiftKey?.001:.01;point[0]=Math.max(0,Math.min(1,point[0]+(e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0)));point[1]=Math.max(0,Math.min(1,point[1]+(e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0)));marker();});
function handleEdit(m){
 if(m.type==='crop-detected'){cropEditor.detected(m.corners);return true;}
 if(m.type==='adjust-preview'){if(m.requestId!==pendingEdit)return true;clearPreview();adjustmentPreview={jpg:URL.createObjectURL(m.jpg),w:m.w,h:m.h,key:m.key,revision:colorRevision};if(current===m.key)show(current,false);return true;}
 if(m.type==='adjusted'){if(m.requestId!==pendingEdit)return true;pendingEdit=0;edited[m.key]={...wrap(m.result),revision:colorRevision};$('#colorStatus').textContent=tr({it:'Regolazioni aggiornate. I download includono le modifiche.',en:'Adjustments updated. Downloads include your edits.'});show(current,false);clearPreview();return true;}
 if(m.type==='neutral-picked'){if(m.requestId!==pendingEdit)return true;pendingEdit=0;settings={...settings,temperature:0,tint:0,gains:m.gains};changeColor();return true;}
 if(m.type==='edit-error'){if(m.requestId!==pendingEdit)return true;pendingEdit=0;$('#colorStatus').textContent=tr({it:'Impossibile correggere questo punto. Scegli un grigio medio, senza riflessi o ombre profonde, oppure ripristina i colori.',en:'Could not adjust this point. Pick a mid grey without glare or deep shadows, or reset colours.'});return true;}
 return false;
}
cropLabel();engineState();updateControls();
