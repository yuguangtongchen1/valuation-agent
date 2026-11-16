export const clampZoom=value=>Math.min(4,Math.max(1,value));
export function fitImage(width,height,viewportWidth,viewportHeight){
 if(!width||!height||!viewportWidth||!viewportHeight)return {width:0,height:0};
 const ratio=Math.min(viewportWidth/width,viewportHeight/height);
 return {width:width*ratio,height:height*ratio};
}
export function zoomScroll({pointer,scroll,viewportSize,baseSize,oldZoom,newZoom}){
 const oldOffset=Math.max(0,(viewportSize-baseSize*oldZoom)/2);
 const newOffset=Math.max(0,(viewportSize-baseSize*newZoom)/2);
 return Math.max(0,(scroll+pointer-oldOffset)*newZoom/oldZoom+newOffset-pointer);
}
