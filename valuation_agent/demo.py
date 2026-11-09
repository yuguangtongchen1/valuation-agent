"""Entirely invented examples exercise the normal public command path."""
from pathlib import Path

from .io import read_input, write_json
from .service import compare
from .reports import render


def run(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    base = {"currency": "CNY", "agreement_type": "采购", "scope": "设备供货",
            "module": "设备供货", "unit": "套", "quantity": "1"}
    quote = {"project": "合成演示项目", "synthetic": True, "currency": "CNY", "rows": [
        {**base, "item_name": "星星灯", "model": "DEMO-STAR-A", "spec": "24V；1200W", "unit_price": "120", "subtotal": "120"},
        {**base, "item_name": "地台收口", "spec": "不锈钢；宽100mm", "unit": "米", "unit_price": "150", "subtotal": "150"},
        {**base, "item_name": "装饰道具组合", "configuration": "帆船2，游泳圈3", "unit_price": "2000", "subtotal": "2000"},
        {**base, "item_name": "合成未知模块", "spec": "DEMO-ZZZ-UNSEEN", "unit_price": "600", "subtotal": "600"},
    ]}
    history = {"project": "合成历史项目", "synthetic": True, "currency": "CNY", "rows": [
        {**base, "project": "演示历史甲", "supplier": "合成供应商甲", "item_name": "星形灯", "model": "DEMO-STAR-A", "spec": "24V；1.2kW", "unit_price": "100", "subtotal": "100"},
        {**base, "project": "演示历史乙", "supplier": "合成供应商乙", "item_name": "装饰包边", "spec": "铝塑板；宽200mm", "unit": "米", "unit_price": "80", "subtotal": "80"},
        {**base, "project": "演示历史丙", "supplier": "合成供应商丙", "item_name": "帆船", "spec": "木制道具", "unit_price": "300", "subtotal": "300"},
    ]}
    for index, row in enumerate(history["rows"], 1):
        row.update(record_status="contract_reconciled", source_token=f"synthetic-source-{index}",
                   source_locator=f"synthetic quote row {index}")
    quote_path, history_path = root / "quote.json", root / "history.json"
    write_json(quote_path, quote)
    write_json(history_path, history)
    compared = compare(read_input(quote_path), history=history_path)
    write_json(root / "comparison.json", compared)
    (root / "report.md").write_text(render(compared), encoding="utf-8")
    return {"synthetic": True, "files": {key: str((root / value).resolve()) for key, value in {
        "quote": "quote.json", "history": "history.json", "comparison": "comparison.json", "report": "report.md"}.items()}}
