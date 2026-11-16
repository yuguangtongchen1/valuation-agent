import Decimal from 'decimal.js';
export const RULE_VERSION = '0.1.0';
export const CATEGORIES = [
 {id:'MC-01-01',name:'地台基础',rule:'C03',definition:'承重基层及结构；排除面层、收口、灯光和另列搭建人工。',fields:[['structure','结构材质'],['board','板材规格/厚度'],['height','平台高度'],['load','承重要求'],['billing','计费面积依据'],['scope','制作/安装/运输范围']]},
 {id:'MC-01-02',name:'地台面层',rule:'C04',definition:'地台表面地胶、地贴及印刷裁型；排除基层和收口。',fields:[['material','材料及厚度/型号'],['process','印刷/裁型工艺'],['base','施工基面'],['billing','计费面积依据'],['scope','制作/铺贴/运输范围']]},
 {id:'MC-01-03',name:'地台收口',rule:'C05',definition:'地台边缘收口条；保留材质、厚度、截面及加工工艺。',fields:[['material','材质及厚度'],['section','截面宽高'],['process','加工工艺'],['billing','计费长度依据'],['scope','制作/安装/运输范围']]},
 {id:'MC-02',name:'道具与装饰 · 待细分',rule:'C02',definition:'成品、定制和整包分别记录；无拆价证据不生成子件单价。',fields:[['delivery','采购/定制方式'],['spec','具体规格'],['scope','包含/排除范围']]},
 {id:'MC-03',name:'灯光电气 · 待细分',rule:'C02',definition:'灯具、耗材、电气服务分别识别，租用与购买不能混用。',fields:[['spec','型号及规格'],['delivery','购买/租赁方式'],['scope','包含/排除范围']]},
 {id:'MC-04',name:'现场服务 · 待细分',rule:'C02',definition:'搭建、撤场、餐住和维护保留各自的计费范围。',fields:[['billing','班次/计费单位定义'],['scope','工期及服务范围']]},
 {id:'MC-05',name:'运输与设备 · 待细分',rule:'C02',definition:'货运、人员交通及设备租赁分别记录。',fields:[['spec','车型/设备规格'],['billing','路线/台班定义'],['scope','搭建/撤场包含范围']]},
 {id:'MC-06',name:'专项费用 · 待细分',rule:'C02',definition:'计算书、保险等按服务对象和覆盖范围单独保留。',fields:[['scope','服务对象及覆盖范围']]},
 {id:'PENDING',name:'待归类',rule:'C07',definition:'信息不足，不凭名称强行归类。',fields:[['spec','材质/工艺/用途'],['scope','包含/排除范围']]}
];
export const categoryOf = id => CATEGORIES.find(c=>c.id===id)||CATEGORIES.at(-1);
export const text = v => v === null || v === undefined ? '' : String(v);
// Restricted arithmetic parser: Decimal, same-row F/H/I references; never eval or execute workbook code.
export function arithmetic(input, resolve = () => {throw Error('无有效引用');}) {
 const source=text(input).replace(/^=/,'').replace(/\s/g,'');
 if(!source || source.length>250) throw Error('公式为空或过长');
 const tokens=source.match(/\d+(?:\.\d+)?|[A-Z]+\d+|[()+\-*/]/g)||[];
 if(tokens.join('')!==source) throw Error('不支持的公式');
 let i=0;
 const atom=()=>{let t=tokens[i++];if(t==='+'||t==='-'){const n=atom();return t==='-'?n.neg():n;}if(t==='('){const n=add();if(tokens[i++]!==')')throw Error('括号不匹配');return n;}if(/^\d/.test(t||''))return new Decimal(t);if(/^[A-Z]+\d+$/.test(t||''))return new Decimal(resolve(t));throw Error('不完整公式');};
 const mul=()=>{let n=atom();while(tokens[i]==='*'||tokens[i]==='/'){const op=tokens[i++],r=atom();if(op==='/'&&r.isZero())throw Error('除零');n=op==='*'?n.mul(r):n.div(r);}return n;};
 const add=()=>{let n=mul();while(tokens[i]==='+'||tokens[i]==='-'){const op=tokens[i++],r=mul();n=op==='+'?n.add(r):n.sub(r);}return n;};
 const n=add();if(i!==tokens.length||!n.isFinite())throw Error('无有效结果');return n;
}
export function evaluateRow(values,rowNo,index,seen=new Set()) {
 const key=`${rowNo}:${index}`; if(seen.has(key))throw Error('循环引用');
 const next=new Set(seen);next.add(key);const v=values[index];
 if(v===null||v===undefined||v==='')return null;
 return arithmetic(v, ref=>{
  const m=/^([A-Z]+)(\d+)$/.exec(ref);if(Number(m[2])!==rowNo||!['F','H','I'].includes(m[1]))throw Error('只支持同行F/H/I引用');
  const n=evaluateRow(values,rowNo,{F:5,H:7,I:8}[m[1]],next);if(n===null)throw Error('引用为空');return n;
 }).toString();
}
function candidate(name,desc,section){
 const s=name+' '+desc;
 if(/收口/.test(name))return 'MC-01-03';
 if(/地台面|地胶|地贴/.test(name))return 'MC-01-02';
 if(/地台/.test(name)&&/钢|木|结构/.test(desc))return 'MC-01-01';
 if(/运输|交通|升降车|曲臂车|叉车|吊车/.test(name))return 'MC-05';
 if(/计算书|保险/.test(name))return 'MC-06';
 if(/人员|搭建差旅|值班|维护|差旅/.test(name))return 'MC-04';
 if(/灯|电工|电料|发光/.test(name))return 'MC-03';
 if(section==='制作物料'||/道具|造型|装饰|摆件/.test(s))return 'MC-02';
 return 'PENDING';
}
export function normalizeUnit(unit){return ({平米:'m²',平方米:'m²','㎡':'m²',米:'m'})[unit]||unit||null;}
export function parseQuote(raw){
 const lines=[],summaries=[];let section='',region='',regionRow=null;
 for(const r of raw.rows){const v=r.values.map(x=>x??'');
  if(r.row<=(raw.headerRow??5))continue;
  if(!v[2]){if(v[0]&&!v[5]&&!v[8]){section=text(v[0]);region='';regionRow=null;}summaries.push(r);continue;}
  // Numeric source sequence identifies detail lines in the supported quotation template.
  if(!/^\d+$/.test(text(v[0]))) {summaries.push(r);continue;}
  if(v[1]){region=text(v[1]);regionRow=r.row;}
  const categoryId=candidate(text(v[2]),text(v[3]),section);
  const calc={};const errors=[];
  for(const [k,index] of [['quantity',5],['unitPrice',7],['amount',8]]){try{calc[k]=evaluateRow(v,r.row,index);}catch(err){calc[k]=null;errors.push(`${k}: ${err.message}`);}}
  let derivedAmount=null;if(calc.quantity!==null&&calc.unitPrice!==null)derivedAmount=new Decimal(calc.quantity).mul(calc.unitPrice).toString();
  lines.push({id:`${raw.id}:${raw.sheet}:${r.row}`,quoteId:raw.id,projectId:raw.projectId,supplierName:raw.supplierName,filename:raw.filename,sheet:raw.sheet,row:r.row,sequence:text(v[0]),section,region,regionRow,name:text(v[2]),description:text(v[3]),dimensions:text(v[4]),unit:text(v[6]),standardUnit:normalizeUnit(text(v[6])),rawQuantity:v[5],rawUnitPrice:v[7],rawAmount:v[8],remark:text(v[9]),...calc,derivedAmount,calcErrors:errors,categoryId,priceStage:'quoted',quoteDate:raw.quoteDate??null,sourceUrl:raw.sourceUrl??null,rawValues:v});
 }
 return {...raw,lines,summaries};
}
export function classify(line,review){const cat=categoryOf(review?.categoryId||line.categoryId);return {category:cat,status:review?'人工确认归类':'规则候选',rule:review?'C07':cat.rule};}
const issue=(code,message,question)=>({code,message,question:question||message});
export function gaps(line,review){
 const out=[],a=review?.attributes||{};const cat=classify(line,review).category;
 if(!review)out.push(issue('C07','候选归类尚未人工确认','请确认归类和业务用途；同名不等于同规格。'));
 if(!a.tax)out.push(issue('V03','税口径待确认','请确认该行单价含税/未税，以及全单优惠价的税口径。全表6%税不自动赋给每行。'));
 if(!line.quoteDate&&!a.quoteDate)out.push(issue('V02','报价日期未核实','请提供报价生效日期；不从文件名或活动时间推断。'));
 for(const [key,label]of cat.fields)if(!a[key])out.push(issue('V01',`${label}待确认`,`请确认${label}。原描述：${line.description||'未填写'}。`));
 if(cat.id==='MC-01-02'&&!/地台面/.test(line.name)&&!a.base)out.push(issue('C04','使用位置/施工基面待确认','请确认地胶或地贴是否属于地台表面。'));
 if(/15厘/.test(line.description)&&!a.board)out.push(issue('C06','15厘单位待确认','该报价中15厘是否指15mm？确认前保留原词。'));
 const circle=/直径\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|毫米|厘米|米)?/i.exec(line.dimensions);
 if(circle&&line.standardUnit==='m²'&&!a.billing){
  const dimensionUnit=circle[2]?.toLowerCase()||line.dimensionUnit||(line.spec==null?'mm':'');
  const factor=({mm:.001,毫米:.001,cm:.01,厘米:.01,m:1,米:1})[dimensionUnit];
  const area=factor?new Decimal(circle[1]).mul(factor).div(2).pow(2).mul(Math.PI):null;
  if(area===null||line.quantity===null||area.minus(line.quantity).abs().gt('.01')){
   const quantities=area!==null&&line.quantity!==null?`计费面积 ${line.quantity} m²，按直径计算的圆面积约 ${area.toFixed(2)} m²。`:'';
   out.push(issue('Q03','圆形尺寸与计费面积需核对',`${quantities}请确认是否按外接面积计费，或含有施工余量。`));
  }
 }
 const rect=/L(\d+(?:\.\d+)?)\*W(\d+(?:\.\d+)?)/.exec(line.dimensions);
 if(rect&&line.standardUnit==='m²'&&line.quantity!==null){const geo=new Decimal(rect[1]).mul(rect[2]).div(1e6);if(!geo.eq(line.quantity)&&!a.billing)out.push(issue('Q03',`尺寸面积${geo.toString()}m²与计费量${line.quantity}m²不同`,'请确认尺寸单位及计费面积中的余量/损耗，原公式保留。'));}
 if(line.unit==='项')out.push(issue('C02','按项/整包计费，不能自动拆单价','请提供独立子项报价或确认整包范围；不得平均分摊给子件。'));
 if(line.unit==='人/工'&&!a.billing)out.push(issue('Q01','人/工定义未明确','每工是几小时/几班？公式中的系数是什么意思？不能直接换算为人/天。'));
 if(!['MC-01-01','MC-01-02','MC-01-03'].includes(cat.id))out.push(issue('V01','超出首批自动比价类目','首批仅覆盖地台基础、面层、收口；本行先保存为参考案例。'));
 if(line.calcErrors.length)out.push(issue('Q02','公式无法安全解析',line.calcErrors.join('；')));
 if(line.quantity===null||new Decimal(line.quantity).lte(0))out.push(issue('Q02','计费数量缺失或非正数'));
 if(line.unitPrice===null||new Decimal(line.unitPrice).lte(0))out.push(issue('Q02','单价缺失或非正数'));
 if(line.amount!==null&&line.derivedAmount!==null&&new Decimal(line.amount).minus(line.derivedAmount).abs().gt('.01'))out.push(issue('Q02','数量×单价与小计不一致'));
 const shift=/安装(\d+)个台班.*撤场(\d+)个台班/.exec(line.description);
 if(shift&&line.quantity!==null&&!new Decimal(shift[1]).add(shift[2]).eq(line.quantity))out.push(issue('Q04','台班数量与描述不一致',`原数量${line.quantity}，描述安装${shift[1]}+撤场${shift[2]}台班；请核实。`));
 if(/剪刀升降车/.test(line.name)&&/吊车/.test(line.description))out.push(issue('Q04','设备名称与备注冲突','名称是剪刀升降车，备注写吊车，请确认实际设备。'));
 return out;
}
export function referenceRows(line,all,reviews={}){
 const cat=classify(line,reviews[line.id]).category.id;
 return all.filter(r=>r.id!==line.id&&classify(r,reviews[r.id]).category.id===cat).map(r=>{
 const diff=[];
 if(r.standardUnit!==line.standardUnit)diff.push(`计费单位不同：${r.unit}`);
 if(r.description!==line.description)diff.push('工艺/材料描述不同');
 if(r.dimensions!==line.dimensions)diff.push('尺寸/规模不同');
 if(r.projectId===line.projectId)diff.push('同项目，不是独立采购案例');
 if(r.quoteId!==line.quoteId)diff.push('跨文件税价/范围需确认');
 return {line:r,differences:diff,comparable:false};
 }).sort((a,b)=>a.differences.length-b.differences.length||a.line.row-b.line.row);
}
export function queryReferences(lines,{keyword='',categoryId='',unit=''},reviews={}){
 const q=keyword.trim().toLowerCase();
 return lines.filter(l=>(!q||`${l.name} ${l.description} ${l.region} ${classify(l,reviews[l.id]).category.name}`.toLowerCase().includes(q))&&(!categoryId||classify(l,reviews[l.id]).category.id===categoryId)&&(!unit||l.standardUnit===unit));
}
export function evidenceCounts(lines){return {projects:new Set(lines.filter(l=>!l.projectId.startsWith('unmapped:')).map(l=>l.projectId)).size,unmappedSources:new Set(lines.filter(l=>l.projectId.startsWith('unmapped:')).map(l=>l.quoteId)).size,suppliers:new Set(lines.map(l=>l.supplierName)).size,quotes:new Set(lines.map(l=>l.quoteId)).size,lines:lines.length};}
export function makeReport(quotes,reviews,history){const lines=quotes.flatMap(q=>q.lines);return {schemaVersion:1,ruleVersion:RULE_VERSION,exportedAt:new Date().toISOString(),mode:'local-prototype',note:'仅报价参考，不构成市场合理价；未连接OA，无自动审批。',sources:quotes.map(({lines,rows,...rest})=>rest),counts:evidenceCounts(lines),lines:lines.map(l=>({...l,classification:classify(l,reviews[l.id]),review:reviews[l.id]||null,issues:gaps(l,reviews[l.id])})),reviewEvents:history};}
