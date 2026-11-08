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

test('exposure uses linear stops, keeps ratios and never changes the source',()=>{
 const im=image([.05,.1,.2]),before=im.data.slice();
 for(const exposure of [-1,1]){
  const out=applyColorAdjustments(im,{exposure});
  for(let k=0;k<3;k++)assert.ok(Math.abs(out.data[k]-im.data[k]*2**exposure)<1e-6);
 }
 assert.deepEqual(im.data,before);
 assert.deepEqual(applyColorAdjustments(im,{exposure:0,contrast:0}).data,before);
});

test('contrast pivots at middle gray with monotonic finite tone and neutral blacks',()=>{
 for(const contrast of [-100,100]){
  const mid=applyColorAdjustments(image([.18,.18,.18]),{contrast});
  assert.ok(Math.abs(mid.data[0]-.18)<1e-6);
  let previous=-1;
  for(const value of [0,.001,.01,.09,.18,.4,.8,1]){
   const out=applyColorAdjustments(image([value,value,value]),{contrast,exposure:3});
   assert.ok(out.data.every(v=>Number.isFinite(v)&&v>=0&&v<=1));
   assert.ok(out.data[0]>=previous);previous=out.data[0];
   assert.ok(Math.abs(out.data[0]-out.data[2])<1e-6);
  }
 }
 assert.ok(applyColorAdjustments(image([.09,.09,.09]),{contrast:100}).data[0]<.09);
 assert.ok(applyColorAdjustments(image([.4,.4,.4]),{contrast:100}).data[0]>.4);
 for(const settings of [{exposure:NaN},{exposure:3.1},{contrast:Infinity},{contrast:-101}])assert.throws(()=>applyColorAdjustments(image([.2,.3,.4]),settings),/adjust-invalid-settings/);
});
