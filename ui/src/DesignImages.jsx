import React,{useEffect,useId,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import './design-images.css';

export function DesignImages({images=[],name}){
 const available=images.filter(i=>/^(data:image\/|https:\/\/|\/(?!\/))/.test(i.preview_url||''));
 const [active,setActive]=useState(null),[zoom,setZoom]=useState(1),[failed,setFailed]=useState(false);
 const dialog=useRef(null),trigger=useRef(null),title=useId();
 useEffect(()=>{
  if(active===null)return;
  const node=dialog.current,previous=document.body.style.overflow;
  node.showModal();document.body.style.overflow='hidden';
  return ()=>{node.close();document.body.style.overflow=previous;trigger.current?.focus({preventScroll:true});};
 },[active]);
 if(!available.length)return null;
 function open(e,index){e.stopPropagation();trigger.current=e.currentTarget;setZoom(1);setFailed(false);setActive(index);}
 function close(){setActive(null);}
 return <><details onClick={e=>e.stopPropagation()}><summary>查看设计原图</summary>{available.map((image,index)=><button type="button" className="design-image-thumbnail" key={index} aria-label={`放大${name}设计原图 ${index+1}`} onClick={e=>open(e,index)}><img src={image.preview_url} alt={`${name}设计原图 ${index+1}`} loading="lazy"/></button>)}</details>{active!==null&&createPortal(<dialog ref={dialog} className="design-image-dialog" aria-labelledby={title} onCancel={e=>{e.preventDefault();close();}} onClick={e=>{e.stopPropagation();if(e.target===e.currentTarget)close();}} onKeyDown={e=>e.stopPropagation()}><header><h2 id={title}>{name} · 设计原图 {active+1}</h2><div className="design-image-controls"><button type="button" disabled={zoom<=1} onClick={()=>setZoom(z=>Math.max(1,z-.5))} aria-label="缩小图片">−</button><button type="button" onClick={()=>setZoom(1)}>适应窗口</button><button type="button" disabled={zoom>=4} onClick={()=>setZoom(z=>Math.min(4,z+.5))} aria-label="放大图片">＋</button><button type="button" autoFocus onClick={close}>关闭</button></div></header><div className="design-image-viewport">{failed?<p role="alert">图片加载失败，请关闭后重试。</p>:<img src={available[active].preview_url} alt={`${name}设计原图 ${active+1}`} onError={()=>setFailed(true)} style={{width:`${zoom*100}%`,maxHeight:zoom===1?'100%':'none',objectFit:'contain'}}/>}</div></dialog>,document.body)}</>;
}
