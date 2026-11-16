import {DesignImages} from './DesignImages.jsx';
import {splitPoints} from './text-points.js';
import React,{useEffect,useRef} from 'react';
import {AlertCircle} from 'lucide-react';
import {money} from './Inspector.jsx';
import {PricePanel} from './PricePanel.jsx';
import {gaps} from './engine.js';
function Specification({line}){
 if(line.spec_completeness?.status==='design_pending')return <span>待设计确定</span>;
 if(!line.dimensions)return <span>{line.spec_completeness?.label||'待核规格'}</span>;
 return <div className="specification-parts">{splitPoints(line.dimensions).map((part,i)=>{
  const notes=part.match(/（[^）]*）/g)||[];
  const main=part.replace(/（[^）]*）/g,'').trim();
  return <div className="specification-part" key={i}><span>{main.split(/(\d+(?:\.\d+)?(?:mm|cm|m)?)/).map((text,j)=>/^\d/.test(text)?<strong key={j}>{text}</strong>:<React.Fragment key={j}>{text.replace(/\*/g,'×')}</React.Fragment>)}</span>{notes.map((note,j)=><small key={j}>{note}</small>)}</div>;
 })}</div>;
}
function ProcessDescription({text=''}){
 // Keep technical requirements; move narrative display themes out of the compact view.
 const concise=text.replace(/展陈内容对应[^；。]*/g,'').replace(/运行平稳无噪音[，,]?/g,'');
 const points=splitPoints(concise,{numbered:true,process:true});
 const content=<ol className="process-points">{points.map((point,i)=><li key={i}>{point}</li>)}</ol>;
 return points.length>4?<details className="long-description" onClick={e=>e.stopPropagation()}><summary>{points.slice(0,2).join('；')}… <span>完整工艺说明</span></summary>{content}</details>:points.length?content:<span>—</span>;
}
export function QuoteTable({lines,selected,onSelect,reviews,onEvidence,observed}){
 const container=useRef(null);
 useEffect(()=>{const el=container.current?.querySelector('[data-selected="true"]');el?.scrollIntoView({block:'nearest',inline:'nearest'});},[selected?.id]);
 function moveRow(e){if(!['ArrowDown','ArrowUp'].includes(e.key))return;e.preventDefault();const current=lines.findIndex(l=>l.id===(e.target.closest('tr')?.dataset.lineId||selected?.id)),index=Math.max(0,Math.min(lines.length-1,current+(e.key==='ArrowDown'?1:-1)));if(lines[index]){onSelect(lines[index].id);container.current.querySelectorAll('.sheet-name')[index]?.focus({preventScroll:true});}}
 let previous='';
 return <div className="quote-sheet-scroll" ref={container}><table className="quote-sheet row-connected"><thead><tr>{['物料','工艺说明','规格 / 尺寸','数量','单位','单价（元）','小计（元）'].map(t=><th key={t}>{t}</th>)}<th className="reference-lane-head" aria-label="参考报价区域"/></tr></thead><tbody onKeyDown={moveRow}>{lines.map(l=>{const group=`${l.quoteId}:${l.section}:${l.region}`,newGroup=group!==previous;previous=group;const flags=gaps(l,reviews[l.id]).filter(g=>['Q03','Q04'].includes(g.code));const flagDescription=flags.map(g=>g.message+'。'+g.question).join(' ');return <React.Fragment key={l.id}>{newGroup&&<tr className="region-row"><th colSpan="7">{l.region||l.section||'其他明细'}</th><td className="empty-reference-lane"/></tr>}<tr data-line-id={l.id} data-selected={l.id===selected?.id} className={l.id===selected?.id?'chosen':''} onClick={()=>onSelect(l.id)}><td data-label="物料" className="sheet-material"><button className="sheet-name" aria-label={`查看${l.name}的参考价格`} aria-description={flagDescription||undefined} aria-pressed={l.id===selected?.id} onClick={e=>{e.stopPropagation();onSelect(l.id)}}><span>{l.name}</span>{flags.length>0&&<small title={flagDescription}><AlertCircle size={13} aria-label="有待核实信息"/></small>}</button></td><td data-label="工艺说明" className="sheet-description"><ProcessDescription text={l.description}/>{l.components?.length>0&&<details onClick={e=>e.stopPropagation()}><summary>查看组合子件（未单独计价）</summary><ul>{l.components.map((c,i)=><li key={i}>{c.item_name}{c.description?` · ${c.description}`:''}</li>)}</ul></details>}<DesignImages images={l.image_evidence} name={l.name}/>{l.price_note&&<small>{l.price_note}</small>}</td><td data-label="规格 / 尺寸" className="sheet-dimensions"><Specification line={l}/></td><td data-label="数量" className="num">{l.quantity??'—'}</td><td data-label="单位" className="sheet-unit">{l.unit||'—'}</td><td data-label="单价（元）" className="num"><button className="unit-price-trigger" aria-label={`查看${l.name}的历史单价`} aria-pressed={l.id===selected?.id} onClick={e=>{e.stopPropagation();onSelect(l.id)}}>{l.currency&&l.currency!=='CNY'?'待折算':money(l.unitPrice)}</button></td><td data-label="小计（元）" className="num">{l.currency&&l.currency!=='CNY'?'待折算':money(l.derivedAmount)}</td><td className={l.id===selected?.id?'attached-reference-cell':'empty-reference-lane'} onClick={e=>e.stopPropagation()}>{l.id===selected?.id&&<PricePanel key={l.id} line={l} onEvidence={onEvidence} observed={observed}/>}</td></tr></React.Fragment>})}</tbody></table>{!lines.length&&<div className="sheet-empty">没有找到明细，请换个关键词。</div>}</div>
}
