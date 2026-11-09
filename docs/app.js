'use strict';
const installation = 'python3 -m pip install git+https://github.com/yuguangtongchen1/valuation-agent.git';
const codexPrompt = `请帮我安装并使用「估价 Agent」。

先读取公开仓库 https://github.com/yuguangtongchen1/valuation-agent 的 README，以及仓库内的 SKILL.md，按当前说明安装 CLI 和 Skill。先运行 valuation-agent demo，确认合成演示可用。

然后连接我提供且有访问权限的报价文件、历史合同或飞书资料。原始资料保存在我指定的位置。按项目 → 装置/服务 → BOM 明细保留包含关系；每行保留名称、型号、规格、组合、数量、单位、单价和金额。没有写明的字段保持缺失，不猜填。

对新报价先按用途、材质、型号、工艺和组合检索，再逐项核对范围和计费单位。分别显示同类参考、规格差异、整包参考和部分子件参考，说明匹配理由，并保留可回查的来源。

输出比价表和简洁的采购建议：哪些项目有历史参考、哪些需要进一步确认，历史供应商是谁；没有参考时，说明是资料缺口还是已有资料仍不足以判断。不同范围或单位的价格不要直接混算。先展示结果，等我检查后再进行后续写入。`;
const copies = {install:installation,demo:'valuation-agent demo',prompt:codexPrompt};
for (const button of document.querySelectorAll('[data-copy]')) {
 button.addEventListener('click', async () => {
  const value=copies[button.dataset.copy];
  const status=document.querySelector('#copy-status');
  try {
   if(navigator.clipboard?.writeText) await navigator.clipboard.writeText(value);
   else {
    const area=document.createElement('textarea');area.value=value;area.setAttribute('aria-label','待复制内容');
    area.style.position='fixed';area.style.top='0';area.style.left='0';area.style.width='1px';area.style.height='1px';
    document.body.append(area);area.select();const ok=document.execCommand('copy');area.remove();button.focus();if(!ok)throw Error('copy');
   }
   const original=button.dataset.copy==='prompt'?'复制使用提示词':'复制';
   for (const other of document.querySelectorAll('[data-copy]')) other.textContent=other.dataset.copy==='prompt'?'复制使用提示词':'复制';
   button.textContent='已复制 ✓';button.setAttribute('aria-label',original+'，已复制');
   if(status) status.textContent=button.dataset.copy==='prompt'?'已复制提示词，粘贴到 Codex 即可。':'已复制命令，粘贴到终端运行。';
  } catch {
   if(status) status.textContent='自动复制未成功，请选择下方命令或指南中的提示词手动复制。';
   if(button.dataset.copy==='prompt') window.location.href='./skill.html#prompt';
  }
 });
}
const promptText=document.querySelector('#codex-prompt');if(promptText)promptText.textContent=codexPrompt;
// Every name, price and project below is invented for this public interaction demo.
const demo=[
 {name:'发光导视牌',spec:'铝合金围边 + 透光板 + LED；600 × 900 mm',qty:4,unit:'套',price:680,total:2720,
  reference:{name:'发光导视牌',project:'合成案例 A · 导视系统',supplier:'演示供应商甲',price:540,unit:'套',label:'规格有差异',reason:'用途与发光结构相近；尺寸不同，当前面板材质未注明，需要先核对配置。',
   comparison:[['围边','铝合金','铝合金',false],['面板','透光板，材质未注明','亚克力板',false],['光源','LED','LED',false],['宽 × 高','600 × 900 mm','500 × 800 mm',true]],
   bom:[['发光导视牌','铝合金围边、亚克力面板、LED；500 × 800 mm','3','套','540','1,620'],['安装配件','配套安装件','1','项','120','120']]}},
 {name:'PVC 图案地贴',spec:'PVC 卷材 + UV 打印；含裁切与铺贴',qty:12,unit:'㎡',price:84,total:1008,
  reference:{name:'PVC 图案地贴',project:'合成案例 B · 地面装饰',supplier:'演示供应商乙',price:72,unit:'㎡',label:'施工范围有差异',reason:'材质和打印工艺相同；历史费用不含现场铺贴，不能直接按差价判断高低。',
   comparison:[['材质','PVC 卷材','PVC 卷材',false],['画面工艺','UV 打印','UV 打印',false],['裁切','包含','包含',false],['现场铺贴','包含','不包含',true]],
   bom:[['PVC 图案地贴','PVC 卷材、UV 打印、裁切；不含铺贴','15','㎡','72','1,080'],['包装运输','单次运输','1','次','160','160']]}},
 {name:'互动道具组合',spec:'旋钮 × 2 + 控制板 + 发光面板；整组制作',qty:1,unit:'组',price:4600,total:4600,
  reference:{name:'旋钮控制模块',project:'合成案例 C · 互动模块',supplier:'演示供应商丙',price:360,unit:'个',label:'仅部分子件参考',reason:'只找到旋钮控制模块。历史单件价格不能代替当前整组报价，控制板、面板和集成仍需补充参考。',
   comparison:[['参考范围','旋钮 + 控制板 + 发光面板','仅旋钮控制模块',true],['旋钮数量','2 个','1 个',true],['计费单位','整组','单个',true],['系统集成','包含','未注明',false]],
   bom:[['旋钮控制模块','旋钮、编码器、连接线','6','个','360','2,160'],['模块调试','仅模块联调','1','项','240','240']]}}
];
const money=value=>new Intl.NumberFormat('zh-CN').format(value);
let selected=0;let detailOpener=null;
const rows=document.querySelector('#demo-rows');
function renderRows(){
 if(!rows)return;
 rows.innerHTML=demo.map((row,i)=>`<tr class="${selected===i?'selected':''}" data-index="${i}"><td><button class="cell-name" data-select="${i}" aria-pressed="${selected===i}">${row.name}</button></td><td class="cell-spec">${row.spec}</td><td class="number qty-cell">${row.qty}<span class="sr-only">${row.unit}</span><span class="mobile-unit" aria-hidden="true">${row.unit}</span></td><td class="unit-cell">${row.unit}</td><td class="number price-cell"><button class="price-button" data-select="${i}" aria-label="查看${row.name}的历史参考" aria-pressed="${selected===i}">¥${money(row.price)}</button></td><td class="number amount-cell">${money(row.total)}</td><td class="reference-cell">${selected===i?`<div class="reference-box"><div class="reference-label">历史参考</div><div class="reference-result"><div><button class="reference-title" data-detail="${i}">${row.reference.name}</button><span class="reference-project">${row.reference.project}</span><span class="match-label">${row.reference.label}</span></div><button class="reference-price" data-detail="${i}" aria-label="查看${row.reference.name}历史报价详情">¥${money(row.reference.price)}<span> / ${row.reference.unit}</span></button></div></div>`:''}</td></tr>`).join('');
 document.querySelector('#selection-status').textContent=`正在对照：${demo[selected].name}`;
}
if(rows){
 renderRows();
 rows.addEventListener('click',event=>{
  const select=event.target.closest('[data-select]');if(select){const index=Number(select.dataset.select);const wasPrice=select.classList.contains('price-button');selected=index;renderRows();const target=rows.querySelector(`tr[data-index="${index}"] ${wasPrice?'.price-button':'.cell-name'}`);target.focus({preventScroll:true});}
  const detail=event.target.closest('[data-detail]');if(detail)openDetail(Number(detail.dataset.detail),detail);
 });
 document.querySelector('#reset-demo').addEventListener('click',()=>{selected=0;renderRows();document.querySelector('#selection-status').textContent='演示已重置，正在对照：发光导视牌';});
}
const dialog=document.querySelector('#reference-dialog');
function openDetail(i,opener){
 const row=demo[i],ref=row.reference;detailOpener=opener;
 document.querySelector('#detail-content').innerHTML=`<h2 class="detail-title" id="detail-title" tabindex="-1">${ref.name}</h2><p class="detail-subtitle">${ref.project} · ${ref.supplier}</p><h3>历史报价明细</h3><div class="detail-bom-wrap"><table class="detail-table detail-bom"><thead><tr><th>物料 / 规格</th><th>数量</th><th>单位</th><th>单价</th><th>金额</th></tr></thead><tbody>${ref.bom.map(b=>`<tr><td><strong>${b[0]}</strong><span class="bom-spec">${b[1]}</span></td><td class="number">${b[2]}</td><td>${b[3]}</td><td class="number">¥${b[4]}</td><td class="number">¥${b[5]}</td></tr>`).join('')}</tbody></table></div><h3 class="comparison-title">规格对照</h3><table class="detail-table"><thead><tr><th>参数</th><th>当前规格</th><th>历史规格</th></tr></thead><tbody>${ref.comparison.map(c=>`<tr><th scope="row">${c[0]}</th><td class="${c[3]?'different':''}">${c[1]}</td><td class="${c[3]?'different':''}">${c[2]}</td></tr>`).join('')}</tbody></table><p class="detail-note"><strong>${ref.label}：</strong>${ref.reason}</p>`;
 dialog.showModal();document.querySelector('#detail-title').focus();
}
function closeDetail(){dialog.close();if(detailOpener?.isConnected)detailOpener.focus();}
if(dialog){document.querySelector('#close-detail').addEventListener('click',closeDetail);document.querySelector('#back-to-row').addEventListener('click',closeDetail);dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeDetail();}});dialog.addEventListener('close',()=>{if(detailOpener?.isConnected)detailOpener.focus();});}
