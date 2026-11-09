# 输入、包含关系与金额

## JSON 基础

CLI 接受对象数组，或含 `rows`（也接受 `items`/`lines`）数组的对象。每条真实清单行一个对象。顶层 `project`、`currency` 可作默认值；行级币种覆盖默认。下例只有结构，不包含成交样本：

```json
{
  "project": "用户项目",
  "currency": "CNY",
  "rows": [
    {
      "line_id": "device-01",
      "item_name": "互动装置",
      "kind": "whole_scope_quote",
      "configuration": "旋钮、控制器及面板组合",
      "scope": "制作及集成，具体包含范围见原合同",
      "quantity": "1",
      "unit": "组",
      "unit_price": null,
      "subtotal": null,
      "source_locator": "合同附件第2页，组合标题",
      "source_original_fields": {"装置名称": "互动装置", "配置": "旋钮、控制器及面板组合"}
    },
    {
      "line_id": "device-01-knob",
      "parent_line_id": "device-01",
      "parent_item_name": "互动装置",
      "item_name": "旋钮",
      "quantity": "2",
      "unit": "个",
      "unit_price": null,
      "subtotal": null,
      "source_locator": "合同附件第2页，配置第1行",
      "source_original_fields": {"配置子件": "旋钮", "数量": "2", "价格": "未列"}
    }
  ]
}
```

`parent_line_id`、`parent_item_name` 和用户自定义层级字段可随行保留；包含关系由模型按原件核实，CLI 不自动证明其成立。每行仍需明确 `item_name`，不能把空白标题/合计伪装物料以绕过导入。

|字段|含义|
|---|---|
|`item_name`|真实物料/设备/服务名称；项目标题另存|
|`brand`、`model`|原件品牌与型号，不因名称相似补型号|
|`spec`|材质、结构、尺寸、功率等技术规格，保留原读数|
|`description`|原文工艺、工作内容和背景|
|`configuration`|组合、附件及每套组成|
|`scope`|设备供货/租赁/安装/制作工序等具体交付范围|
|`quantity`、`unit`|计价数量与单位；人数/天数/每工时长另保留原字段|
|`unit_price`、`subtotal`|原件明确单价和金额；明确同一对象的数量及总额且经授权可推算单价，需标记计算值|
|`currency`|原币，例如CNY/HKD/USD/SGD；未写不猜|
|`supplier`、`project`|原供应商和项目；不得凭上下文虚构|
|`record_id`、`line_id`、`project_key`|原系统关联ID；缺少时CLI生成技术ID，不代表新项目证据|
|`source_token`、`source_locator`、`source_evidence`|用户自己的来源标识、页/表/行和文件摘要|
|`source_original_fields`|原字段原值，包含合并列、备注、日数、包价等|

JSON 任意附加字段随行保留。表头别名字典只用于已经理解的常用表头，不是非标准合同语义提取器。名称与规格合并时，规范字段与原单元格并存；明确何者是产品、何者是配置，不能把备注里的工人数当物料名。

## 计费对象与版本

- 保留整包、真实子件、未定价配置、单独服务、合计/优惠和变更前后版本的角色。合计用于核算，不能再次作为可累加BOM物料。
- `kind: "whole_scope_quote"` 表示整项报价，不是缺BOM时捏造的一组分项。子件未报价则保留空价，不均摊父项。
- 数量×单价不一定是完整式：源表可能为人数×日数×日单价、数量×日数×单价＋包价或按整个服务包计价。保存原公式与各因子，不套统一列位。
- 同一物理行的原生表格和OCR是两种证据，不是两次采购。不同真实行、变更前后版本、不同合同不能仅同名去重；保留定位和别名证据。
- 同一套里三只角色与每套一只、组合内一个旋钮与整组装置、设备租赁与采购、静态材质灯光与最终输出不是同价对象。

## 金额单位及财务换算

默认保留原币元。金额应是纯数字或 `null`；币种和单位分列。仅明确的万元标记才放大，例如表头 `单价（万元）`，或行级：

```json
{"currency":"CNY","money_unit":"万元","unit_price":"1.2","subtotal":"2.4"}
```

得到人民币12,000元及24,000元。两个金额列单位不同时用 `unit_price_amount_unit` 与 `subtotal_amount_unit` 分别指定。CLI在 `money_normalization` 保留原读数、原单位和归一证据；再次导入已归一结果不重复放大。

外币示例（合成汇率，仅演示字段）：

```json
{
  "currency":"HKD",
  "money_unit":"万元",
  "unit_price":"2",
  "confirmed_rate_to_cny":"0.92",
  "finance_conversion_evidence":"用户财务已确认的该笔换算记录"
}
```

原币为HKD20,000元，按明确确认依据得到人民币18,400元。没有确认汇率和依据时只保留HKD20,000，显示待关联财务折算价，不改标CNY、不判断跨币种高低。换算依据可用 `finance_conversion_evidence` 或显式 `source_evidence`。也支持逐金额字段的币种/汇率，例如 `unit_price_currency`、`unit_price_confirmed_rate_to_cny`。

台账已确认的含税人民币总额与合同原币总额直接关联，税费/汇率不成为内容提取门槛；但合同总额换算不能冒充某条子BOM的人民币单价依据。

## 历史状态与价格判断

`--history` 默认记录是 `user_history_pending_review`。它可供检索，但不代表模型或CLI已核过原件。只有真正核过明细与来源时才用 `record_status: "contract_reconciled"`；整项已核用 `whole_scope_source_checked`。保留采购/租赁等 `agreement_type` 和具体 `scope`。

直接高低判断还需型号规格、组成、交付范围、计价单位、金额币种与证据都可比，原明细能按真实计费式复算。整包、部分工作、组合子件及工艺只能说明相关范围，不代表整项价格。没有参数与参数相同是两回事。

`--data` 适用于用户已有的完整兼容Data Hub：台账、合同关联/来源登记、明细、层级及复核状态必须通过引擎校验。它不是任意JSON目录，也不提供自动实时飞书访问。普通用户优先提供自己的 `--history` 文件；缺资料会明确保留，不使用发布者的数据补齐。

## 报告交付

把 `compare` 的JSON交给 `report`，再由Codex核对具体候选并补充说明。至少交付：物料/服务、当前价格、匹配对象、供应商、历史价格、差异、参考覆盖范围、建议动作。来源定位用于回查，用户只需看采购结论时可放在附注。

无参考应区分：缺少当前规格、已有记录待核价、原件附表缺失、历史库尚未收录、检索尚未对应。无法区分时直说证据不足，不能替用户断定“完全非标”或“从未采购”。
