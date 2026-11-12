"""Private, versioned supplier quotations. Never promotes offers to executed purchases."""
import hashlib
import json
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from .source_identity import canonical_source, identities


def unit_price(amount, quantity, periods=None):
    if amount is None or quantity is None:
        return None
    denominator = Decimal(str(quantity))
    if periods is not None:
        denominator *= Decimal(str(periods))
    if denominator <= 0:
        return None
    return str((Decimal(str(amount)) / denominator).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def ingest(document, database):
    """Accept model-reviewed source rows; content hash makes re-ingestion idempotent."""
    if not document.get('source_sha256') or not document.get('source_url'):
        raise ValueError('入库需要原件 SHA256 和来源地址')
    if not document.get('project') or not document.get('rows'):
        raise ValueError('入库需要项目和已解析明细')
    ids = [r.get('line_id') for r in document['rows']]
    if not all(ids) or len(set(ids)) != len(ids):
        raise ValueError('明细必须有不重复的来源行标识')
    for r in document['rows']:
        if not r.get('source_locator') or not r.get('record_role'):
            raise ValueError('每行必须有原文位置和行角色')
        for field in ('quantity', 'unit_price', 'subtotal', 'pricing_periods'):
            if r.get(field) is not None and not Decimal(str(r[field])).is_finite():
                raise ValueError('数值必须为有限数字')
        if r.get('supplier') and not r.get('supplier_basis'):
            raise ValueError('供应商关联必须有来源依据')
        if r.get('parent_line_id') and r['parent_line_id'] not in ids:
            raise ValueError('组合子件的父行不存在')
    document = dict(document, source_url=canonical_source(document["source_url"]))
    family = document.get("quotation_family_id") or document["source_url"]
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True)
    revision = hashlib.sha256(payload.encode()).hexdigest()
    path = Path(database); path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript('''
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS quote_versions (
          revision TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, source_url TEXT NOT NULL,
          project TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS quote_lines (
          revision TEXT NOT NULL REFERENCES quote_versions(revision), line_id TEXT NOT NULL,
          supplier TEXT, role TEXT NOT NULL, payload TEXT NOT NULL,
          PRIMARY KEY(revision,line_id));
        CREATE INDEX IF NOT EXISTS supplier_quotes ON quote_lines(supplier,revision);
        CREATE TABLE IF NOT EXISTS active_sources (source_url TEXT PRIMARY KEY, revision TEXT NOT NULL REFERENCES quote_versions(revision));
        ''')
        existed = db.execute('SELECT 1 FROM quote_versions WHERE revision=?',(revision,)).fetchone() is not None
        db.execute('INSERT OR IGNORE INTO quote_versions(revision,source_sha256,source_url,project,payload) VALUES(?,?,?,?,?)',
                   (revision,document['source_sha256'],document['source_url'],document['project'],payload))
        for row in document['rows']:
            # Status cannot be elevated by an import payload.
            row = dict(row, record_status='supplier_quotation', purchase_executed=False)
            db.execute('INSERT OR IGNORE INTO quote_lines VALUES(?,?,?,?,?)',
                       (revision,row['line_id'],row.get('supplier'),row['record_role'],json.dumps(row,ensure_ascii=False)))
        if not existed:
            db.execute('INSERT OR REPLACE INTO active_sources VALUES(?,?)',(family,revision))
    path.chmod(0o600)
    return {'revision':revision,'rows':len(ids),'already_present':existed,'database':str(path.resolve())}


def export(database, supplier=None, exclude_source=None, references_only=False):
    """Current offers only, with optional supplier browse and self-quote exclusion."""
    if references_only and not exclude_source:
        raise ValueError('比价候选导出必须提供 --exclude-source 当前报价来源')
    with sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True) as db:
        versions={revision:json.loads(payload) for revision,payload in db.execute('SELECT revision,payload FROM quote_versions ORDER BY rowid')}
        active={revision for revision, in db.execute('SELECT revision FROM active_sources')}
        current={}
        for revision,doc in versions.items():
            if revision in active:current[doc.get('quotation_family_id') or canonical_source(doc['source_url'])]=revision
        active=set(current.values())
        blocked={('source',canonical_source(exclude_source))} if exclude_source else set()
        while True:
            expanded=set(blocked)
            for doc in versions.values():
                ids=identities(doc)
                if ids & blocked:expanded.update(ids)
            if expanded==blocked:break
            blocked=expanded
        rows=[];seen=set()
        for revision,payload in db.execute('SELECT revision,payload FROM quote_lines'):
            doc=versions[revision]
            if revision not in active or identities(doc)&blocked:continue
            row=json.loads(payload)
            if supplier and row.get('supplier')!=supplier:continue
            key=(doc['source_sha256'],row['line_id'])
            if key in seen:continue
            seen.add(key)
            rows.append(dict(row,source_url=doc['source_url'],source_sha256=doc['source_sha256'],
                             quotation_family_id=doc.get('quotation_family_id') or doc['source_url'],
                             economic_purchase_group=doc.get('quotation_family_id') or canonical_source(doc['source_url']),
                             quote_revision=revision,is_current_version=True))
    if references_only:
        rows = [r for r in rows if r.get('record_role') == 'quote_line' and r.get('comparable_price') is True]
    return {'rows':rows,'record_status':'supplier_quotation'}
