---
name: procurement-estimation
description: 理解非标准合同和报价单，关联项目、装置及BOM明细，用 valuation-agent 查询历史参考并生成可回查的比价表。适用于报价导入、归类、规格和组合对照、历史报价检索及比价表输出。
---

# 采购估价

先理解实际交付内容，再比较价格。Codex 负责逐份理解非标原件、辨认字段和复核候选；`valuation-agent` 负责归一、规则归类、检索和表格输出，不自带 OCR 或远程模型；飞书读取需安装并授权官方飞书 CLI。

## 开始

使用用户已授权的文件或只读数据源。已有授权和任务范围内直接完成，不逐步索要确认；关键字段有歧义时保留原文和缺口，继续处理不受影响的记录。原件和用户数据留在用户控制的位置，公开仓库不包含真实合同、报价或凭据。

有 CLI 时先运行 `valuation-agent --help`。未安装时使用 Python 3.9+ 和独立环境：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'valuation-agent[excel] @ git+https://github.com/yuguangtongchen1/valuation-agent.git'
```

随后用 `.venv/bin/valuation-agent` 替代下方的 `valuation-agent`。Skill 不需要私有仓库或其脚本。

## 界面交付约束

使用原版完整 React 工作台，不新写简化上传页，不替换原有三级步骤、分组报价表、右侧比价、详情与规格对照、导出样式。访问码只作为首次激活步骤；激活后由 `launch` 提供包内原版构建。用户仍看到简化页面时，升级至少0.2.10，结束旧版本机进程，再启动新URL；只刷新旧服务不会升级程序。已有有效访问码继续使用，不重复签发。

## 用户拿到安装指令和访问码时

用户要求直接使用/打开界面时，安装带 Excel 依赖的最新版，然后运行 `valuation-agent launch`，保持进程运行并打开输出的 localhost URL。不要只展示 help、跑 demo、生成 JSON 后结束。首次无配置时界面显示访问码输入；已有配置直接进入上传报价。界面内可以上传、整单比价、看历史参考、打开合同明细、导出 Excel。

访问码为 `VA1.` 开头、可撤销的个人内部凭证，不能写进公开 Skill、安装脚本、仓库或网页 URL。用户已经在聊天提供时，用进程标准输入交给 `valuation-agent activate`，不回显；或读取用户给定的本地访问码文件 `valuation-agent activate --file <path>`。不把码放进命令参数，也不将某人的访问码共享给其他人。若用户未提供，只打开激活页，不捏造凭证。

Windows 解释器用 `py`、虚拟环境 `.valuation-env\Scripts\python.exe`；macOS/Linux 用 `python3`、`.valuation-env/bin/python`。安装 `valuation-agent[excel]`，不是仅基础包。包内自带网页，不需要 Node 或另取前端目录。默认随机可用端口，避免冲突；远程执行环境自动打开浏览器失败时，明确给出 URL 并打开本机浏览器。服务应持续运行直至用户完成。

## 内部服务器模式

管理员已提供访问配置时优先用 `--remote /path/to/remote.json`。使用者只需安装 CLI 和 Excel 依赖；不用下载历史数据库。不要让用户把 token 写入聊天、参数或仓库，只读取管理员已放好的配置路径。不要把离线副本当作服务器实时数据。

```sh
valuation-agent run ./quotation.xlsx --worksheet 报价 --remote /path/to/remote.json --output-dir ./比价结果
valuation-agent search '用途 型号 规格' --remote /path/to/remote.json
valuation-agent contract <返回的record_id> --remote /path/to/remote.json --out ./合同明细.json
```

`run` 只生成两张工作表的 Excel 和 JSON，不生成采购建议。远程模式只发送检索字段，原文件不上传；返回的历史参考仍属于内部数据。401 联系管理员核对凭证，403 核对权限，429 稍后重试，503 等当前查询完成；不要循环重试或绕过 HTTPS。Windows 使用 `py` 和 `.venv\Scripts\valuation-agent.exe`，macOS/Linux 使用 `python3` 和 `.venv/bin/valuation-agent`。

## 理解并导入

遇到合同、PDF、DOC/DOCX、图片、合并表头、多个报价区块时，先读 [schema.md](references/schema.md)。直接复用已有原文、表格和 OCR 缓存；只有具体字段看不清、疑似错列或漏行时才回原页/图片。没有识别缓存且当前工具支持时再提取，不把任务调整当作重新扫描的理由。

逐份识别项目背景、装置/模块、真实物料或服务行、规格子行、备注、合计、版本及附表。表头可以合并、换位置或跨行，不能固定列号或把“材料名称/规格”当未知后改取备注。“2个人工”可能是备注，项目名称也不等于物料名。保留每张附表及未标价、零价的真实子行。

- 每个真实明细行一条 JSON，原始列和值保留在 `source_original_fields`；拆开的名称、型号、规格记录拆分依据和原件位置。
- 保存“项目→区域/工作包→装置/组合→子BOM”的包含关系，层级按原件，不固定三级。同合同不意味着所有物料都属于同一装置。
- 只有整项报价时保留一条 `whole_scope_quote`，关联背景、交付范围和原文；不虚构子项单价、不虚构数量或子件单价。
- 数量、单位、单价、小计、日数、每套组成及包价分别保留。先确认实际计算式，不能把所有表都套成“数量×单价”。
- 归类模板仅是类目和字段规范；模板零值、示例报价及新测试单不进入历史成交库。

标准 CSV/JSON，或已明确选表和表头的 XLSX / XLS，可直接导入：

```sh
valuation-agent import ./quote.json --out ./normalized.json
valuation-agent import ./quotation.xlsx --worksheet 报价 --out ./normalized.json
valuation-agent classify ./normalized.json --out ./classified.json
```

CLI 读取 Excel 公式的已有缓存值，不执行公式；多表逐张明确选择后由模型关联。非标资料先理解并生成 JSON，再导入，不声称 CLI 能直接识别所有合同。

## 检索与复核

```sh
valuation-agent search '型号或物料 规格' --history ./history.json --limit 20 --out ./search.json
valuation-agent compare ./normalized.json --history ./history.json --out ./comparison.json
```

历史 Excel 可用 `compare --history-worksheet 表名`，`search --worksheet 表名`。已有完整兼容 Data Hub 时将 `--history ./history.json` 换为 `--data ./private-data`；二者互斥，`--data` 不是任意 JSON 文件夹。连接飞书等来源须用当前可用的授权连接器，只读获取后再归一；本地缓存查询不能说成实时遍历了飞书。

对整张新报价逐行检查结果，不能第一次名称未命中就结束。先用途和实际功能→同层技术细类→型号、材质、尺寸、工艺和组合→交付与计费范围；再扩展相似对象、明确子件及工艺线索。名称别名帮助召回，不证明同物同价。用模型阅读原描述、候选规格和排除条件，对缺召回继续分解工艺/配置关键词检索，但不把无关候选凑成参考。

明确区分：直接可比、有规格差异的同类、整包、部分工作、组合子件、工艺参考。缺参数与参数明确不同要分别表达；相异材质/型号/范围应指出差异。整包或局部参考不判断整项高低，也不把一个包价重复计到所有子项。

归类借鉴“定义先行、细项优先、同层比较、组合看实际功能”的方法，不将海关编码规则机械当成采购价格算法。类别深度不固定；项目实例树、归类树和价格属性分开保存。

## 金额与建议

财务已确认的台账人民币金额直接关联，不反复审核税费或外汇口径；合同价格保留实际原币。明确 `万元` 才乘10,000，保留原值和单位，已归一金额不重复转换。外币万元转换后仍是原币，不能裸标 CNY；人民币单项价需要明确财务换算依据，不能用合同人民币总额反推单项汇率。详见 schema 金额字段。

复核状态是源文核对的结果，不能为获得“偏高/偏低”结果批量改成已核。单条历史报价仅是某次交易参考；即使多个项目有价格，也先排除重复证据、旧版本和范围差异。

最终默认只交付比价表，不在表格下附加采购建议、报价分析或长篇说明。表内保留当前物料与规格配置、参考物料、供应商、人民币价格、计价方式、差异、整包/子项范围和无参考原因。来源完整存入JSON和详情，原件页行定位不用塞进主表。

`report` 是兼容的可选文档命令，仅当用户明确要求分析或报告时调用。`demo` 使用合成数据，必须与真实历史分开。

币种须以原文明示为准，AUDIO 等名称不能按 ISO 代码前缀识别为澳元。财务比例折算只改变人民币展示，不升级成交或可比性状态；同文件本期付款比例不能称为整份 BOM 的付款分摊。行政报批、设计编程、设备采购、安装人工和复合服务分别归类，名称不明时保留待确认。

## 报价层级与版本

分项单价与有来源的整包总额分别检索和展示；整包不能充当单件单价。同一采购的城市方案、盖章版本可分别查看，按经济采购事项去重，不作为独立成交样本。

按服务类型和采购对象归类，品牌和项目背景不代替技术类别。数字内容、人员运营、设计、拍摄、设备采购和租赁分别判断。组合子件仅作部分参考；缺参数不代表一致。用户授权且数量与总额明确对应时，可计算总额÷数量，保留两位小数并标记计算值，不冒充原始单价。

逐行检查未命中和弱参考：区分未收录、漏召回、参数不足、缺分项价格、范围不同及非独立计价；无命中不能推断完全非标。真正没有附表时按服务描述和整项金额归档，不要求补不存在的附件；有附表但读不清时记录具体缺口。

完整兼容 Data Hub 可用 `valuation-agent audit --data ./private-data --out ./audit.json` 检查关联；通过不等于每个字段已核实或所有报价可比。

对于原件未标币种、但完整单项服务与财务台账已精确核对的记录，可直接关联该项人民币台账总额作为小计展示；保留未知原币种，不伪造汇率或单价。直接关联必须限定来源行和相同完整范围，不得让其他子项继承整笔金额。零台账记录不能一刀切；只有明确核过的无人民币价格依据档案排除人民币价格召回，BOM和原价仍保留。`audit` 的 `unconverted_reference_rows` 用于检查可检索价格池的人民币展示缺口。

用户提供内部专用的 Python 启动文件并要求启动时，使用 Python 运行该文件并保持工作台进程运行。文件负责安装、激活及打开原版界面，运行前后均无需在对话中复制文件里的个人访问码。飞书导入沿用本机已授权的飞书 CLI。

## 飞书链接导入：主动修复新电脑环境

用户粘贴飞书链接或遇到飞书读取失败时，不只返回“检查授权”。使用官方指南：https://open.feishu.cn/document/no_class/mcp-archive/feishu-cli-installation-guide.md 。

1. 在运行估价工作台的同一台电脑、同一用户环境检查 `lark-cli --version`、`node --version`、`npm --version`。缺少 Node.js 时按 Node.js 官方安装方式安装 LTS（含 npm/npx），不要复制其他电脑的凭据。
2. 缺少飞书 CLI 时，主动运行 `valuation-agent feishu-setup`；它按官方指南安装 `npm install -g @larksuite/cli` 和 `npx -y skills add https://open.feishu.cn --skill -y`。若已有 CLI，复用它；缺少官方 Skills 时补装 Skills。权限不足不自动 sudo，给出具体失败环节。
3. 阅读已安装的 lark-shared Skill，运行 `lark-cli auth status --json --verify`。仅未配置应用时运行 `lark-cli config init --new`，不覆盖已有配置。未登录/授权失效时按官方指南和 lark-shared 发起用户登录；展示授权链接及二维码，用户完成后收尾登录并复查状态。登录必须由接收方自己的账号完成；不将估价访问码当飞书 token。
4. 授权正常后，用飞书只读命令读取用户原链接，区分文件无权限、缺 scope、链接类型不支持、网络失败和表格解析失败。不要反复重装；不要把所有异常都归为未登录。仅请求所需读取权限，不输出密钥。
5. 新安装后重启工作台以刷新 PATH，并重试原链接；核对实际导入的工作表与行数，继续比价、详情和导出。无法完成时报告具体阻塞，本地 Excel 上传仍可使用。

普通本地 Excel 工作流不依赖 Node.js 或飞书 CLI；只在使用飞书来源时补齐这些依赖。

## 指定用户的一次复制交付

管理员提供已有个人访问码文件后，用 `valuation-agent handoff --access-file <个人访问码文件> --out <私密命令文件>` 生成一行命令；Windows 加 `--windows`。不新建权限、不共用其他用户的码，不输出命令内容到日志，不提交生成文件到 Git。输出文件不得已存在。

接收方将专属命令粘贴给 Codex 后，直接执行安装、标准输入激活和 launch，保持进程运行并打开本机 URL，不再要求手动填写访问码。先检查 Python 3.9+；Windows 使用 py，macOS/Linux 使用 python3。若授权已过期或撤销，停止并联系管理员，不重复安装或绕过授权。飞书导入仍需接收方自己的飞书授权。专属命令内含凭据，仅私发给对应人员，不在官网展示。

## 左侧对话与原版工作台联动

用户在聊天提供新报价时，先读取文件并理解字段、规格和组合；普通 Excel 可直接使用，非标表先用模型整理成 `{ "project": "项目名称", "rows": [{"item_name":"名称","spec":"规格","description":"工艺","quantity":1,"unit":"套","unit_price":100,"subtotal":100,"currency":"CNY"}] }` JSON，保留 source_locator 和原文。不能凭空补金额或规格。

运行 `valuation-agent launch --input <报价文件绝对路径> --worksheet <需要时指定工作表>`，保持服务运行，将返回的带 `?handoff=1` 的 URL 在可用的 Codex 右侧浏览器打开；无法控制面板时提供 URL，不声称已打开。已有远程配置可加 `--remote <路径>`。激活后会自动加载，无需用户再次上传。

AI 理解与候选复核由当前 Codex 完成；工作台通过服务器查询历史参考，不内置自动聊天模型。用户纠正后，原子更新同一 JSON 文件，页面约两秒检测新版本并更新表格；修改会清除旧参考缓存。不要只改左侧回复而不更新文件。新的报价文件可以另启动实例，避免混淆项目。同步只读取明确指定文件，不监听用户全部聊天或磁盘。完成后实际检查页面明细和导出，不将成功启动等同于比价正确。
