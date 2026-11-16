import test from 'node:test';
import assert from 'node:assert/strict';
import {clampZoom,fitImage,zoomScroll} from './image-zoom.mjs';
test('portrait and landscape fit without distorted aspect ratio',()=>{
 assert.deepEqual(fitImage(1000,2000,900,600),{width:300,height:600});
 assert.deepEqual(fitImage(2000,1000,900,600),{width:900,height:450});
});
test('zoom preserves pointer position including centered margins',()=>{
 assert.equal(zoomScroll({pointer:500,scroll:0,viewportSize:900,baseSize:300,oldZoom:1,newZoom:4}),300);
 assert.equal(zoomScroll({pointer:450,scroll:0,viewportSize:900,baseSize:900,oldZoom:1,newZoom:2}),450);
});
test('fit restores origin and zoom remains bounded',()=>{
 assert.equal(zoomScroll({pointer:450,scroll:450,viewportSize:900,baseSize:900,oldZoom:2,newZoom:1}),0);
 assert.equal(clampZoom(.2),1); assert.equal(clampZoom(8),4);
});
