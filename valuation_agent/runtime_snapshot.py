"""Load an immutable, locally audited query snapshot without reparsing all source pages."""
import hashlib,json
from collections import defaultdict
from pathlib import Path
from .engine import modules

def load_snapshot(data):
    root=Path(data);path=root/'query-snapshot.json';manifest=json.loads((root/'snapshot-manifest.json').read_text())
    with path.open('rb')as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest() if hasattr(hashlib,'file_digest')else hashlib.sha256(stream.read()).hexdigest()
    if digest!=manifest['snapshot_sha256']:raise ValueError('Private query snapshot checksum mismatch')
    doc=json.loads(path.read_text());engine=modules();rows=doc['rows'];ledger=doc['ledger']
    if len(rows)!=manifest['quote_rows']or len(ledger)!=manifest['ledger_records']:raise ValueError('Snapshot count mismatch')
    ids={r['line_id']:r for r in rows}
    if len(ids)!=len(rows)or any(r['record_id']not in ledger for r in rows):raise ValueError('Invalid snapshot associations')
    catalog=object.__new__(engine['catalog'].ReferenceCatalog)
    catalog.template_schema=doc['catalog']['template_schema'];catalog.entries={key:(value[0],tuple(value[1]))for key,value in doc['catalog']['entries'].items()}
    catalog.aliases=defaultdict(list)
    for alias in doc['catalog']['aliases']:
        catalog.aliases[tuple(alias['key'])]=[ids[key]for key in alias['line_ids']]
    return engine,root,rows,ledger,set(doc['duplicates']),set(doc['shared']),catalog,{**doc['metadata'],'mode':'private_audited_snapshot','snapshot_sha256':digest,'live_feishu_search':False}
