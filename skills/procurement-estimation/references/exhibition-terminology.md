# 展馆报价的语义理解与参考边界

研究日期：2026-11-12。此文是采购匹配方法，不是设计规范、施工验收意见或自动价格等同性认证。

## 先理解交付对象，再识别术语

按每一行及其所属展项、表头、图片说明理解；不要把整份合同的背景词贴到每个物料上。项目名、地点和艺术家不是采购分类。名称保留原文，另填 `standard_object_name` 或 `standard_service_name`。

分类链路建议：业务领域 → 交付系统 → 对象/工序 → 构造与用途 → 有证据的规格。不同报价可有不同深度。采购对象、组成关系、交易范围、价格单位是不同维度，不强塞到一个同义词集合里。

模型先做下列判断，CLI 保存和校验，不能声称 CLI 已自行调用模型看图：
1. 这一行交付的是实物、数字资产、施工工序、设计服务，还是系统整包？
2. 名称是位置、展项主题，还是物料？用工艺、图片和同一行说明确定标准对象，并留下证据。
3. 构造拆成支撑/基层/饰面/设备/辅材/安装；不能把基层材料当最终饰面。
4. 分离尺寸、厚度、电气、光学、时长、分辨率和数量。图片只支持可见形态，未标尺寸不得按视觉猜数。
5. 正投/背投、室内/室外、供货/租赁/拆除、整机/部件等差异优先于词面相似度。

## 术语关系要有类型

| 关系 | 示例 | 处理 |
|---|---|---|
| 常见同对象表达 | 天花/吊顶；展示柜/陈列柜；导轨式射灯/轨道射灯 | 扩展候选；继续核材料、尺寸、功能、单位 |
| 材料俗名 | 亚克力/有机玻璃/PMMA；雪弗板/PVC发泡板；夹板/胶合板/多层板 | 仅归一材料族，等级、厚度、阻燃、表面处理不能省略 |
| 条件相近 | 木饰面/木皮饰面；播控主机/媒体服务器 | 要核构造或实际播放能力；品牌和配置保留 |
| 部件与整套 | 灯箱画面/灯箱成品；灯带/线性灯具 | 整套只作范围参考，不当部件单价；反向不能代表整套 |
| 同用途异材料 | GRG造型/玻璃钢造型；铝单板/铝塑复合板 | 可展示差异参考，不认同规格价格 |
| 不同对象 | 中控系统/播放服务器；展陈系统/展墙；数字模型/实物沙盘 | 不因同项目、同颜色或同数量单位匹配 |

不要把 A≈B、B≈C 推导成 A≈C。不要凭单个“装饰”“安装”“艺术”“系统”扩充同义词。

## 按专业拆解

### 空间与装饰
- 地台：承重框架、基层板、面层、收口分开；地台整包与地胶不等价。
- 展墙：龙骨、基层、饰面、造型、展窗、设备开孔等组成要保留。展墙里的可调平台、悬吊与展陈支架是展具系统，不是墙面饰材。
- 吊顶/天花：钢架、板材、GRG造型与涂装分别理解。不能因为都“白色弧形”就归同材。
- 隔墙：轻钢龙骨石膏板系统不是承重结构；防火、防潮、隔声和单双面构造是参数，不能据外观推定。[Knauf系统](https://www.knauf.com.cn/app/Default.aspx)
- GRG/GFRG 是玻纤增强石膏复合材料；其模制造型与板材现场拼装不同。[Formglas材料说明](https://www.formglas.com/pdfs/datasheets/Formglas-GFRG-Product-Data-Sheet-V18.1%2B.pdf)
- GRP玻璃钢以树脂和玻纤构成，不能与GRG合并材料身份。[Stevensons说明](https://stevensons-of-norwich.co.uk/bespoke-grp-103-w.asp)

### 图文与标识
- UV打印是工艺，不是承印材料。地贴、墙贴、展板和灯箱布不能仅因同用UV就直接比价。
- 地面图文应核步行环境及保护层；墙用贴膜不能自动作为同规格地贴。[3M地面图文应用](https://www.3m.com.cn/3M/zh_CN/graphics-signage-cn/applications/floors-and-sidewalks/)
- 亚克力/有机玻璃属于PMMA；品牌仍独立保存，PC不是PMMA，浇铸和挤出也要保留。[PLEXIGLAS材料说明](https://www.plexiglas.de/en/service/product-info/what-is-plexiglas)
- 灯箱透光画面与灯箱框体、光源分开。扩散织物是可构成灯箱的材料，不是灯箱整套。[ShowTex](https://www.showtex.com/en/products/soft-goods/projection-light-effects/projection-fabrics/backlit-premium)

### 灯光
- 安装方式（轨道、嵌入、悬吊）、形态（线性、环形）、配光（重点照明、洗墙）是独立维度；轨道灯并不固定一种光束。[ERCO展馆照明](https://www.erco.com/en/knowledge/culture/discovering/)
- 功率相等不能代替光束角、显色指数、色温、调光协议、防护等级比对。不能把灯带当星星灯；裸灯带不能当带型材和驱动的线性成品灯。
- DMX是控制协议；RDM是DMX体系内的双向通信方式，不等于网线型号。[ETC RDM](https://www.etcconnect.com/webdocs/controls/colorsource_onlinehelp/en/Content/HelpAboutRDM.html)

### 多媒体与数字内容
- 播放服务器负责内容播放；中控的控制对象和接口另核，不因同为主机而合并。
- 投影机、镜头、吊架、幕面、融合调试、影片内容分别交付。几何校正和边缘融合相关但不是同一工序。[Barco mapping](https://www.barco.com/en/solutions/projection-mapping)
- 正投和背投是不同条件；幕布、纱幕、透光织物不能无条件互换。[Rosco投影材料](https://us.rosco.com/en/node/492)
- 建模是几何资产，材质/贴图是表面视觉属性，动画、绑定、灯光、渲染、后期剪辑是不同工作。按“场景制作”一个名称不能推断全部包含。[Autodesk建模](https://www.autodesk.com.cn/solutions/3d-modeling-software)、[纹理映射](https://www.autodesk.com.cn/solutions/texture-mapping)
- 数字内容的秒数、帧率、分辨率、版本数、屏幕适配和修改轮次都是价格条件，不能与实物3D打印混淆。

## 输出和审校

每个候选说明：标准对象、分类链、已知共同点、关键差异、未写参数、整套/部分范围、计价单位。材料、型号、尺寸不确定时保留，不猜填。空价不是零元，零元也不自动代表免费。只输出用户要求的比价表。

新表达由模型结合原行证据归一；有歧义的词不直接加入全局别名。把典型成功案例和反例加入测试。这里的术语库是可扩展的候选检索知识，不代表历史库已全量重新审核。
## 组合图文、设计阶段与外观参照

NPS 展览规范分别讨论实体图文、数字节目、设备和结构；实体图文也可由立体字、底板与印刷组合。估算由区域到展项再到制作明细逐步细化。应用到本工具：必须比较同一交付粒度，设计费不能匹配被设计的墙体，运输安装和运营维护不能混成制作单价。这是方法参考，不是本项目的法定计价规则。
来源：[NPS 展览设计制作规范，第8、13、15章](https://www.nps.gov/subjects/hfc/upload/NPS-Exhibit-Planning-Design-and-Fabrication-Specifications-2019.pdf)。

可丽耐是树脂与矿物填料构成的实体面材，不能直接等同普通亚克力板。“效果对标可丽耐”是外观参照，不证明使用可丽耐。保留原文，材质归类只取明确的采购材料表述；铜色或铜质纹理也不证明采用铜板。
来源：[DuPont What is Corian](https://www.dupont.com/content/dam/dupont/amer/us/en/corian/public/documents/en/what_is_corian_r_.pdf)。

## 模型理解到可验证字段

先逐行理解对象、工序、交付范围、包含与排除项，再向 CLI 提供结构化结果；不要声称 CLI 自己调用了模型。组合项可添加 `comparison_components`，每项提供 `name` 和原文中的 `source_text`。原文“标题金属立体字；正文丝网印”可以拆出两个子件；没有分项金额就不分摊价格。引擎只接受能定位到当前行的证据，不把“不含、甲供、另计”的条款当作已包含子件。

```json
{"comparison_components":[{"name":"金属立体字","source_text":"标题金属立体字"},{"name":"丝网印图文","source_text":"正文丝网印"}]}
```

消防疏散标识与一般展陈导视按不同功能比较。显色指数 ≥90 保留最低要求，不改写成实测 90。模糊同义词不能消除这些差别。


## 名称中的多个维度

“轨道安装的洗墙灯”包含安装方式和配光用途，不能只凭“轨道”归为普通射灯。宽光束也不自动等于洗墙配光；不同品牌的示例角度不能当所有产品的固定参数。[ERCO 精准照明](https://www.erco.com/en/knowledge/culture/white-cube/setting-precise-accents/)

图示能辅助判断形态、组合和位置，不能无依据推断材料牌号、隐藏结构、功率或防火等级。透光织物可用于灯箱和布景，不自动等于投影幕，需核用途与型号。[ShowTex 扩散织物](https://www.showtex.com/en/products/soft-goods/projection-light-effects/projection-fabrics/backlit-premium)

操作次序：读整行、表头、图片和相邻分组；区分位置名与采购对象；拆出材料、工艺、尺寸、功能和包含项；判断同义或仅条件相似；生成有证据的字段和候选；逐项核价格单位与范围。未命中要反查组合子件和不同表达，不只降低相似度阈值。

## 材料名称与表面效果的补充边界

GFRC/GRC 是水泥基玻纤复合材料，不能因为都含玻纤就与石膏基 GFRG/GRG 或树脂基 GRP/FRP 合并。参考：[Formglas GFRC-L 规格](https://www.formglas.com/pdfs/specifications/Formglas_GFRC-L_Specification_v07-2015.pdf)。

装饰膜可呈现木纹、石纹等外观，外观不等于基材；3M DI-NOC 的 PO 系列还说明不同系列的膜材料不一定相同，不能把所有装饰膜统一猜为 PVC。参考：[3M DI-NOC PO 技术资料](https://multimedia.3m.com/mws/media/2397812O/3m-di-noc-e-series-po-polyolefin-film-tech-data-sheet.pdf)。

## 隔墙数量词的语义

“双面”说明两侧，“双层板”说明板层数，“双层龙骨”说明骨架体系，不能相互改写。单层龙骨也可配单层或多层板。名称相同仍需核板层数、板厚、骨架、填充和面层施工；原文只写双面时，不补猜双层。参考：[可耐福隔墙系统](https://www.knauf.com.cn/app/list.aspx?cid=72620543991349248)、[双层龙骨构成](https://www.knauf.com.cn/about/show.aspx?cid=72339069014638592&id=855)。
