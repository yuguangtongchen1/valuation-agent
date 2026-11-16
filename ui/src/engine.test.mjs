import assert from 'node:assert/strict';
import {test} from 'node:test';
import {evidenceCounts} from './engine.js';

test('legacy handoff rows without project identifiers remain countable',()=>{
 const lines=[
  {quoteId:'old',supplierName:'A'},
  {quoteId:'old',projectId:null,supplierName:'A'},
  {quoteId:'new',projectId:'unmapped:codex:new',supplierName:'B'},
  {quoteId:'linked',projectId:'project-1',supplierName:'B'},
 ];
 const before=JSON.stringify(lines);
 assert.deepEqual(evidenceCounts(lines),{projects:1,unmappedSources:2,suppliers:2,quotes:3,lines:4});
 assert.equal(JSON.stringify(lines),before);
});
