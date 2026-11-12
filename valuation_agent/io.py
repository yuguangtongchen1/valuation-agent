"""Input normalization retains original columns and does not infer missing prices."""
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .engine import modules


ALIASES = {
    "item_name": ("item_name", "name", "名称", "物料", "物料名称", "材料名称", "产品名称", "服务名称", "项目／展项", "项目/展项", "工程名称", "报目名称"),
    "model": ("model", "型号", "产品型号"),
    "spec": ("spec", "specification", "规格", "规格型号", "规格/型号", "规格 / 型号", "规格尺寸", "规格/尺寸", "尺寸mm", "尺寸数量"),
    "description": ("description", "工艺说明", "工艺描述", "描述", "工作内容", "服务内容", "制作工艺", "项目特征"),
    "configuration": ("configuration", "配置", "组合", "组合模式"),
    "quantity": ("quantity", "qty", "数量"),
    "unit": ("unit", "单位", "计价单位"),
    "unit_price": ("unit_price", "单价", "原始单价", "综合单价"),
    "subtotal": ("subtotal", "amount", "金额", "小计", "总价", "原表金额"),
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


def table_rows(headers, values, start_row=2):
    headers = [str(h).strip() if h is not None else "" for h in headers]
    active = [h for h in headers if h]
    if len(set(active)) != len(active):
        raise ValueError("表头名称重复；请先区分同名列")
    result = []
    for index, row in enumerate(values, start_row):
        if not any(v is not None and str(v).strip() for v in row):
            continue
        if len(row) > len(headers) and any(v not in (None, "") for v in row[len(headers):]):
            raise ValueError(f"第 {index} 行含无表头的数据列")
        if any(not h and pos < len(row) and row[pos] not in (None, "") for pos, h in enumerate(headers)):
            raise ValueError(f"第 {index} 行有值但缺少列名")
        result.append({**{h: row[pos] if pos < len(row) else None for pos, h in enumerate(headers) if h},
                       "_input_row": index})
    return result


def detect_table(matrix):
    """Locate an explicit detail header; keep preceding summaries as evidence."""
    for index, candidate in enumerate(matrix[:100]):
        names = {str(v).strip().casefold() for v in candidate if v is not None}
        named = any(a.casefold() in names for a in ALIASES['item_name'])
        quantitative = any(a.casefold() in names for a in ALIASES['quantity'])
        priced = any(a.casefold() in names or any(money_header(n, (a,)) for n in names)
                     for a in ALIASES['unit_price'] + ALIASES['subtotal'])
        if named and (quantitative or priced):
            return table_rows(candidate, matrix[index+1:], index+2), [
                {'kind': 'preamble', 'source_row': i+1, 'values': list(r)}
                for i, r in enumerate(matrix[:index]) if any(v is not None for v in r)]
    raise ValueError('未找到明确的报价明细表头；请由 Skill 结合上下文映射为 JSON，不能以汇总区代替明细')


def enrich_mixed_fields(row, original):
    """Extract only explicit counts; preserve composite pricing and source text."""
    mixed = str(original.get('尺寸数量') or '').strip()
    thickness = str(original.get('厚度参数') or '').strip()
    if thickness:
        row['spec'] = '；'.join(x for x in (row.get('spec'), thickness) if x)
    if mixed:
        counts = re.findall(r'(\d+(?:\.\d+)?)\s*(套|组|件|个|台)(?![\w])', mixed)
        # Chinese characters are word characters too; accept punctuation/end after unit.
        if len(counts) == 1 and row.get('quantity') is None and not row.get('unit'):
            row['quantity'], row['unit'] = counts[0]
            row['quantity_source'] = '尺寸数量原文明示'
            if '预估' in mixed or '待定' in mixed:
                row['quantity_status'] = 'estimated'
        elif len(counts) > 1:
            row['configuration'] = row.get('configuration') or mixed
            row['import_notes'] = ['多规格组合：保留各子件数量，不分摊整行金额']
    path = [str(original.get(k) or '').strip() for k in ('分类', '区域／展馆', '分项', '项目／展项')]
    if any(path):
        row['source_hierarchy'] = [part for part in path if part]
    return row


def derive_unit_price(row):
    """Compute a labelled price for a single stated billing quantity; retain source totals."""
    if row.get('unit_price') not in (None, ''):
        return row
    if not str(row.get('unit') or '').strip() or row.get('quantity') in (None, '') or row.get('subtotal') in (None, ''):
        return row
    if row.get('configuration') or row.get('quantity_is_estimate'):
        return row
    try:
        quantity, total = Decimal(str(row['quantity'])), Decimal(str(row['subtotal']))
        if not quantity.is_finite() or not total.is_finite() or quantity <= 0 or total < 0:
            return row
        price = (total / quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return row
    row['unit_price'] = format(price, 'f')
    row['unit_price_source'] = '小计÷数量（计算值，保留两位小数）'
    row['unit_price_calculation'] = {'subtotal': str(total), 'quantity': str(quantity),
                                   'rounding': 'ROUND_HALF_UP', 'original_unit_price': None}
    row['unit_price_amount_unit'] = '元'
    row['unit_price_currency'] = row.get('subtotal_currency') or row.get('currency')
    # Re-normalize derived money without inheriting old missing-price metadata.
    row.get('money_normalization', {}).pop('unit_price', None)
    return row


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
            rows, metadata['non_item_rows'] = detect_table(list(reader))
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
        rows, metadata['non_item_rows'] = detect_table([r['values'] for r in sheet['rows']])
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
            rows, preamble = detect_table(list(sheet.iter_rows(values_only=True)))
            items=[]; non_items=[]
            for source_row in rows:
                filled={k:v for k,v in source_row.items() if k!='_input_row' and v is not None and str(v).strip()}
                named=any(str(source_row.get(a) or '').strip() for a in ALIASES['item_name'])
                if not named and len(filled)==1 and isinstance(next(iter(filled.values())),str):
                    non_items.append({'kind':'section_or_note','source_original_fields':source_row});continue
                labels={'合计','总计','含税合计','税额','优惠价','优惠价：','优惠价:'}
                quantity=str(source_row.get('数量') or '').strip()
                summary_label=quantity in labels or bool(re.fullmatch(r'\d+(?:\.\d+)?%税',quantity))
                if not named and summary_label and set(filled).issubset({'数量','金额','小计','总价'}):
                    non_items.append({'kind':'summary','source_original_fields':source_row});continue
                items.append(source_row)
            rows=items
            metadata['non_item_rows']=preamble + non_items
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
    previous_source = None
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
        row = enrich_mixed_fields(row, original)
        if not row['item_name'] and previous_source and original.get('制作工艺'):
            group_keys = ('分类', '区域／展馆', '分项')
            if original.get('分项') and all(original.get(k) == previous_source.get(k) for k in group_keys):
                row['item_name'] = str(previous_source.get('项目／展项') or previous_source.get('项目/展项') or '')
                row['name_source'] = '同分项前行名称延续；保留原空白值'
                row['import_notes'] = row.get('import_notes', []) + ['名称延续，需结合前行确认方案关系']
        previous_source = original
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
        row = derive_unit_price(row)
        row = modules()["money"].normalize_money_fields(row, metadata)
        normalized.append(row)
    return {"schema_version": 1, "project": metadata.get("project", ""), "currency": metadata.get("currency", ""),
            "source_file": path.name, "source_sha256": digest, "worksheet": metadata.get('worksheet'), "synthetic": metadata.get("synthetic", False),
            "rows": normalized, "non_item_rows": metadata.get("non_item_rows", [])}
