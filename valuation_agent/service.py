"""Public adapters around the existing classification and retrieval engine."""
import hashlib
import json
from pathlib import Path

from .engine import modules
from .io import read_input


def classify(document):
    engine = modules()
    rows = []
    for row in document["rows"]:
        context = " ".join(str(row.get(field) or "") for field in ("spec", "model", "description", "configuration", "scope"))
        path = engine["classification"].classify_row(row)
        parsed = engine["parameters"].parameters(engine["valuation"].norm(context))
        rows.append({**row, "classification_path": list(path),
                     "parameters": {label: [{"normalized_value": str(key), "source_text": value}
                                             for key, value in values.items()] for label, values in parsed.items()},
                     "classification_status": "classified" if path else "needs_category_review"})
    return {**document, "rows": rows}


def history_rows(document):
    """Complete technical IDs, but do not invent source verification or prices."""
    rows, ledger = [], {}
    for index, source in enumerate(document["rows"], 1):
        row = dict(source)
        project = row.get("project") or "未注明项目"
        project_key = row.get("project_key") or "project:" + hashlib.sha256(project.encode()).hexdigest()[:16]
        record_id = row.get("record_id") or row.get("contract_id") or project_key
        row.update(record_id=str(record_id), project_key=str(project_key),
                   kind=row.get("kind") or "bom_line",
                   line_id=row.get("line_id") or f"{record_id}:line-{index}",
                   agreement_type=row.get("agreement_type") or "",
                   module=row.get("module") or row.get("scope") or "",
                   record_status=row.get("record_status") or "user_history_pending_review")
        row["currency"] = row.get("currency", "").upper()
        ledger[str(record_id)] = {
            "record_id": str(record_id), "project_name": project,
            "contract_name": row.get("contract_name") or project,
            "contract_link": row.get("source_name") or document["source_file"],
            "sheet": str(row.get("sheet") or ""), "row": row.get("ledger_row") or index,
        }
        rows.append(row)
    ids = [row["line_id"] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("历史数据 line_id 重复，无法可靠区分来源")
    return rows, ledger


def load_history(data=None, history=None, worksheet=None):
    if bool(data) == bool(history):
        raise ValueError("请指定 --data 私有数据目录或 --history 历史 JSON/CSV/XLSX，二选一")
    engine = modules()
    if data:
        root = Path(data).resolve()
        rows, duplicates, shared, record_count, checked_count = engine["valuation"].load(root)
        # Older whole-scope exports have a source position but no BOM line ID.
        # A stable view ID lets the same lookup show these as package references,
        # while leaving the original data and actual source identity untouched.
        rows = [{**row, "line_id": row.get("line_id") or "scope-view:" + hashlib.sha256(
                    json.dumps([row.get("record_id"), row.get("source_token"), row.get("source_locator")],
                               ensure_ascii=False).encode()).hexdigest()}
                for row in rows]
        ledger = {r["record_id"]: r for r in json.loads((root / "ledger.json").read_text(encoding="utf-8"))}
        catalog = engine["catalog"].ReferenceCatalog(root, rows)
        source_mode = "private_data"
    else:
        document = read_input(history, worksheet)
        rows, ledger = history_rows(document)
        root = Path(history).resolve().parent
        duplicates, shared, catalog = set(), set(), None
        record_count = len(ledger)
        checked_count = len({r["record_id"] for r in rows if engine["valuation"].is_checked(r)})
        source_mode = "provided_history"
    return engine, root, rows, ledger, duplicates, shared, catalog, {
        "mode": source_mode, "records": record_count, "source_checked_records": checked_count,
        "history_rows": len(rows), "live_feishu_search": False,
        "verification_note": "复核状态来自所提供数据；CLI 不替代原件核查" if history else "复用私有数据的原件复核状态",
    }


def search(phrase, data=None, history=None, limit=10, worksheet=None):
    if limit < 1:
        raise ValueError("--limit 须大于零")
    engine, _, rows, _, duplicates, shared, _, metadata = load_history(data, history, worksheet)
    pairs = [(row, engine["valuation"].rejection(row, duplicates, shared)
              if engine["valuation"].is_checked(row) else "pending_source_review") for row in rows]
    return {**engine["valuation"].search(pairs, phrase, limit), "history": metadata}


def compare(document, data=None, history=None, worksheet=None):
    engine, root, rows, ledger, duplicates, shared, catalog, metadata = load_history(data, history, worksheet)
    valuation, workbench = engine["valuation"], engine["workbench"]
    # Association failures and superseded configurations must never be priced references.
    usable = workbench.reference_pool(rows, allow_pending=metadata["mode"] == "provided_history")
    pending = workbench.pending_price_index(rows)
    names = workbench.source_name_index(rows)
    source_by_line = {row["line_id"]: row for row in rows}
    output = []
    for row in document["rows"]:
        query = {**row, "name": row["item_name"], "currency": row.get("currency", "").upper()}
        if len(query["name"]) > 120:
            raise ValueError("物料名称超过 120 字；请把工艺、规格和项目背景放入独立字段")
        found = workbench.lookup(root, usable, ledger, duplicates, shared, query, False,
                                 pending=pending, catalog=catalog, source_names=names)
        for ref in found.get("references", []):
            if ref.get("kind") == "ledger_match":
                if not workbench.TABLE_URL:
                    ref["url"] = None
                continue
            original = source_by_line.get(ref.get("line_id"), {})
            for key in ("money_normalization", "money_unit", "amount_unit", "confirmed_rate_to_cny",
                        "source_evidence", "finance_conversion_evidence", "unit_price_amount_unit",
                        "subtotal_amount_unit", "unit_price_currency", "subtotal_currency",
                        "unit_price_confirmed_rate_to_cny", "subtotal_confirmed_rate_to_cny"):
                if key in original:
                    ref[key] = original[key]
            # No deployment-specific URL is inferred by the portable wrapper.
            if not workbench.GITHUB:
                ref["source_url"] = None
            if ref.get("kind") == "whole_scope_quote":
                ref["comparison_role"] = "package"
        output.append({"quote": row, **found})
    return {"schema_version": 1, "project": document.get("project", ""),
            "synthetic": document.get("synthetic", False), "history": metadata,
            "engine": "workbench.lookup / relationship / quote_classification", "rows": output}


def audit(data):
    """Validate hub associations using the same loader as comparison, without mutating it."""
    engine, _, rows, _, _, _, _, metadata = load_history(data=data)
    pool = engine["workbench"].reference_pool(rows)
    packages = [row for row in pool if row.get("kind") == "whole_scope_quote"
                or (not row.get("unit_price") and row.get("subtotal"))]
    return {"schema_version": 1, "status": "association_checks_passed", "history": metadata,
            "reference_rows": len(pool), "package_reference_rows": len(packages),
            "unit_price_reference_rows": len(pool) - len(packages),
            "note": "验证项目、合同、原件与明细关联；允许未写或未辨字段留空，不代表每项规格都可直接比价。"}
