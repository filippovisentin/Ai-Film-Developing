/** One shared viewport in selected-image pixels, also used by the reference view. */
export function detailTransform(w, h, vw, vh, zoom, center) {
 const scale=zoom==='fit'?Math.min(vw/w,vh/h):Number(zoom);
 const clamp=(p,size,view)=>size<=view?.5:Math.max(view/(2*size),Math.min(1-view/(2*size),p));
 const x=clamp(center[0],w*scale,vw),y=clamp(center[1],h*scale,vh);
 return {scale,center:[x,y],x:vw/2-x*w*scale,y:vh/2-y*h*scale,width:w*scale,height:h*scale};
}
