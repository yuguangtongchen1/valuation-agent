# Valuation Agent

将报价单导入为明细，按用途、交付内容、型号、规格和组合查询历史报价，输出比价表和采购建议。CLI 与工作台共用归类和检索引擎；不会仅凭物料名称判断价格高低。

发行包只含通用代码和合成示例，不含公司的合同、台账、图片、Token 或登录状态。所有命令在本地运行，不自动上传文件，也不自动访问飞书。

## 安装与演示

Python 3.9 或以上。建议使用独立环境：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install git+https://github.com/yuguangtongchen1/valuation-agent.git
.venv/bin/valuation-agent demo --output-dir ./demo-output
```

演示会生成 `quote.json`、`history.json`、`comparison.json` 和 `report.md`。所有项目、供应商及金额均为合成数据。报告演示同配置参考、材质差异、组合中的部分子件及未找到参考四种情况。

## 七个命令

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

# 6. 比价结果下的结构化采购建议
valuation-agent report ./comparison.json --out ./advice.md
```

`report --threshold 0.15` 表示相对历史参考超过 15% 时提示偏高或偏低。单条参考只代表某次历史报价，多个项目的区间也不代表市场合理价格。供应商、匹配依据、规格差异及缺参考的补充动作会一并列出。

金额统一显示为人民币元。明确的 `万元` 标注会乘以 10,000，保留原读数、原单位和转换证据；已经转换的元金额再次导入不会重复放大。外币万元先换成原币元，不会因此变成人民币。外币只有明确的 `confirmed_rate_to_cny` 和 `source_evidence` 或 `finance_conversion_evidence` 时才生成 `*_cny_yuan`；否则显示“待关联财务折算价”，同时保留原币原值，不判断高低。

## 输入格式

支持 JSON、UTF-8 CSV；安装可选依赖后支持 XLSX：

```sh
python3 -m pip install "valuation-agent[excel] @ git+https://github.com/yuguangtongchen1/valuation-agent.git"
valuation-agent import ./quotation.xlsx --worksheet 报价 --out ./quote.json
```

XLSX 多工作表时必须明确选表；读取公式的已有缓存值，不执行公式。一个 JSON 对象表示一个真实清单行；整项报价保留为一条，不捏造子件价格。数量、单位、单价、金额分列，不从总价倒推单价。字段缺失保留为空。

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
