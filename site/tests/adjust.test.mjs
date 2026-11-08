import { test } from 'node:test';
import assert from 'node:assert/strict';
import { img } from '../src/engine/core.js';
import { applyColorAdjustments, sampleNeutralGains } from '../src/engine/adjust.js';
const image = rgb => img(5,5,3,new Float32Array(Array.from({length:25},()=>rgb).flat()));
const lum = d => d[0]*.2126+d[1]*.7152+d[2]*.0722;
test('identity clones exactly and reset is pristine',()=>{
 const im=image([.12,.35,.72]), before=im.data.slice();
 assert.deepEqual(applyColorAdjustments(im).data,before);
 assert.notEqual(applyColorAdjustments(im).data,im.data);
 applyColorAdjustments(im,{temperature:100,tint:-100});
 assert.deepEqual(im.data,before);
 assert.deepEqual(applyColorAdjustments(im,{gains:[1,1,1]}).data,before);
});
test('warm/cool, tint, gamut mapping preserve luminance',()=>{
 const im=image([.2,.2,.2]);
 const warm=applyColorAdjustments(im,{temperature:100});
 const cool=applyColorAdjustments(im,{temperature:-100});
 assert.ok(warm.data[0]>warm.data[2]); assert.ok(cool.data[0]<cool.data[2]);
 const magenta=applyColorAdjustments(im,{tint:100}); assert.ok(magenta.data[0]>magenta.data[1]);
 for(const rgb of [[0,0,0],[1,1,1],[1,.7,.02],[.01,.9,.02]]) {
  const source=image(rgb), out=applyColorAdjustments(source,{temperature:100,tint:-100,gains:[4,.5,2]});
  assert.ok(out.data.every(v=>Number.isFinite(v)&&v>=0&&v<=1));
  assert.ok(Math.abs(lum(out.data)-lum(source.data))<1e-6);
 }
});
test('median neutral patch removes cast and rejects unsuitable samples',()=>{
 const im=image([.2,.3,.4]); const gains=sampleNeutralGains(im,{x:.5,y:.5});
 const out=applyColorAdjustments(im,{gains}); assert.ok(Math.abs(out.data[0]-out.data[2])<1e-6);
 for(const [rgb,error] of [[[.001,.001,.001],'neutral-too-dark'],[[1,.5,.5],'neutral-clipped'],[[.02,.3,.3],'neutral-extreme-color']]) assert.throws(()=>sampleNeutralGains(image(rgb),{x:.5,y:.5}),new RegExp(error));
 assert.throws(()=>sampleNeutralGains(im,{x:NaN,y:0}),/neutral-invalid-position/);
});
