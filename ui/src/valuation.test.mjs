import assert from 'node:assert/strict';
import {test} from 'node:test';
import {lookupQuery} from './valuation.js';
test('source conflict survives lookup mapping without sending review evidence',()=>{
 const query=lookupQuery({name:'环形灯',spec:'3500mm',spec_review:{status:'source_conflict',evidence:'private source note'},spec_completeness:{status:'provided'}});
 assert.equal(query.spec_status,'source_conflict');
 assert.equal(query.spec,'3500mm');
 assert.equal(JSON.stringify(query).includes('private source note'),false);
});
test('completeness conflict is preserved for normalized imported rows',()=>{
 assert.equal(lookupQuery({name:'环形灯',spec_completeness:{status:'source_conflict'}}).spec_status,'source_conflict');
});
