## 0.2.17 远程来源隔离修复

远程比价保留整份报价的来源标识，跨批次排除自身及关联版本，只启用当前版本。新增远程回归检查，CLI 测试共 68 项通过。

## 0.2.16 归类与来源隔离

新增核心功能、整机/部件归类边界和专家 QA；完善展陈术语与有原文证据的子件匹配。新报价排除自身来源，重复导入不增加样本，非当前版本不参与查询。Skill 增加行业案例与海关方法参考；内部采购分类不等于海关申报编码。远程查询引擎需由管理员单独升级，本地安装不会自动修改服务器。

## 0.2.15 非标准报价导入

支持先汇总后明细的 CSV/XLS/XLSX、非标准报价列名、尺寸内数量和多规格组合保留。复杂语义由配套 Skill 复核；不猜填、不自动摊价。

# Valuation Agent

将报价单导入为明细，按用途、交付内容、型号、规格和组合查询历史报价，输出可回查的比价表。CLI 与工作台共用归类和检索引擎；不会仅凭物料名称判断价格高低。

发行包只含通用代码和合成示例，不含公司的合同、台账、图片、Token 或登录状态。默认在本地运行，不自动访问飞书。显式使用 --remote 时，仅把报价检索所需字段发送到你配置的 HTTPS 接口，不发送原 Excel/PDF，也不下载历史数据库。

## 安装并打开操作界面

给指定内部用户两样东西：下面的安装启动命令，以及管理员单独提供的 `VA1.` 访问码。公开网站不含真实访问码，也不会因安装成功而自动获得公司数据权限。

macOS / Linux：

```sh
python3 -m venv .valuation-env
.valuation-env/bin/python -m pip install --upgrade 'valuation-agent[excel] @ git+https://github.com/yuguangtongchen1/valuation-agent.git'
.valuation-env/bin/valuation-agent launch
```

Windows（PowerShell）：

```powershell
py -m venv .valuation-env
.\.valuation-env\Scripts\python.exe -m pip install --upgrade "valuation-agent[excel] @ git+https://github.com/yuguangtongchen1/valuation-agent.git"
.\.valuation-env\Scripts\valuation-agent.exe launch
```

需要 Python 3.9+、Git 和联网，无需 Node.js、压缩包或历史数据库。`launch` 使用原有完整工作台：三级步骤、项目分组表格、右侧历史参考、合同明细、规格对照和原Excel导出均保留。网页直接由原React源码构建，未改成简化页面。`launch` 自动打开浏览器；首次粘贴访问码激活，之后直接上传报价。流程：上传 → 整单比价 → 点单价查看历史参考 → 点参考进入合同明细 → 导出 Excel。页面只在本机监听；命令进程要保持运行。远程桌面环境不能自动打开浏览器时，用终端输出的本机网址打开。

**直接粘贴给另一位 Codex 的说明：**

> 读取本仓库 README 和 skills/procurement-estimation/SKILL.md，安装最新版 CLI，然后运行 valuation-agent launch 并保持服务运行，打开输出的本机网址。使用我单独提供的访问码启用，不要只运行合成演示后结束。访问码不要写入代码、日志或 GitHub；若我直接在聊天提供访问码，用标准输入交给下述 activate 命令，不再回显它。完成后让我在操作界面上传报价，只输出比价表，不生成采购建议。

访问码是持有即授权的内部凭证，不是公开演示码；每人单独发放，到期/撤销后不能继续查询。若不方便在浏览器中粘贴，可执行 `valuation-agent activate` 并在隐藏输入中输入访问码；或用受限本地文本文件：`valuation-agent activate --file /path/to/access.txt`。不把访问码放在命令行参数中。

## 安装与演示

Python 3.9 或以上。建议使用独立环境：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade 'valuation-agent[excel] @ git+https://github.com/yuguangtongchen1/valuation-agent.git'
.venv/bin/valuation-agent demo --output-dir ./demo-output
```

演示会生成 `quote.json`、`history.json`、`comparison.json` 和 `report.md`。所有项目、供应商及金额均为合成数据。报告演示同配置参考、材质差异、组合中的部分子件及未找到参考四种情况。

## 常用命令

```sh
# 1. 生成合成演示
valuation-agent demo --output-dir ./demo-output

# 2. 导入，保留原始表头与字段
valuation-agent import ./quotation.csv --out ./quote.json

# 3. 多级归类与参数归一
valuation-agent classify ./quote.json --out ./classified.json

# 4. 检索指定历史资料，含标注为待核的记录
valuation-agent search "星形灯" --history ./demo-output/history.json

# 5. 用同一工作台引擎遍历历史、拆解规格和组合，生成比价结果
valuation-agent compare ./quote.json --history ./history.json --out ./comparison.json

# 6. 可选文档报告（仅在用户要求时运行）
valuation-agent report ./comparison.json --out ./advice.md
```

默认只交付比价表，不在下方附加采购建议或报价分析。`report` 保留为按需调用的兼容命令。

`report --threshold 0.15` 表示相对历史参考超过 15% 时提示偏高或偏低。单条参考只代表某次历史报价，多个项目的区间也不代表市场合理价格。供应商、匹配依据、规格差异及缺参考的补充动作会一并列出。

金额统一显示为人民币元。明确的 `万元` 标注会乘以 10,000，保留原读数、原单位和转换证据；已经转换的元金额再次导入不会重复放大。外币万元先换成原币元，不会因此变成人民币。外币只有明确的 `confirmed_rate_to_cny` 和 `source_evidence` 或 `finance_conversion_evidence` 时才生成 `*_cny_yuan`；否则显示“待关联财务折算价”，同时保留原币原值，不判断高低。

## 输入格式

支持 JSON、UTF-8 CSV；安装可选依赖后支持 XLSX / XLS：

```sh
python3 -m pip install "valuation-agent[excel] @ git+https://github.com/yuguangtongchen1/valuation-agent.git"
valuation-agent import ./quotation.xlsx --worksheet 报价 --out ./quote.json
```

Excel 多工作表时必须明确选表；读取公式的已有缓存值，不执行公式。一个 JSON 对象表示一个真实清单行；整项报价保留为一条，不捏造子件价格。数量、单位、单价、金额分列，不把整包总额分摊成虚构子件单价。字段缺失保留为空。用户明确授权且同一报价项的数量与金额对应时，可计算单价并标为计算值，不能冒充原件单价。

```json
{
  "project": "新项目",
  "currency": "CNY",
  "rows": [
    {
      "item_name": "星形灯",
      "model": "DEMO-STAR-A",
      "spec": "24V；1200W",
      "description": "设备供货",
      "configuration": "",
      "scope": "设备供货",
      "quantity": "2",
      "unit": "套",
      "unit_price": "120",
      "subtotal": "240",
      "supplier": "拟报价供应商"
    }
  ]
}
```

也识别常用中文表头，如物料名称、材料名称、型号、规格、工艺说明、配置、数量、单位、单价、金额、供应商、项目名称。`source_original_fields` 保留每行原字段。非标准合同表格应先由 Codex Skill 理解表头、合并列和上下文，明确映射后输出上述 JSON；CLI 不通过猜列处理 PDF、DOC 或图片。

金额单位可写在表头 `单价（万元）`、`金额（元）`，也可使用 `money_unit: "万元"`，或分别指定 `unit_price_amount_unit`、`subtotal_amount_unit`。`money_normalization` 保留逐字段原值与两步转换证据。换币证据示例：

```json
{"currency":"HKD","money_unit":"万元","unit_price":"2","confirmed_rate_to_cny":"0.92","finance_conversion_evidence":"财务已确认的对应折算记录"}
```

该示例得到原币 HKD 20,000 元、人民币 18,400 元；其中 0.92 是显式输入的合成示例汇率，程序不会自行查询或猜测汇率。

## 历史数据与复核状态

历史 JSON 格式与新报价相同，每行应补充项目、供应商及证据位置。提供 `record_id`、`line_id`、`project_key` 可保留原系统关联；没有时生成本地技术编号。项目未注明的记录不会被当成多个独立项目。

默认历史记录为 `user_history_pending_review`，可查询和展示，不能据此判断高低。只有经过原件复核的记录才应设置：

```json
{
  "record_status": "contract_reconciled",
  "agreement_type": "采购",
  "scope": "设备供货",
  "source_token": "用户自己的来源标识",
  "source_locator": "原合同第3页，清单第2行"
}
```

这只是传入数据的复核声明，CLI 不会因一个状态字段就声称重新核查过合同。整项服务可用 `kind: "whole_scope_quote"` 和 `record_status: "whole_scope_source_checked"` 保留；只能提供整项上下文，不能当作子件单价。只有整项总额、没有单价的记录可通过 `search` 查询，不从总额推算子件价格。

判断偏高/偏低还要求来源可用、无规格和范围冲突、已统一为人民币元、同计价单位、明确一致的交付范围、原始数量×单价与金额可复算。整包、部分工作、组合中的子件、工艺旁证都只作参考。项目归属待核、旧配置、被标记不可比的来源不进入价格参考。税率及台账换算差异不另设阻塞；外币单价不使用台账总额反推汇率，不跨币种裸比。

找不到参考时，报告区分已有待核线索与所选资料未检索到，不会直接断言该物料完全非标。

## 连接已有私有 Data Hub

```sh
valuation-agent search "灯控 网线" --data /path/to/private-data
valuation-agent compare ./quote.json --data /path/to/private-data --out ./comparison.json
```

`--data` 使用既有 `valuation.load` 校验台账、合同复核覆盖、项目层级及统一来源登记，再调用工作台 `lookup`。目录须包含现有 Data Hub 的台账、报价明细、覆盖清单、层级及复核进度文件；这不是任意 JSON 文件夹。缺件或关联错误会明确报错，不降级为假结果。`--history` 与 `--data` 二选一。

环境变量 `VALUATION_AGENT_FEISHU_TABLE_URL`、`VALUATION_AGENT_SOURCE_BASE_URL` 可选，只用于结果中的来源入口，不配置则不生成私有链接。CLI 不含默认公司地址，也不发起实时飞书查询。真实资料应保存在你控制的数据目录或私有仓库，不打包进入公开安装文件。

## 版本维护

安装包使用仓库内 `valuation_agent/_engine/` 的通用引擎快照。公开仓库不包含公司的历史数据。当前通过 GitHub 安装，没有发布到 PyPI；新版可在独立环境中重新安装对应 GitHub 版本。

### 校验私有 Data Hub

```sh
valuation-agent audit --data ./private-data --out ./audit.json
```

0.2.0 使用共享匹配引擎，区分整包总额和单项价格，报价版本分别展示、同一采购去重。关联通过不代表所有报价均可直接比较。

0.2.1 修复整包人民币展示缺口：支持同一完整服务与已确认人民币台账的精确总额关联，原币种未知仍保留未知；不会把总额分配给其他子项。`audit` 新增人民币展示覆盖检查。

0.2.2 改善同型号候选保留、组合/子件范围与源行去重；默认仅比价表和Excel，优化右侧参考与手机布局。

0.2.3 修复报价刷新/前进恢复、重复文件重开、失败重试和文件错误提示；本机工作台直接读取旧版XLS，保留缓存数值及合并表头。投影机整机不再以吊架、改色或镜头服务充当设备价格。

0.2.4 优化参考排序：同用途候选优先比较有效计费单位、报价范围和规格差异，再比较名称；每人月/每场费率不冒充普通单位。工作台侧栏隐藏供应商，详情保留，并随栏宽调整字号。

## 内部离线数据包

0.2.5 支持经校验的轻量数据快照。内部人员取得单独提供的数据包后，使用 `--data ./private-data` 查询或比价；无需服务器。启动时核验快照校验和、记录数量和合同关联，失败会报错。公开安装包仍不含真实数据。

```sh
valuation-agent search "灯控网线" --data ./private-data
valuation-agent compare ./quotation.xlsx --worksheet 报价 --data ./private-data --out ./comparison.json
```

离线数据保存在使用者电脑上，授权后无法远程撤销；请只分发给获准接触公司报价的内部人员。

## 内部服务器查询（0.2.8）

由管理员为指定人员分别提供访问配置（endpoint、token），不要把配置上传GitHub或复制进聊天。macOS/Linux配置文件须权限600。

```sh
valuation-agent run 新报价.xlsx --worksheet 报价 --remote /path/to/remote.json --output-dir 比价结果
valuation-agent search 灯控网线 --remote /path/to/remote.json
valuation-agent contract <检索返回的record_id> --remote /path/to/remote.json --out 合同明细.json
```

服务器只返回匹配结果，Excel和JSON在本机生成，默认不生成采购建议。每人凭证独立、可撤销、有到期时间和请求限额；授权结果仍可被使用者保存。原0.2.6/0.2.7离线副本不会因服务端撤销而被删除。


管理员提供的访问配置只放在使用者本机，不包含在公开仓库、Skill 或命令参数中。不要把 token 粘贴到 Codex 聊天；让 Codex 使用配置文件路径即可。Windows 使用 `py` 和 `.venv\Scripts\valuation-agent.exe`，macOS/Linux 使用 `python3` 和 `.venv/bin/valuation-agent`。客户端需要联网访问查询服务，无需下载历史数据包或部署自己的服务器。

0.2.10 恢复原版 React 工作台，撤除0.2.9简化主页面。首次激活后进入原版界面；原访问码继续有效，无需重新签发。飞书导入入口保留，实际读取需要使用者电脑另有飞书授权；仅访问码不授予飞书权限。

0.2.11 接回原工作台的飞书导入。获授权的同事可接收管理员提供的单文件 Python 启动器并直接交给 Codex 运行。启动器包含个人访问码及启动说明，应单独转交。
