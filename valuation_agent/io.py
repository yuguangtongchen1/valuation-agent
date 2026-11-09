"""Input normalization retains original columns and does not infer missing prices."""
import csv
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .engine import modules


ALIASES = {
    "item_name": ("item_name", "name", "名称", "物料", "物料名称", "材料名称", "产品名称", "服务名称"),
    "model": ("model", "型号", "产品型号"),
    "spec": ("spec", "specification", "规格", "规格型号", "规格/型号", "规格 / 型号", "规格尺寸", "规格/尺寸"),
    "description": ("description", "工艺说明", "描述", "工作内容", "服务内容"),
    "configuration": ("configuration", "配置", "组合", "组合模式"),
    "quantity": ("quantity", "qty", "数量"),
    "unit": ("unit", "单位", "计价单位"),
    "unit_price": ("unit_price", "单价", "原始单价"),
    "subtotal": ("subtotal", "amount", "金额", "小计", "总价"),
    "currency": ("currency", "币种"),
    "supplier": ("supplier", "供应商", "乙方公司"),
    "project": ("project", "project_name", "项目", "项目名称"),
    "brand": ("brand", "品牌"),
    "scope": ("scope", "范围", "交付范围"),
}
NUMERIC = {"quantity", "unit_price", "subtotal"}
MONEY = {"unit_price", "subtotal"}


@lru_cache(maxsize=256)
def money_header(name, aliases):
    """Recognize an explicit amount scale in a monetary column heading."""
    normalized = unicodedata.normalize("NFKC", str(name)).strip()
    for alias in aliases:
        if not normalized.casefold().startswith(alias.casefold()):
            continue
        suffix = normalized[len(alias):].strip()
        if not suffix:
            continue
        unit = suffix.strip(" ()/：:")
        try:
            modules()["money"].unit_details(unit)
        except ValueError:
            continue
        return unit
    return None


def decimal_text(value, field):
    if value is None or str(value).strip() in ("", "—", "-", "/"):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} 必须是数字，不能是布尔值")
    raw = str(value).strip().replace(",", "").replace("，", "")
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{field} 无法识别为纯数字：{value}。请将币种、单位分列。") from exc
    if not number.is_finite():
        raise ValueError(f"{field} 必须是有限数字")
    return str(number)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def table_rows(headers, values):
    headers = [str(h).strip() if h is not None else "" for h in headers]
    active = [h for h in headers if h]
    if len(set(active)) != len(active):
        raise ValueError("表头名称重复；请先区分同名列")
    result = []
    for index, row in enumerate(values, 2):
        if not any(v is not None and str(v).strip() for v in row):
            continue
        if len(row) > len(headers) and any(v not in (None, "") for v in row[len(headers):]):
            raise ValueError(f"第 {index} 行含无表头的数据列")
        if any(not h and pos < len(row) and row[pos] not in (None, "") for pos, h in enumerate(headers)):
            raise ValueError(f"第 {index} 行有值但缺少列名")
        result.append({**{h: row[pos] if pos < len(row) else None for pos, h in enumerate(headers) if h},
                       "_input_row": index})
    return result


def read_input(path, worksheet=None):
    path = Path(path)
    metadata = {}
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = next((payload[k] for k in ("rows", "items", "lines") if isinstance(payload.get(k), list)), None)
            if rows is None:
                raise ValueError("JSON 需为对象数组或含 rows/items/lines 数组的对象")
            metadata = {k: v for k, v in payload.items() if k not in ("rows", "items", "lines")}
        else:
            raise ValueError("JSON 顶层需为数组或对象")
    elif suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            headers = next(reader, None)
            if headers is None:
                raise ValueError("CSV 为空")
            rows = table_rows(headers, reader)
    elif suffix == ".xls":
        book = modules()["legacy"].legacy_xls_document(path.read_bytes())
        candidates = [s for s in book['sheets'] if not worksheet or s['name'] == worksheet]
        if not candidates:
            raise ValueError("不存在指定工作表：" + str(worksheet))
        if not worksheet and len(candidates) != 1:
            raise ValueError("XLS 有多个工作表，请用 --worksheet 指定，避免漏读")
        sheet = candidates[0]
        if not sheet['rows']:
            raise ValueError("工作表为空")
        rows = table_rows(sheet['rows'][0]['values'], (r['values'] for r in sheet['rows'][1:]))
        metadata['worksheet'] = sheet['name']
    elif suffix == ".xlsx":
        try:
            import openpyxl
        except ImportError as exc:
            raise ValueError('读取 XLSX 请先安装：pip install "valuation-agent[excel]"') from exc
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            if worksheet and worksheet not in book.sheetnames:
                raise ValueError("不存在指定工作表：" + worksheet)
            if not worksheet and len(book.sheetnames) != 1:
                raise ValueError("XLSX 有多个工作表，请用 --worksheet 指定，避免漏读")
            sheet = book[worksheet] if worksheet else book[book.sheetnames[0]]
            iterator = sheet.iter_rows(values_only=True)
            headers = next(iterator, None)
            if not headers:
                raise ValueError("工作表为空")
            rows = table_rows(headers, iterator)
            metadata["worksheet"] = sheet.title
        finally:
            book.close()
    else:
        raise ValueError("支持 JSON、CSV、XLSX、XLS；PDF/图片/非标准合同请先由 Skill 逐表识别并归一为 JSON，保留原表头和证据位置")
    if not rows:
        raise ValueError("输入没有明细行")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("每条明细必须是 JSON 对象")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    normalized = []
    for index, original in enumerate(rows, 1):
        row = dict(original)
        keys = {str(k).strip().casefold(): k for k in original}
        for field, aliases in ALIASES.items():
            matches = [(keys[a.casefold()], original[keys[a.casefold()]]) for a in aliases if a.casefold() in keys]
            if field in MONEY:
                headed = [(key, value, money_header(key, aliases)) for key, value in original.items()]
                headed = [(key, value, unit) for key, value, unit in headed if unit]
                matches.extend((key, value) for key, value, _ in headed)
                previous = (original.get("money_normalization") or {}).get(field)
                if previous and field in original:
                    # Original headings stay present for review. The current,
                    # labelled base-unit field is authoritative on re-import.
                    matches = [(field, original[field])]
                elif headed:
                    units = {unit for _, _, unit in headed}
                    if len(units) != 1:
                        raise ValueError(f"第 {index} 条 {field} 的金额单位冲突")
                    row.setdefault(field + "_amount_unit", headed[0][2])
            filled = [(key, value) for key, value in matches if value is not None and str(value).strip()]
            if len({str(v).strip() for _, v in filled}) > 1:
                raise ValueError(f"第 {index} 条 {field} 有多个冲突字段，请先明确映射：" + "、".join(k for k, _ in filled))
            value = filled[0][1] if filled else (matches[0][1] if matches else None)
            row[field] = value if field in MONEY else decimal_text(value, field) if field in NUMERIC else str(value).strip() if value is not None else ""
        if not row["item_name"]:
            raise ValueError(f"第 {index} 条缺物料/服务名称；不要把项目名称或备注当物料名称")
        row["project"] = row["project"] or str(metadata.get("project", ""))
        row["currency"] = row["currency"] or str(metadata.get("currency", ""))
        row.setdefault("row_id", f"row-{index}")
        row.setdefault("source_token", f"local-sha256:{digest}")
        source_sheet = f":sheet {metadata['worksheet']}" if metadata.get('worksheet') else ''
        row.setdefault("source_locator", f"{path.name}{source_sheet}:row {original.get('_input_row', index)}")
        row.setdefault("source_original_fields", original.get("source_original_fields", original))
        row.setdefault("source_evidence", {"file": path.name, "sha256": digest, "locator": row["source_locator"]})
        row = modules()["money"].normalize_money_fields(row, metadata)
        normalized.append(row)
    return {"schema_version": 1, "project": metadata.get("project", ""), "currency": metadata.get("currency", ""),
            "source_file": path.name, "source_sha256": digest, "worksheet": metadata.get('worksheet'), "synthetic": metadata.get("synthetic", False),
            "rows": normalized}
