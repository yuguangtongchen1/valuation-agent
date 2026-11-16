import {splitPoints} from './text-points.js';
import React, {useEffect,useState} from 'react';
import {ArrowLeft} from 'lucide-react';
import {money} from './Inspector.jsx';
import {api,lookupQuery,billingText,referencePrice,quotationVariantLabel} from './valuation.js';

const originalLink = row => {
 if(row.source_url){try{const u=new URL(row.source_url);if(u.protocol==='https:')return u.href;}catch{}}
 return /^[A-Za-z0-9]{16,64}$/.test(row.source_token||'')?`https://www.feishu.cn/file/${encodeURIComponent(row.source_token)}`:null;
};
const archiveOnly = row => row.source_attributes?.finance_archive_only===true;
const price = (value,currency,cny,archived=false) => cny!=null?`¥${money(cny)}`:value==null||archived?'—':currency==='CNY'?`¥${money(value)}`:'待折算人民币';
const title = value => (value||'相关台账记录').replace(/--.*\d{4}-\d{2}-\d{2}.*$/,'');
const componentLabel = row => row.component_name ? `部分参考 · ${row.component_name}` : '';
const readableReason = row => {
 const category=row.classification?.historical?.at(-1);
 const basis=row.component_name?`匹配子件：${row.component_name}`:category?`按交付内容匹配：${category}`:'';
 const differences=(row.differences||[]).filter(d=>d!=='规格不同').flatMap(d=>splitPoints(d,{sentences:true})).map(d=>d.trim()).filter(d=>d&&!/不作为|仅保留|不代表|进一步比较|仅作|不能确认|不可直接比较/.test(d));
 return [...new Set([basis,...differences].filter(Boolean))];
};
const rankReferences = (rows,line) => {
 const unit=u=>({'m2':'㎡','平方米':'㎡','平方':'㎡','平米':'㎡','m':'米'}[u]||u||'');
 const rank=row=>[
  row.component_name?2:/上位|交易|旁证|工艺参考/.test(row.match_kind||'')?3:0,
  /施工图/.test(line.name||'')&&!/施工图/.test(row.item_name||'')?1:0,
  unit(row.unit)&&unit(row.unit)===unit(line.unit)?0:1,
  (row.parameters||[]).filter(p=>p.different).length,
 ];
 return rows.map((row,index)=>({row,index,key:rank(row)})).sort((a,b)=>{
  for(let i=0;i<a.key.length;i++){if(a.key[i]!==b.key[i])return a.key[i]-b.key[i];}
  return a.index-b.index;
 }).map(x=>x.row);
};
const referenceAmount = row => {const view=referencePrice(row);return price(view.amount,view.currency,view.cny);};
const hasRateContext = row => Boolean(row.reference_rate_label||row.billing_period||row.period||Number(row.billing_multiplier||row.price_multiplier)>1);
const variantId = row => row.quotation_variant_id||row.source_attributes?.quotation_variant_id||row.parent_quote_variant?.quotation_variant_id||row.parent_quote_variant?.id||'';
export function PricePanel({line,onEvidence,observed}){
 const [result,setResult]=useState(null),[failed,setFailed]=useState(false),[attempt,setAttempt]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();
  setResult(null);setFailed(false);
  api('lookup',lookupQuery(line),controller.signal).then(value=>{
   if(observed)observed.current[line.id]=value;
   setResult(value);
  }).catch(e=>{if(e.name!=='AbortError')setFailed(true);});
  return ()=>controller.abort();
 },[line,observed,attempt]);
 return <section className="attached-reference" aria-label={`${line.name}参考报价`}>
  <table><colgroup><col/><col className="reference-price-column"/></colgroup><thead><tr><th colSpan="2">历史参考报价</th></tr></thead><tbody>
   {result?.references.length?rankReferences(result.references,line).map(row=>row.kind==='ledger_match'
    ?<tr key={`${row.sheet}:${row.address}`}><td><a href={row.url} target="_blank" rel="noreferrer">{row.value||line.name}</a><small>{row.sheet} 台账 · {row.address}</small></td><td><small className="price-inline">无分项单价</small></td></tr>
    :<tr key={`${row.line_id}:${row.component_name||''}`}>
      <td>
       <button className="reference-link reference-item" onClick={()=>onEvidence(row,line)}>
        <strong>{row.item_name}</strong>
        <span className="reference-kind">{[componentLabel(row),row.match_kind].filter(Boolean).join(' · ')}</span>
        {quotationVariantLabel(row)&&<span className="reference-kind">{quotationVariantLabel(row)}</span>}
        {!!readableReason(row).length&&<ol className="reference-points">{readableReason(row).map(point=><li key={point}>{point}</li>)}</ol>}

       </button>
       <small className="reference-project" title={title(row.project)}>{title(row.project)}</small>
      </td>
      <td><button className="reference-link price-inline" onClick={()=>onEvidence(row,line)} aria-label={`查看${row.item_name} ${referenceAmount(row)}${referencePrice(row).componentNote?' 子件金额注记':referencePrice(row).packageTotal?' 整包':referencePrice(row).unit?` 每${referencePrice(row).unit}`:''}`}><strong>{referenceAmount(row)}</strong><small>{referencePrice(row).unit?` / ${referencePrice(row).unit}`:''}</small></button>
       {hasRateContext(row)&&row.subtotal!=null&&<small className="reference-rate-total">小计 {price(row.subtotal,row.currency,row.subtotal_cny_yuan,archiveOnly(row))}</small>}
      </td>
     </tr>)
    :<tr><td colSpan="2" role="status">{failed?'历史参考暂不可用':!result?'正在查找历史参考…':'当前资料未找到可用参考'}
     {failed&&<button className="reference-retry" onClick={()=>setAttempt(n=>n+1)}>重新查询</button>}
     {!!result?.query_classification?.length&&<small title={result.query_classification.join(' › ')}>{result.query_classification.slice(-2).join(' › ')}</small>}
    </td></tr>}
  </tbody></table>
 </section>;
}
export function EvidencePage({row,line,onBack}){
 const [details,setDetails]=useState(null),[attempt,setAttempt]=useState(0);
 const contractSubtitle=[row.contract_name,row.supplier].filter(Boolean).join(' · ');
 const allLines=details?.lines||[];
 const variantLines=variantId(row)?allLines.filter(item=>variantId(item)===variantId(row)):[];
 const detailLines=variantLines.length?variantLines:allLines;
 useEffect(()=>{
  const controller=new AbortController();
  setDetails(null);
  api('contract',{exclude:row.record_id},controller.signal).then(setDetails).catch(e=>{if(e.name!=='AbortError')setDetails({error:true,message:e.message});});
  return ()=>controller.abort();
 },[row.record_id,attempt]);
 return <main className="valuation-detail">
  <button className="detail-back" onClick={onBack}><ArrowLeft size={16}/>返回报价行</button>
  <p className="entry-eyebrow">第 3 步 · 历史报价详情</p>
  <h1>{title(row.project)}</h1>
  <p className="contract-subtitle" title={contractSubtitle}>{contractSubtitle}</p>
  <dl className="valuation-meta">
   <div><dt>当前物料</dt><dd>{line.name} · {componentLabel(row)||row.match_kind}</dd></div>
   {quotationVariantLabel(row)&&<div><dt>报价版本</dt><dd>{quotationVariantLabel(row)}</dd></div>}
   {referencePrice(row).packageTotal&&<div><dt>{referencePrice(row).componentNote?'子件金额注记':'整包参考'}</dt><dd>{referenceAmount(row)} · {referencePrice(row).componentNote?'子件金额注记，不是独立采购单价':'按原件整体范围记录，不拆成单价'}</dd></div>}
   {row.match_reason&&<div><dt>匹配依据</dt><dd>{row.match_reason}{row.component_name&&'。此价格仅参考该子件。'}</dd></div>}
   {row.classification&&<>
    <div><dt>当前归类</dt><dd>{row.classification.current.join(' › ')||'待归类'}</dd></div>
    <div><dt>历史归类</dt><dd>{row.classification.historical.join(' › ')||'待归类'}</dd></div>
   </>}
   {!!row.spec_differences?.length&&<div><dt>当前规格</dt><dd>{[line.model,line.spec||line.dimensions,line.description,line.configuration].filter(Boolean).join(' · ')||'—'}</dd></div>}
   <div><dt>台账</dt><dd>{row.sheet} 年 · 含税人民币 {row.ledger_amount_cny_tax_inclusive||'未列'}</dd></div>
   <div><dt>合同原件</dt><dd>{originalLink(row)?<a href={originalLink(row)} target="_blank" rel="noopener noreferrer">{row.source_name||'打开合同原件'} ↗</a>:<span>{row.source_name||'合同原件'}（原件链接待补）</span>}</dd></div>
  </dl>
  <h2>历史合同明细</h2>
  {detailLines.length?<div className="evidence-scroll"><table className="evidence-table"><thead><tr><th>物料</th><th>规格 / 型号</th><th>数量</th><th>单位</th><th>单价（人民币元）</th><th>金额（人民币元）</th></tr></thead><tbody>{detailLines.map((r,i)=>{
   const selected=r.line_id===row.line_id;
   const specDifferences=selected?row.spec_differences||[]:[];
   const specificDifferences=specDifferences.filter(difference=>difference!=='规格不同');
   const specification=[...new Set([r.spec,r.model].filter(Boolean))].join(' / ');
   return <tr key={r.line_id||i} className={selected?'evidence-highlight':''}>
    <td data-label="物料">{r.item_name}{archiveOnly(r)&&<small className="spec-note">原报价留存，不作人民币比价</small>}{quotationVariantLabel(r)&&<small className="spec-note">{quotationVariantLabel(r)}</small>}</td><td data-label="规格 / 型号" className={specDifferences.length?'spec-different':undefined}>
     {specification||<span className="spec-note">{r.description?'未单列规格 / 型号':'暂无规格 / 型号'}</span>}
     {r.description&&r.description!==r.spec&&r.description!==r.model&&<small className="spec-note">工艺 / 配置 · {r.description}</small>}
     {billingText(r)&&<small className="spec-note">{billingText(r)}</small>}
     {!!specDifferences.length&&<div className="spec-differences">
      <strong>规格差异</strong>
      {!!specificDifferences.length&&<ul>{specificDifferences.map(difference=><li key={difference}>{difference.replace(/^([长宽高])不同/,'$1度不同')}</li>)}</ul>}
     </div>}
    </td><td data-label="数量" className="price-inline">{r.quantity??'—'}</td><td data-label="单位" className="price-inline">{r.unit||'—'}</td><td data-label="单价（元）" className="price-inline">{price(r.unit_price,r.currency,r.unit_price_cny_yuan,archiveOnly(r))}</td><td data-label="金额（元）" className="price-inline">{price(r.subtotal,r.currency,r.subtotal_cny_yuan,archiveOnly(r))}</td>
   </tr>;
  })}</tbody></table></div>
  :<p role="status">{details?.error?`合同明细读取失败：${details.message||'请重新读取'}`:'正在打开合同明细…'}{details?.error&&<button className="reference-retry" onClick={()=>setAttempt(n=>n+1)}>重新读取</button>}</p>}
  {!!row.parameters?.length&&<section className="parameter-comparison">
   <h2>规格对照</h2>
   <table><thead><tr><th>参数</th><th>当前规格</th><th>历史规格</th></tr></thead><tbody>
    {row.parameters.map(parameter=><tr key={parameter.label} className={parameter.different?'parameter-difference':undefined}>
     <th scope="row">{parameter.label}</th><td>{parameter.current||'未注明'}</td><td>{parameter.historical||'未注明'}</td>
    </tr>)}
   </tbody></table>
  </section>}
 </main>;
}
