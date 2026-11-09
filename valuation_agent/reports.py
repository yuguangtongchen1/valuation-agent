"""Evidence-bounded procurement advice from the actual retrieval result."""
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from statistics import median

from .engine import modules


def numeric(value):
    try:
        parsed = Decimal(str(value))
        return parsed if parsed.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def text(value):
    return str(value or "未注明").replace("|", "\\|").replace("\n", " ")


def money_record(row, field="unit_price"):
    return modules()["money"].normalize_money_fields(row, fields=(field,))["money_normalization"][field]


def money(value, currency="", unit="", record=None):
    record = record or modules()["money"].normalize_money(value, currency)
    number = numeric(record.get("cny_yuan"))
    per = f"/{unit}" if unit else ""
    if number is not None:
        return f"人民币 {number:,.2f} 元{per}"
    base = numeric(record.get("base_amount"))
    if base is None:
        return "待关联财务折算价（原价未注明）"
    raw = str(record.get("raw_value"))
    raw_unit = str(record.get("raw_unit") or "")
    if raw_unit and not any(marker in raw for marker in ("万", "元")):
        raw += raw_unit
    return (f"待关联财务折算价（原币 {record.get('base_currency') or '未注明币种'} "
            f"{base:,.2f} 元{per}；原始读数：{raw}）")


def assessment(entry, threshold=Decimal("0.15")):
    query = entry["quote"]
    engine = modules()
    normal = engine["valuation"].norm
    unit = engine["classification"].billing_unit
    references = [ref for ref in entry.get("references", []) if ref.get("kind") != "ledger_match"]
    current_money = money_record(query)
    eligible = []
    for ref in references:
        label = ref.get("match_kind", "")
        past_money = money_record(ref)
        cny_ready = current_money.get("cny_yuan") is not None and past_money.get("cny_yuan") is not None
        differences = [value for value in ref.get("differences", []) if not (cny_ready and value == "币种不同")]
        if (ref.get("comparison_role") != "candidate" or ref.get("estimation_exclusion")
                or differences or ref.get("spec_differences")
                or not any(term in label for term in ("同型号", "同规格", "参数一致", "型号或规格与组合一致"))):
            continue
        # An exact label is still not evidence of an omitted model/spec or delivery scope.
        if not (query.get("model") or query.get("spec")) or not (ref.get("model") or ref.get("spec")):
            continue
        if not cny_ready:
            continue
        if not normal(query.get("unit")) or unit(normal(query["unit"])) != unit(normal(ref.get("unit"))):
            continue
        current_scope = normal(query.get("scope") or query.get("module"))
        past_scope = normal(ref.get("scope"))
        if not current_scope or not past_scope or current_scope != past_scope:
            continue
        price = numeric(past_money.get("cny_yuan"))
        if price is not None and price > 0:
            eligible.append(ref)
    grouped = defaultdict(list)
    unidentified = []
    for ref in eligible:
        key = str(ref.get("project_key") or "").strip()
        key_label = normal(key)
        project = normal(ref.get("project"))
        if (not key or key_label in {"unknown", "unmapped", "none", "null", "n/a", "未注明", "未关联", "待关联"}
                or key_label.startswith(("unknown:", "unmapped:", "unspecified:", "pending:"))
                or (key_label.startswith("project:") and project in {"", "未注明项目", "未注明", "待关联"})):
            unidentified.append(ref)
        else:
            grouped[key].append(ref)
    conflicts = [{"project_key": key,
                  "prices_cny_yuan": sorted({format(numeric(money_record(ref)["cny_yuan"]).normalize(), "f") for ref in group}),
                  "reference_line_ids": [ref.get("line_id") for ref in group]}
                 for key, group in grouped.items()
                 if len({numeric(money_record(ref)["cny_yuan"]) for ref in group}) > 1]
    project_meta = {"independent_project_count": len(grouped),
                    "deduplicated_same_project_rows": sum(len(group) - 1 for group in grouped.values()
                                                            if len({numeric(money_record(ref)["cny_yuan"]) for ref in group}) == 1),
                    "unidentified_project_reference_line_ids": [ref.get("line_id") for ref in unidentified],
                    "project_price_conflicts": conflicts}
    if conflicts:
        return {"status": "仅供参考", "references": references, "comparable": [], **project_meta,
                "reason": "同一项目存在不同历史单价；需确认版本、数量及包含范围，当前不自动判断高低"}
    comparable = [group[0] for group in grouped.values()]
    current_price = numeric(current_money.get("cny_yuan"))
    if comparable and current_price is not None and current_price >= 0:
        prices = [numeric(money_record(ref)["cny_yuan"]) for ref in comparable]
        baseline = median(prices)
        change = (current_price - baseline) / baseline
        status = "偏高" if change > threshold else "偏低" if change < -threshold else "接近历史"
        return {"status": status, "references": references, "comparable": comparable, **project_meta,
                "reference_price": str(baseline), "currency": "CNY", "amount_unit": "元", "difference_ratio": str(change),
                "range": [str(min(prices)), str(max(prices))],
                "reason": "相对所选历史参考价，不能据此直接认定市场合理价"}
    if references:
        reason = ("历史参考缺少可确认的项目归属，不计为独立项目，也不自动判断高低" if eligible and not grouped
                  else "规格、范围、来源复核、单位或币种尚未同时对齐；整包、部分子件和工艺参考均不判断整项高低")
        return {"status": "仅供参考", "references": references, "comparable": [], **project_meta,
                "reason": reason}
    return {"status": "缺少参考", "references": [], "comparable": [], **project_meta,
            "reason": "所选资料未找到可用的分项价格；不能仅因此认定为完全非标"}


def input_issues(entry):
    """Retain backend warnings and inspect the preserved input without editing it."""
    existing = entry.get("input_issues") or []
    if isinstance(existing, str):
        existing = [existing]
    inspect = getattr(modules()["workbench"], "inspect_input", None)
    generated = inspect(entry["quote"]) if inspect else []
    return list(dict.fromkeys(str(issue) for issue in [*existing, *generated] if issue))


def render(result, threshold=Decimal("0.15")):
    if not isinstance(result, dict) or not isinstance(result.get("rows"), list):
        raise ValueError("report 需要 compare 生成的 JSON")
    if not threshold.is_finite() or threshold < 0:
        raise ValueError("--threshold 须为不小于零的比例，例如 0.15")
    project = result.get("project") or "新项目"
    out = [f"# {text(project)} · 采购比价建议", ""]
    if result.get("synthetic"):
        out.extend(["合成演示数据，不代表真实项目或供应商。", ""])
    out.extend(["| 物料/服务 | 当前单价（人民币元） | 判断 | 历史供应商 |", "| --- | --- | --- | --- |"])
    assessed = []
    for entry in result["rows"]:
        advice = assessment(entry, threshold)
        assessed.append((entry, advice))
        query = entry["quote"]
        suppliers = list(dict.fromkeys(ref.get("supplier") or "未注明" for ref in advice["references"]))
        status = "原单待澄清" if input_issues(entry) else advice["status"]
        out.append(f"| {text(query.get('item_name'))} | {text(money(query.get('unit_price'), query.get('currency'), query.get('unit'), money_record(query)))} | {status} | {text('、'.join(suppliers))} |")
    out.extend(["", "## 逐项建议", ""])
    for entry, advice in assessed:
        query = entry["quote"]
        out.append(f"### {text(query.get('item_name'))} · {advice['status']}")
        out.append("")
        issues = input_issues(entry)
        if issues:
            out.extend(["**原单待澄清**", ""])
            out.extend("- " + issue for issue in issues)
            out.append("")
        if advice["comparable"]:
            count = len({r.get("project_key") for r in advice["comparable"]})
            delta = Decimal(advice["difference_ratio"]) * 100
            out.append(f"当前单价相对历史参考{'高' if delta >= 0 else '低'} {abs(delta):.1f}%；参考单价 {money(advice['reference_price'], 'CNY', query.get('unit'))}，来自 {count} 个项目。")
            out.append("建议：" + ("请供应商说明溢价构成，逐项确认配置和交付范围。" if advice["status"] == "偏高" else "确认是否漏项、降低配置或未包含安装运输等费用。" if advice["status"] == "偏低" else "按当前配置和交付范围继续询价确认。"))
            out.append(advice["reason"] + "。")
        elif advice["references"]:
            out.append(advice["reason"] + "。")
        else:
            if entry.get("known_item_in_sources") or entry.get("pending_price_sources"):
                out.append("资料中已有相关名称或待核价格线索；先补原件分项报价与规格，不把无价格记录当作已报价。")
            else:
                out.append("所选资料尚未收录可用参考，或名称与配置未能对应；现有证据不足以区分资料缺失与非标定制。")
            out.append("建议：补充品牌/型号、材质、尺寸、组合及服务范围；请采购补录原报价或向供应商索取分项报价。")
        for ref in advice["references"]:
            role = {"component": "部分子件", "package": "整包", "partial": "部分工作", "process": "工艺"}.get(ref.get("comparison_role"), "分项")
            out.append(f"- {role}参考：{text(ref.get('item_name'))}；{money(ref.get('unit_price'), ref.get('currency'), ref.get('unit'), money_record(ref))}；供应商：{text(ref.get('supplier'))}；项目：{text(ref.get('project'))}。")
            if ref.get("comparison_role") == "component":
                out.append(f"  仅对应当前组合中的 {text(ref.get('component_name'))}，不代表整组报价。")
            differences = list(dict.fromkeys(ref.get("differences", []) + ref.get("spec_differences", [])))
            if money_record(query).get("cny_yuan") is not None and money_record(ref).get("cny_yuan") is not None:
                differences = ["原币不同，已按确认依据统一为人民币元" if difference == "币种不同" else difference
                               for difference in differences]
            if differences:
                out.append("  差异：" + "；".join(differences) + "。")
            if ref.get("match_reason"):
                out.append("  依据：" + str(ref["match_reason"]) + "。")
            if ref.get("estimation_exclusion"):
                out.append("  该记录尚不满足直接判断高低的证据条件。")
        out.append("")
    out.extend(["金额统一展示为人民币元；外币未有已确认汇率和依据时，保留原币原值并显示“待关联财务折算价”，不判断高低。", ""])
    return "\n".join(out)
