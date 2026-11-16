// Split semantic clauses only outside brackets; preserve dimensions and comparisons.
export function splitPoints(text='', {sentences=false, numbered=false, process=false}={}) {
 const points=[]; let current='', depth=0;
 const flush=()=>{const value=current.trim().replace(/^[，,]+|[，,]+$/g,'').trim();if(value)points.push(value);current='';};
 for(let i=0;i<text.length;i++) {
  const char=text[i];
  if('（(【['.includes(char))depth++;
  if('）)】]'.includes(char))depth=Math.max(0,depth-1);
  const marker=numbered&&depth===0&&(i===0||/\s/.test(text[i-1]))?text.slice(i).match(/^\d+[.、](?!\d)/):null;
  if(marker){flush();i+=marker[0].length-1;continue;}
  const separator=depth===0&&('；;'.includes(char)||(sentences&&char==='。')||(char==='\n'&&!/[，,]$/.test(current.trim())&&!/^[，,]/.test(text.slice(i+1).trimStart()))||(process&&'，,'.includes(char)&&/^(配排|无刷|集成|转速|圆形旋转|地台旁|地台上)/.test(text.slice(i+1))));
  if(separator)flush();else current+=char==='\n'?' ':char;
 }
 flush();return points;
}
