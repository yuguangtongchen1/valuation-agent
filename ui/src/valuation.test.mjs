import assert from 'node:assert/strict';
import {test} from 'node:test';
import {lookupQuery,comparisonWorkbook} from './valuation.js';
test('source conflict survives lookup mapping without sending review evidence',()=>{
 const query=lookupQuery({name:'环形灯',spec:'3500mm',spec_review:{status:'source_conflict',evidence:'private source note'},spec_completeness:{status:'provided'}});
 assert.equal(query.spec_status,'source_conflict');
 assert.equal(query.spec,'3500mm');
 assert.equal(JSON.stringify(query).includes('private source note'),false);
});
test('completeness conflict is preserved for normalized imported rows',()=>{
 assert.equal(lookupQuery({name:'环形灯',spec_completeness:{status:'source_conflict'}}).spec_status,'source_conflict');
});

test('export uses the fresh batch rather than stale displayed references',async()=>{
 const {default:ExcelJS}=await import('exceljs');
 const quote={projectName:'test',lines:[{id:'r',row:1,name:'施工图',quantity:1,unit:'项',unitPrice:100,derivedAmount:100}]};
 const fresh={references:[]};
 const bytes=await comparisonWorkbook(quote,async()=>[fresh],{r:{references:[{kind:'ledger_match',value:'stale'}]}});
 const book=new ExcelJS.Workbook();await book.xlsx.load(bytes);
 assert.equal(book.getWorksheet('历史参考').rowCount,1);
 assert.equal(book.getWorksheet('当前报价').getCell('K2').value,0);
});
