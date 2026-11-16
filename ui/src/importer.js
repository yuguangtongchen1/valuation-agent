import ExcelJS from 'exceljs';
import {parseQuote,text} from './engine.js';

function cellValue(cell, cached = false){
 const value=cell.value;
 if(value==null)return '';
 if(typeof value!=='object')return value;
 if(value.formula||value.sharedFormula){
  if(cached)return typeof value.result==='number'?value.result:'';
  if(!cell.formula)throw Error('共享公式无法展开。');
  return '='+cell.formula;
 }
 if(value.richText)return value.richText.map(part=>part.text).join('');
 if(value.text)return value.text;
 if(value instanceof Date)return value.toISOString();
 return '';
}

const template='序号|区域|物料|工艺描述|尺寸mm|数量|单位|单价|小计';
const aliases={
 name:/^(物料|物料名称|材料名称|设备名称|项目名称|产品名称|服务名称|名称|品名|name|item|itemname)$/,
 group:/^(类别|区域|分类|模块|class|classes|category)$/,
 description:/^(内容|工艺描述|工艺说明|说明|描述|内容说明|description)$/,
 spec:/^(规格|规格型号|产品参数|技术参数|spec|specification)$/,
 dimensions:/^(尺寸|尺寸mm|尺寸cm|尺寸m|外形尺寸|dimensions|size)$/,
 power:/^(功率|额定功率|功率说明|功率w|功率kw|power|ratedpower)$/,
 voltage:/^(电压|额定电压|电压v|voltage|ratedvoltage)$/,
 model:/^(型号|设备型号|产品型号|model|modelnumber)$/,
 configuration:/^(组合|组合方式|组合模式|配置|配置明细|套装内容|包含项|configuration|packagecontents)$/,
 quantity:/^(数量|工程量|qty|quantity)$/,
 unit:/^(单位|计量单位|unit)$/,
 price:/^(单价|含税单价|不含税单价|未税单价|price|unitprice)$/,
 currency:/^(币种|原币|货币|currency)$/,
 tax:/^(税口径|价格口径|含税口径|taxbasis)$/,
 amount:/^(小计|合计|金额|费用|总价|cost|amount|subtotal)$/,
 remark:/^(备注|remark|remarks)$/
};
const summary=/^(?:内容|费用|项目|报价|含税|不含税|未税|税前)?(?:小计|合计|总计|总额|总价|折扣|优惠|税点|税费)|^(?:subtotal|total|grandtotal)$/i;
const taxBasis=value=>/不含税|未税|税前|exclusive/i.test(value)?'exclusive':/含税|税后|inclusive/i.test(value)?'inclusive':undefined;
const currencyCode=value=>{
 const code=value.toUpperCase().match(/\b(CNY|RMB|USD|HKD|EUR|JPY|GBP|SGD|AUD|CAD)\b/)?.[1];
 return code==='RMB'?'CNY':code||Object.entries({人民币:'CNY',港币:'HKD',港元:'HKD',美元:'USD',欧元:'EUR',日元:'JPY',英镑:'GBP',新加坡元:'SGD'}).find(([term])=>value.includes(term))?.[1];
};
function headerFor(sheet){
 for(let n=1;n<=Math.min(sheet.rowCount,40);n++){
  const row=sheet.getRow(n);
  const isTemplate=Array.from({length:9},(_,i)=>text(cellValue(row.getCell(i+1)))).join('|')===template;
  const columns={};
  for(let i=1;i<=Math.min(row.cellCount,60);i++){
   const cell=row.getCell(i);
   if(cell.isMerged&&cell.master.address!==cell.address)continue;
   const tokens=text(cellValue(cell,true)).normalize('NFKC').toLowerCase().replace(/\s+/g,'').split('/').map(x=>x.replace(/\([^)]*\)$/,''));
   for(const [field,pattern] of Object.entries(aliases)){
    if(!columns[field]&&tokens.some(token=>pattern.test(token))){columns[field]=i;break;}
   }
  }
  if(isTemplate)return {n,columns,template:true};
  if(columns.name&&(columns.quantity||columns.unit)&&(columns.price||columns.amount))return {n,columns};
 }
 return null;
}

function priceContext(sheet,{n,columns},row){
 const read=(number,key)=>columns[key]?text(cellValue(sheet.getRow(number).getCell(columns[key]),true)):'';
 const heading=read(n,'price').normalize('NFKC');
 return {currency:currencyCode(read(row,'currency'))||currencyCode(heading),
  taxBasis:taxBasis(read(row,'tax'))||taxBasis(heading)};
}

export function normalizeMoneyNumber(value,heading=''){
 const raw=text(value).normalize('NFKC').trim();
 const match=raw.replace(/,/g,'').match(/^[¥￥]?([+-]?\d+(?:\.\d+)?)\s*(?:人民币\s*)?(万元|元)?$/);
 if(!match)return value;
 const unit=match[2]||(/万元/.test(heading)?'万元':'元');
 return Number(match[1])*(unit==='万元'?10000:1);
}

function genericQuote(sheet,header,filename,id,meta){
 const {columns,n}=header;
 const rows=[],sourceRows=[],details=new Map();
 const headerText=key=>columns[key]?text(cellValue(sheet.getRow(n).getCell(columns[key]))).normalize('NFKC').toLowerCase():'';
 const dimensionUnit=headerText('dimensions').match(/(?:mm|cm|m)\)?$/)?.[0]?.replace(/\)$/,'')||'';
 const powerUnit=headerText('power').match(/(?:kw|w|千瓦|瓦)\)?$/)?.[0]?.replace(/\)$/,'');
 const voltageUnit=headerText('voltage').match(/(?:v|伏)\)?$/)?.[0]?.replace(/\)$/,'');
 for(let r=n+1;r<=sheet.rowCount;r++){
  const row=sheet.getRow(r);
  const read=key=>columns[key]?cellValue(row.getCell(columns[key]),true):'';
  const numeric=key=>{
   const raw=read(key);
   const value=['price','amount'].includes(key)?normalizeMoneyNumber(raw,headerText(key)):raw;
   return typeof value==='string'&&/^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$/.test(value.trim())
    ?value.trim().replace(/,/g,''):value;
  };
  const name=text(read('name')).trim();
  if(!name||summary.test(name)||![numeric('price'),numeric('amount')].some(v=>v!==''&&Number.isFinite(Number(v))))continue;
  const measurement=(key,unit)=>{
   const value=text(read(key)).trim();
   return /^\d+(?:\.\d+)?$/.test(value)&&unit?`${value} ${unit}`:value;
  };
  const model=text(read('model')).trim(),configuration=text(read('configuration')).trim();
  const dimensions=text(read('dimensions')).trim();
  const spec=[text(read('spec')).trim(),dimensions].filter(Boolean).join('；');
  const power=measurement('power',powerUnit);
  const voltage=measurement('voltage',voltageUnit);
  const description=[read('description'),configuration,power&&`功率 ${power}`,voltage&&`电压 ${voltage}`].filter(Boolean).join(' · ');
  details.set(r,{model,configuration,spec,dimensionUnit,...priceContext(sheet,header,r),
   moneyNormalization:{unit:'元',price:{raw:read('price'),header:headerText('price'),value:numeric('price')},amount:{raw:read('amount'),header:headerText('amount'),value:numeric('amount')}}});
  const values=[rows.length+1,read('group'),name,description,[model,spec].filter(Boolean).join(' / '),numeric('quantity'),read('unit'),numeric('price'),numeric('amount'),read('remark')];
  rows.push({row:r,values});
  sourceRows.push({row:r,values:Array.from({length:Math.min(row.cellCount,60)},(_,i)=>cellValue(row.getCell(i+1)))});
 }
 if(!rows.length)throw Error('找到了报价表头，但没有可读取的分项价格。请检查金额列或公式缓存。');
 const heading=text(cellValue(sheet.getCell('A1'),true)).trim();
 const project=text(cellValue(sheet.getCell('A2'),true)).trim();
 const supplier=heading.match(/（([^）]*公司)）/)?.[1]||'供应商未标注';
 const quote=parseQuote({id,filename,sheet:sheet.name,rows,sourceRows,headerRow:n,supplierName:supplier,
  projectName:meta.projectName||project||heading||filename.replace(/\.xlsx$/i,''),
  projectId:meta.projectId||`unmapped:${id}`,quoteDate:null,sourceUrl:meta.sourceUrl||null});
 quote.lines=quote.lines.map(line=>({...line,...details.get(line.row),derivedAmount:line.amount??line.derivedAmount}));
 return quote;
}

export async function importWorkbook(buffer,filename,id,meta={}){
 if(!/\.xlsx?$/i.test(filename))throw Error('请上传 .xlsx 或 .xls 格式的 Excel 报价单。');
 if(buffer.byteLength>30*1024*1024)throw Error('文件超过 30 MB，请拆分后导入。');
 const workbook=new ExcelJS.Workbook();
 const magic=Array.from(new Uint8Array(buffer,0,Math.min(8,buffer.byteLength))).map(v=>v.toString(16).padStart(2,'0')).join('');
 if(magic==='d0cf11e0a1b11ae1'){
  const response=await fetch('/api/valuation/legacy-xls',{method:'POST',headers:{'Content-Type':'application/vnd.ms-excel'},body:buffer});
  const document=await response.json().catch(()=>null);
  if(!response.ok||document?.error||!Array.isArray(document?.sheets))throw Error(document?.error||'旧版Excel暂时无法读取，请稍后重试。');
  for(const original of document.sheets){
   const sheet=workbook.addWorksheet(original.name);
   for(const row of original.rows)sheet.getRow(row.row).values=row.values;
   for(const [first,last,left,right] of original.merged_ranges||[])sheet.mergeCells(first+1,left+1,last,right);
  }
 }else{
  try{await workbook.xlsx.load(buffer);}catch{throw Error('无法解析Excel文件，请确认文件未损坏、未加密，且扩展名与文件格式一致。');}
 }
 const matches=workbook.worksheets.map(sheet=>({sheet,header:headerFor(sheet)})).filter(x=>x.header&&(!meta.worksheet||x.sheet.name===meta.worksheet));
 const templates=matches.filter(x=>x.sheet.name==='报价清单'&&x.header.template);
 const selected=meta.worksheet?matches[0]:templates.length===1?templates[0]:matches.length===1?matches[0]:null;
 if(!selected)throw Error(matches.length?'发现多张报价表，请指定工作表：'+matches.map(x=>x.sheet.name).join('、'):'没有找到报价表头。需要物料名称、数量或单位，以及单价或金额。');
 const {sheet,header}=selected;
 if(sheet.rowCount>5000)throw Error('超过 5000 行，请拆分。');
 if(!header.template)return genericQuote(sheet,header,filename,id,meta);
 const rows=[];
 sheet.eachRow((row,n)=>{
  const values=Array.from({length:10},(_,i)=>cellValue(row.getCell(i+1)));
  if(values.some(v=>v!==''))rows.push({row:n,values});
 });
 const supplierName=text(cellValue(sheet.getCell('F2'))).trim();
 const title=text(cellValue(sheet.getCell('A1'))).trim();
 if(!supplierName||!title)throw Error('项目标题或供应商名称为空，不能创建来源记录。');
 const quote=parseQuote({id,filename,sheet:sheet.name,rows,headerRow:header.n,supplierName,projectName:meta.projectName||title,projectId:meta.projectId||`unmapped:${id}`,quoteDate:null,sourceUrl:meta.sourceUrl||null});
 quote.lines=quote.lines.map(line=>({...line,...priceContext(sheet,header,line.row)}));
 return quote;
}
export async function hashBuffer(buffer){const h=await crypto.subtle.digest('SHA-256',buffer);return [...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,'0')).join('');}
