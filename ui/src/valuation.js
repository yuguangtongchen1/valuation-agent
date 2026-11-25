export async function api(action, params = {}, signal) {
 const post = action === 'oa' || action === 'batch' || action === 'lookup';
 const response = await fetch(`/api/valuation/${action}${post?'':`?${new URLSearchParams(params)}`}`, {
  signal, method:post?'POST':'GET',
  ...(post?{headers:{'Content-Type':'application/json'},body:JSON.stringify(params)}:{})
 });
 if(!response.ok){
  const error=await response.json().catch(()=>null);
  throw new Error(error?.error || '历史证据暂不可用，请稍后重试。');
 }
 const value=await response.json();
 if(value?.error)throw new Error(value.error);
 return value;
}

export const lookupQuery = line => ({
 spec_status:line.spec_review?.status==='source_conflict'?'source_conflict':line.spec_completeness?.status,
 source_url:line.source_url,source_token:line.source_token,source_sha256:line.source_sha256||line.source_evidence?.sha256,quotation_family_id:line.quotation_family_id,economic_purchase_group:line.economic_purchase_group,comparison_components:line.comparison_components,
 name:line.name,retrieval_name:line.retrieval_name,quantity:String(line.quantity??''),exclude:line.sourceRecordId||'',unit:line.unit||'',
 currency:line.currency||'CNY',model:line.model||'',spec:line.spec??line.dimensions??'',configuration:line.configuration||'',
 dimension_unit:line.dimensionUnit??(line.spec==null?'mm':''),
 description:(line.description||'').slice(0,6000)
});

export function billingText(row) {
 const factor=row.billing_multiplier||row.price_multiplier;
 const label=row.source_attributes?.rate_multiplier_label;
 return [...new Set([row.reference_rate_label,row.period,row.billing_period,
  factor&&Number(factor)!==1?(label?`计费 ${factor} ${label}`:`计费倍数 ×${factor}`):null
 ].filter(Boolean))].join(' · ');
}

// A package total has no per-item unit price, even when its source has a quantity.
export function referencePrice(row) {
 const componentNote=row.comparison_role==='component'&&row.price_comparison_eligible===false&&row.reference_price_type==='package_total';
 const packageTotal=row.reference_price_type==='package_total'||row.kind==='whole_scope_quote';
 const amount=packageTotal?(row.reference_total??row.subtotal):row.unit_price;
 const cny=packageTotal?(row.reference_total_cny_yuan??row.subtotal_cny_yuan):row.unit_price_cny_yuan;
 return {amount,cny,currency:row.currency,unit:componentNote?'子件注记':packageTotal?'整包':(row.reference_rate_unit||row.unit||''),packageTotal,componentNote};
}

export function quotationVariantLabel(row) {
 const value=row.quotation_variant_name||row.quote_variant_name||row.price_variant_label
  ||row.quote_variant?.name||row.quotation_variant?.name||row.parent_quote_variant?.quotation_variant_name
  ||row.parent_quote_variant?.name||row.source_attributes?.quotation_variant_name;
 return typeof value==='string'?value:'';
}

export function saveExcel(bytes, filename) {
 const blob=new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
 const url=URL.createObjectURL(blob);
 const link=document.createElement('a');
 link.href=url;
 link.download=filename;
 link.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
}

const moneyCell=value=>value!=null&&value!==''&&Number.isFinite(Number(value))?Number(value):null;

export async function comparisonWorkbook(quote, lookup = api, observed = {}) {
 const {default:ExcelJS}=await import('exceljs');
 const results=await lookup('batch',quote.lines.map(lookupQuery));
 if(!Array.isArray(results)||results.length!==quote.lines.length)throw new Error('比价结果与报价行数量不一致。');
 const book=new ExcelJS.Workbook();
 const current=book.addWorksheet('当前报价');
 const references=book.addWorksheet('历史参考');
 current.addRow(['项目','源行','物料','规格','数量','单位','币种','单价（人民币元）','小计（人民币元）','历史报价条数','关联台账条数','状态','型号','组合方式','子件参考条数','整包旁证条数','当前归类','同细类待核记录','工艺旁证条数']);
 references.addRow(['当前源行','当前物料','历史项目或台账','供应商','匹配类型','规格 / 型号','币种','单位','单价（人民币元）','差异','合同','原件位置','原件链接','匹配依据','参考子件','当前子件数量','当前子件单位','当前归类','历史归类','价格类型','范围 / 子件参考金额（人民币元）','报价版本','独立样本标识']);
 for(const [i,line] of quote.lines.entries()){
  const result=results[i];
  const matches=result.references;
  const history=matches.filter(r=>r.kind!=='ledger_match');
  const priced=history.length;
  const partial=matches.filter(r=>r.component_name).length;
  const bundles=history.filter(r=>referencePrice(r).packageTotal||r.classification?.bundle_reference).length;
  const process=matches.filter(r=>r.classification?.process_reference).length;
  const standalone=history.filter(r=>!r.component_name&&!referencePrice(r).packageTotal&&!r.classification?.bundle_reference&&!r.classification?.process_reference).length;
  const status=standalone?'有历史参考':partial?'仅部分子件有参考':bundles?'有整包金额参考':process?'仅有工艺旁证':'本次导出未找到已核分项单价';
  current.addRow([quote.projectName,line.row,line.name,line.spec??line.dimensions,moneyCell(line.quantity),line.unit,'CNY',(!line.currency||line.currency==='CNY')?moneyCell(line.unitPrice):null,(!line.currency||line.currency==='CNY')?moneyCell(line.derivedAmount):null,standalone,matches.length-priced,status,line.model,line.configuration,partial,bundles,result.query_classification?.join(' › '),result.pending_price_sources?.join('、'),process]);
  for(const row of matches){
   const view=referencePrice(row);
   references.addRow(row.kind==='ledger_match'
    ?[line.row,line.name,row.value,null,'关联台账，无分项单价',null,null,null,null,null,null,`${row.sheet} ${row.address}`,row.url]
    :[line.row,line.name,row.project,row.supplier,row.component_name?`部分参考 · ${row.match_kind}`:row.match_kind,[...new Set([row.spec,row.model].filter(Boolean))].join(' / '),'CNY',view.packageTotal?'':view.unit,view.packageTotal?null:moneyCell(view.cny??(row.currency==='CNY'?view.amount:null)),row.differences?.join('、'),row.contract_id,row.source_locator,row.source_url,row.match_reason,row.component_name,row.component_quantity,row.component_unit,row.classification?.current?.join(' › '),row.classification?.historical?.join(' › '),view.componentNote?'子件金额注记':view.packageTotal?'整包金额':(row.reference_rate_label||'分项单价'),view.packageTotal?moneyCell(view.cny??(row.currency==='CNY'?view.amount:null)):null,quotationVariantLabel(row),row.independent_sample_key||'']);
  }
 }
 for(const sheet of [current,references]){
  sheet.views=[{state:'frozen',ySplit:1}];
  sheet.getRow(1).font={bold:true};
  sheet.columns.forEach(col=>{col.width=20;});
  sheet.getColumn(3).width=36;
 }
 return book.xlsx.writeBuffer();
}
