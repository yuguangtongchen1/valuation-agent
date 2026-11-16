import React,{useEffect,useLayoutEffect,useId,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import './design-images.css';
import {clampZoom,fitImage,zoomScroll} from './image-zoom.mjs';

export function DesignImages({images=[],name}){
 const available=images.filter(i=>/^(data:image\/|https:\/\/|\/(?!\/))/.test(i.preview_url||''));
 const [active,setActive]=useState(null),[zoom,setZoom]=useState(1),[failed,setFailed]=useState(false);
 const [natural,setNatural]=useState({width:0,height:0}),[bounds,setBounds]=useState({width:0,height:0});
 const base=fitImage(natural.width,natural.height,bounds.width,bounds.height);
 const geometry=useRef(base);geometry.current=base;
 const dialog=useRef(null),trigger=useRef(null),viewport=useRef(null),anchor=useRef(null),zoomRef=useRef(1),title=useId();
 function changeZoom(next,x,y){
  const node=viewport.current;if(!node)return;
  const old=zoomRef.current,value=clampZoom(next);
  if(value===old)return;
  const rect=node.getBoundingClientRect(),px=x==null?node.clientWidth/2:x-rect.left,py=y==null?node.clientHeight/2:y-rect.top;
  anchor.current={left:zoomScroll({pointer:px,scroll:node.scrollLeft,viewportSize:node.clientWidth,baseSize:geometry.current.width,oldZoom:old,newZoom:value}),top:zoomScroll({pointer:py,scroll:node.scrollTop,viewportSize:node.clientHeight,baseSize:geometry.current.height,oldZoom:old,newZoom:value})};
  zoomRef.current=value;setZoom(value);
 }
 function fit(){zoomRef.current=1;anchor.current={left:0,top:0};setZoom(1);viewport.current?.scrollTo(0,0);}
 useLayoutEffect(()=>{if(anchor.current&&viewport.current){viewport.current.scrollTo(anchor.current.left,anchor.current.top);anchor.current=null;}},[zoom]);
 useEffect(()=>{
  if(active===null)return;const node=viewport.current;
  function wheel(e){e.preventDefault();const delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?node.clientHeight:1);changeZoom(zoomRef.current*Math.exp(-Math.max(-100,Math.min(100,delta))*(e.ctrlKey ? .015 : .003)),e.clientX,e.clientY);}
  node.addEventListener('wheel',wheel,{passive:false});
  return ()=>node.removeEventListener('wheel',wheel);
 },[active]);
 useEffect(()=>{
  if(active===null)return;
  const node=dialog.current,previous=document.body.style.overflow;
  node.showModal();document.body.style.overflow='hidden';
  const view=viewport.current;const measure=()=>setBounds({width:view.clientWidth,height:view.clientHeight});
  measure();const observer=new ResizeObserver(measure);observer.observe(view);
  return ()=>{observer.disconnect();node.close();document.body.style.overflow=previous;trigger.current?.focus({preventScroll:true});};
 },[active]);
 if(!available.length)return null;
 function open(e,index){e.stopPropagation();trigger.current=e.currentTarget;zoomRef.current=1;setZoom(1);setFailed(false);setNatural({width:0,height:0});setActive(index);}
 function close(){setActive(null);}
 return <><details onClick={e=>e.stopPropagation()}><summary>查看设计原图</summary>{available.map((image,index)=><button type="button" className="design-image-thumbnail" key={index} aria-label={`放大${name}设计原图 ${index+1}`} onClick={e=>open(e,index)}><img src={image.preview_url} alt={`${name}设计原图 ${index+1}`} loading="lazy"/></button>)}</details>{active!==null&&createPortal(<dialog ref={dialog} className="design-image-dialog" aria-labelledby={title} onCancel={e=>{e.preventDefault();close();}} onClick={e=>{e.stopPropagation();if(e.target===e.currentTarget)close();}} onKeyDown={e=>e.stopPropagation()}><header><h2 id={title}>{name} · 设计原图 {active+1}</h2><div className="design-image-controls"><button type="button" disabled={zoom<=1} onClick={()=>changeZoom(zoomRef.current-.5)} aria-label="缩小图片">−</button><button type="button" onClick={fit}>适应窗口</button><button type="button" disabled={zoom>=4} onClick={()=>changeZoom(zoomRef.current+.5)} aria-label="放大图片">＋</button><button type="button" autoFocus onClick={close}>关闭</button></div></header><div ref={viewport} className="design-image-viewport" title="滚轮或触控板捏合缩放图片">{failed?<p role="alert">图片加载失败，请关闭后重试。</p>:<div className="design-image-stage" style={{width:Math.max(bounds.width,base.width*zoom),height:Math.max(bounds.height,base.height*zoom)}}><img src={available[active].preview_url} alt={`${name}设计原图 ${active+1}`} onLoad={e=>setNatural({width:e.currentTarget.naturalWidth,height:e.currentTarget.naturalHeight})} onError={()=>setFailed(true)} style={{width:base.width?base.width*zoom:undefined,height:base.height?base.height*zoom:undefined}}/></div>}</div></dialog>,document.body)}</>;
}
