import React,{useEffect,useRef,useState} from 'react';
import {ArrowLeft,ArrowRight,Download,FileUp,Link2,X} from 'lucide-react';
import seed from './seed.json';
import {parseQuote} from './engine.js';
import {loadDatabase,saveQuote} from './storage.js';
import {ImportDialog} from './DataWorkbench.jsx';
import {QuoteTable} from './QuoteTable.jsx';
import {EvidencePage} from './PricePanel.jsx';
import {api,comparisonWorkbook,saveExcel} from './valuation.js';
import {readWorkbenchSession,rememberWorkbenchSession,resolveWorkbenchQuote} from './workbench-session.js';
import './simple.css';
import './table-layout.css';

export default function App(){
 const [db,setDb]=useState(null),[fatal,setFatal]=useState('');
 const [quote,setQuote]=useState(null),[selectedId,setSelectedId]=useState(null),[evidence,setEvidence]=useState(null);
 const [notice,setNotice]=useState(''),[busy,setBusy]=useState(''),[oa,setOA]=useState(false),[oaError,setOAError]=useState('');
 const dialog=useRef(null),observed=useRef({}),returnPosition=useRef(null);
 const quoteCache=useRef(new Map()),restored=useRef(false);
 const demoRequested=useRef(new URLSearchParams(location.search).get('demo')==='1');
 const fileRequested=useRef(new URLSearchParams(location.search).get('file'));
 const fileWorksheet=useRef(new URLSearchParams(location.search).get('worksheet')||'');
 const handoffRevision=useRef(null);
 useEffect(()=>{
  if(!db||new URLSearchParams(location.search).get('handoff')!=='1')return;
  let stopped=false,timer;
  async function sync(){
   try{
    const payload=await api('handoff');
    if(stopped)return;
    if(payload.revision&&payload.revision!==handoffRevision.current){
     const doc=payload.document,id=`codex:${payload.revision}`;
     const q={id,projectName:doc.project||payload.filename,filename:payload.filename,supplierName:doc.supplier||'',sheet:'Codex',summaries:[],rows:[],lines:doc.rows.map((r,i)=>({
      ...r,id:`${id}:${i}`,quoteId:id,row:i+1,name:String(r.item_name||''),description:String(r.description||r.configuration||''),dimensions:String(r.spec||''),spec:r.spec||'',model:r.model||'',configuration:r.configuration||'',
      quantity:r.quantity??null,unit:r.unit||'',standardUnit:r.unit||'',unitPrice:r.unit_price??null,amount:r.subtotal??null,derivedAmount:r.subtotal??null,currency:r.currency||'CNY',
      section:r.section||'',region:r.region||'',categoryId:'PENDING',calcErrors:[],priceStage:'quoted',sourceLocator:r.source_locator||null
     }))};
     await saveQuote(q);
     if(stopped)return;
     observed.current={};select(q);handoffRevision.current=payload.revision;
     setNotice(`已同步 ${q.projectName}：${q.lines.length} 条明细。`);
    }
   }catch(e){if(!stopped)setNotice(`左侧文件同步失败：${e.message}`);}
   finally{if(!stopped)timer=setTimeout(sync,2000);}
  }
  sync();return()=>{stopped=true;clearTimeout(timer);};
 },[Boolean(db)]);
 useEffect(()=>{
  loadDatabase(parseQuote(seed)).then(loaded=>{
   loaded.quotes.forEach(q=>quoteCache.current.set(q.id,q));
   const saved=readWorkbenchSession();
   const previous=resolveWorkbenchQuote(saved,loaded.quotes,saved?.demoQuote);
   if(previous&&!demoRequested.current&&!fileRequested.current){
    quoteCache.current.set(previous.id,previous);setQuote(previous);
    setSelectedId(saved.selectedId||previous.lines[0]?.id);
    if(location.hash==='#reference'&&saved.evidence)setEvidence(saved.evidence);
   }
   restored.current=true;setDb(loaded);
  }).catch(e=>setFatal(e.message));
 },[]);
 useEffect(()=>{
  if(db&&demoRequested.current){demoRequested.current=false;showDemo();}
 },[db]);
 useEffect(()=>{
  if(!db||!fileRequested.current)return;
  const file=fileRequested.current;fileRequested.current=null;
  async function openFile(){
   setBusy('file');setNotice('正在载入报价单…');
   try{
    const source=new URL(file,location.origin);
    if(source.origin!==location.origin||source.username||source.password||!/^https?:$/.test(source.protocol)||! /\.xlsx?$/i.test(source.pathname))throw Error('只支持本机工作台内的Excel报价文件。');
    const response=await fetch(source.href);
    if(!response.ok)throw Error('本机报价文件暂时无法打开，请重新上传。');
    const {hashBuffer,importWorkbook}=await import('./importer.js');
    const bytes=await response.arrayBuffer(),hash=await hashBuffer(bytes),worksheet=fileWorksheet.current;
    const filename=decodeURIComponent(source.pathname.split('/').pop());
    const q=await importWorkbook(bytes,filename,worksheet?`${hash}:${worksheet}`:hash,{worksheet,sourceUrl:source.href});
    const clean=new URL(location.href);clean.searchParams.delete('file');clean.searchParams.delete('worksheet');
    history.replaceState(history.state,'',clean.pathname+clean.search+clean.hash);
    await imported(q);setNotice(`已加载 ${q.projectName}：${q.lines.length}条明细。`);
   }catch(error){
    const clean=new URL(location.href);clean.searchParams.delete('file');clean.searchParams.delete('worksheet');
    history.replaceState(history.state,'',clean.pathname+clean.search+clean.hash);
    setNotice(error.message);
   }finally{setBusy('');}
  }
  openFile();
 },[db]);
 useEffect(()=>{
  const back=()=>{
   const view=history.state?.valuation;
   const previous=quoteCache.current.get(view?.quoteId);
   if(previous){
    setQuote(previous);setSelectedId(view.selectedId||previous.lines[0]?.id);
    returnPosition.current=view.scrollTop??0;setEvidence(view.evidence||null);
   }else{setQuote(null);setEvidence(null);}
  };
  window.addEventListener('popstate',back);
  return ()=>window.removeEventListener('popstate',back);
 },[]);
 useEffect(()=>{
  if(!db||!restored.current)return;
  const view={quoteId:quote?.id||null,selectedId,evidence,scrollTop:evidence?0:(returnPosition.current??window.scrollY)};
  history.replaceState({...history.state,valuation:view},'');
  rememberWorkbenchSession(view,quote);
 },[db,quote,selectedId,evidence]);
 useEffect(()=>{
  if(evidence){window.scrollTo({top:0});return;}
  if(returnPosition.current!=null){
   const top=returnPosition.current;
   returnPosition.current=null;
   requestAnimationFrame(()=>{
    window.scrollTo({top});
    document.querySelector('.sheet-name[aria-pressed="true"]')?.focus({preventScroll:true});
   });
  }
 },[evidence]);
 function select(q){
  quoteCache.current.set(q.id,q);
  history.pushState({valuation:{quoteId:q.id,selectedId:q.lines[0]?.id,evidence:null,scrollTop:0}},'',location.pathname+location.search);
  setQuote(q);setSelectedId(q.lines[0]?.id);setEvidence(null);window.scrollTo({top:0});
 }
 function goEntry(){
  history.pushState({valuation:{quoteId:null,evidence:null}},'',location.pathname+location.search);
  setQuote(null);setEvidence(null);setNotice('');window.scrollTo({top:0});
 }
 async function imported(q){
  const existing=db.quotes.find(old=>old.id===q.id);
  if(existing){
   const context=new Map(q.lines.map(line=>[line.row,line]));
   const refreshed={...existing,lines:existing.lines.map(line=>{
    const source=context.get(line.row);
    return {...line,currency:source?.currency||line.currency,taxBasis:source?.taxBasis||line.taxBasis};
   })};
   select(refreshed);
   return;
  }
  await saveQuote(q);
  setDb(await loadDatabase(parseQuote(seed)));
  select(q);
 }
 async function showDemo(){
  setBusy('demo');setNotice('');
  try{
   const rows=await api('demo');
   const sample=parseQuote({id:'verified-demo',projectName:'数字内容制作 · 已核样例',supplierName:'历史数据演示',sheet:'样例',
    rows:rows.map((r,i)=>({row:i+6,values:[i+1,i===0?'数字内容制作':'',r.item_name,r.description||'',r.spec||r.model||'',r.quantity,r.unit,r.unit_price,r.subtotal]}))});
   sample.lines=sample.lines.map((line,i)=>({...line,sourceRecordId:rows[i].record_id,currency:rows[i].currency,model:rows[i].model,derivedAmount:rows[i].subtotal}));
   select(sample);
  }catch(e){setNotice(e.message);}finally{setBusy('');}
 }
 async function submitOA(event){
  event.preventDefault();
  const form=new FormData(event.currentTarget);
  setBusy('oa');setOAError('');
  try{
   const link=form.get('link').trim();
   const worksheet=form.get('worksheet').trim();
   const doc=await api('oa',{link,worksheet});
   if(doc.error)throw Error(doc.error);
   let bytes;
   if(doc.rows){
    const {default:ExcelJS}=await import('exceljs');
    const book=new ExcelJS.Workbook();
    const sheet=book.addWorksheet(doc.worksheet);
    for(const row of doc.rows)sheet.getRow(row.row).values=row.values;
    bytes=await book.xlsx.writeBuffer();
   }else{
    bytes=Uint8Array.from(atob(doc.bytes),c=>c.charCodeAt(0)).buffer;
   }
   const {hashBuffer,importWorkbook}=await import('./importer.js');
   const projectCode=form.get('projectCode').trim();
   const projectName=form.get('projectName').trim();
   const hash=await hashBuffer(bytes);
   const q=await importWorkbook(bytes,doc.filename,worksheet?`${hash}:${worksheet}`:hash,{
    projectId:projectCode?`oa:${projectCode}`:undefined,projectName:projectName||undefined,
    worksheet:doc.worksheet||worksheet,sourceUrl:link
   });
   await imported(q);
   setOA(false);
  }catch(e){setOAError(e.message);}finally{setBusy('');}
 }
 async function exportQuote(){
  setBusy('export');setNotice('');
  try{
   const bytes=await comparisonWorkbook(quote,api,observed.current);
   saveExcel(bytes,`${quote.projectName.replace(/[\\/:*?"<>|]/g,'_')}比价单.xlsx`);
   setNotice('已导出整张报价及历史参考。');
  }catch(e){setNotice(e.message);}finally{setBusy('');}
 }
 function openEvidence(row,line){
  returnPosition.current=window.scrollY;
  history.replaceState({valuation:{quoteId:quote.id,selectedId,evidence:null,scrollTop:window.scrollY}},'');
  history.pushState({valuation:{quoteId:quote.id,selectedId,evidence:{row,line},scrollTop:0}},'','#reference');
  setEvidence({row,line});
 }
 function closeEvidence(){
  if(history.state?.valuation?.evidence)history.back();
  else{history.replaceState({...history.state},'',location.pathname+location.search);setEvidence(null);}
 }
 if(fatal)return <main className="sheet-empty" role="alert">本机数据无法加载：{fatal}</main>;
 if(!db)return <main className="sheet-empty" role="status">正在打开估价工作台…</main>;
 const selected=quote?.lines.find(l=>l.id===selectedId)||quote?.lines[0];
 return <>
  <nav className="valuation-steps" aria-label="估价步骤">
   <strong>采购估价</strong>
   <ol>{['项目接入','报价比价','历史报价详情'].map((step,i)=>
    <li key={step} aria-current={i===(evidence?2:quote?1:0)?'step':undefined}><span>{i+1}</span>{step}</li>
   )}</ol>
  </nav>
  {notice&&<div className="simple-notice" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="关闭提示"><X size={14}/></button></div>}
  {evidence?<EvidencePage row={evidence.row} line={evidence.line} onBack={closeEvidence}/>
   :quote?<main className="simple-app valuation-sheet">
    <header className="simple-header">
     <div className="quote-title"><button onClick={goEntry}><ArrowLeft size={16}/>项目接入</button><div><h1>{quote.projectName}</h1><span>{quote.supplierName}</span></div></div>
     <div className="simple-actions"><button onClick={()=>dialog.current.showModal()}><FileUp size={16}/>更换报价单</button><button className="primary" onClick={exportQuote} disabled={busy==='export'}><Download size={16}/>{busy==='export'?'正在生成…':'导出比价 Excel'}</button></div>
    </header>
    <div className="simple-content"><section className="sheet-area" aria-label="当前报价表">
     <QuoteTable lines={quote.lines} selected={selected} onSelect={setSelectedId} reviews={db.reviews} onEvidence={openEvidence} observed={observed}/>
    </section></div>
   </main>:<main className="valuation-entry">
    <p className="entry-eyebrow">第 1 步 · 项目接入</p>
    <h1>开始一份采购比价</h1>
    <div className="entry-options">
     <button className="entry-choice" onClick={()=>{setOA(true);setOAError('');}} disabled={!!busy}><Link2 size={23}/><strong>从飞书导入报价</strong><span>支持飞书电子表格、知识库报价页和云盘 Excel 附件。</span><ArrowRight size={16}/></button>
     <button className="entry-choice" onClick={()=>dialog.current.showModal()} disabled={!!busy}><FileUp size={23}/><strong>上传本地 Excel</strong><span>上传 Excel 报价单，可关联已有或新建项目。</span><ArrowRight size={16}/></button>
    </div>
    {oa&&<form className="entry-oa" onSubmit={submitOA}>
     <label>飞书表格或附件链接<input name="link" type="url" placeholder="https://…feishu.cn/wiki/…" required/></label>
     <div className="entry-fields"><label>项目编号（选填）<input name="projectCode"/></label><label>项目名称（选填）<input name="projectName"/></label></div>
     <label>工作表名称（多张报价表时填写）<input name="worksheet" placeholder="例如 CG"/></label>
     {oaError&&<p role="alert" className="form-error">{oaError}</p>}
     <button className="primary" disabled={!!busy}>{busy==='oa'?'正在读取…':'读取并开始比价'}</button>
    </form>}
    <button className="entry-demo" onClick={showDemo} disabled={!!busy}>{busy==='demo'?'正在载入…':'先看已核样例'} <ArrowRight size={15}/></button>
   </main>}
  <ImportDialog dialog={dialog} quotes={db.quotes} onImported={imported} onNotice={setNotice}/>
 </>;
}
