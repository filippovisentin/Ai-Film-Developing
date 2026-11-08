import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detailTransform } from '../src/js/view-geometry.js';

test('100% maps selected image pixels to CSS pixels; AI reference stays aligned',()=>{
 const t=detailTransform(4000,3000,400,320,1,[.6,.4]);
 assert.equal(t.scale,1);assert.equal(t.width,4000);assert.equal(t.height,3000);
 // At 4x AI, a source feature at 60%, 40% has the same viewport position.
 for(const [w,h] of [[1000,750],[4000,3000]]){
  assert.equal(.6*w*(t.width/w)+t.x,200);
  assert.equal(.4*h*(t.height/h)+t.y,160);
 }
});
test('pan clamps at edges, fit centres smaller images, 200% preserves the centre',()=>{
 const edge=detailTransform(1000,800,400,320,1,[0,1]);
 assert.deepEqual(edge.center,[.2,.8]);assert.equal(edge.x,0);assert.equal(edge.y,-480);
 const fit=detailTransform(1000,800,400,320,'fit',[0,1]);assert.deepEqual(fit.center,[.5,.5]);assert.equal(fit.scale,.4);assert.equal(fit.x,0);assert.equal(fit.y,0);
 const zoom=detailTransform(1000,800,400,320,2,[.6,.4]);assert.deepEqual(zoom.center,[.6,.4]);assert.equal(zoom.width,2000);
 const small=detailTransform(100,80,400,320,1,[0,1]);assert.deepEqual(small.center,[.5,.5]);assert.equal(small.x,150);
});
