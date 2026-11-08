import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { img } from '../src/engine/core.js';
import { validateManualCorners, manualCornersToPixels } from '../src/engine/geometry.js';
import { developFrame } from '../src/engine/pipeline.js';
const require=createRequire(import.meta.url);
const {cv}=await new Promise(resolve=>{const cv=require('@techstark/opencv-js');const wait=()=>cv.Mat?resolve({cv}):setTimeout(wait,20);wait();});
test('manual quadrilateral rejects crossing, degenerate and nonfinite coordinates',()=>{
 assert.deepEqual(validateManualCorners([[0,0],[1,0],[1,1],[0,1]]),[[0,0],[1,0],[1,1],[0,1]]);
 for(const q of [[[0,0],[1,1],[1,0],[0,1]],[[0,0],[0,0],[1,1],[0,1]],[[NaN,0],[1,0],[1,1],[0,1]],[[0,0],[2,0],[1,1],[0,1]]]) assert.throws(()=>validateManualCorners(q),/manual-crop-/);
 assert.throws(()=>manualCornersToPixels([[0,0],[1,0],[1,1],[0,1]],2,2),/too-small/);
});
test('manual crop keeps measured dimensions, dark borders and bypasses auto aspect snap',()=>{
 const im=img(101,67,3);im.data.fill(.3);
 for(let x=0;x<im.w;x++) for(let k=0;k<3;k++) im.data[x*3+k]=0;
 const q=[[0,0],[1,0],[1,1],[0,1]];
 const result=developFrame(cv,im,{profile:{type:'slide', color_matrix:[[1,0,0],[0,1,0],[0,0,1]], print_contrast:1},manualCorners:q});
 assert.equal(result.positive.w,100);assert.equal(result.positive.h,66);
 assert.equal(result.warnings.length,0);
});
