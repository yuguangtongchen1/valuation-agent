"""Source identity shared by ingestion and comparison; never inferred from item names."""
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import re


def source_aliases(value):
    """Join a Feishu share URL to its file token without guessing wiki targets."""
    raw = canonical_source(value)
    result = {('source', raw)}
    parsed = urlsplit(raw)
    if parsed.hostname and (parsed.hostname.endswith('.feishu.cn') or parsed.hostname.endswith('.larksuite.com')):
        match = re.fullmatch(r'/(?:file|sheets|docx|docs|wiki|base)/([A-Za-z0-9]+)', parsed.path)
        if match:
            result.add(('source', match[1]))
    return result


def canonical_source(value):
    value = str(value or '').strip()
    u = urlsplit(value)
    if not u.scheme or not u.netloc:
        return value
    # A workbook/file remains one source across sheet views and sharing links.
    query = '' if u.hostname and u.hostname.endswith('.feishu.cn') else urlencode(
        [(k,v) for k,v in parse_qsl(u.query) if k not in ('from','from_copylink') and not k.startswith('utm_')])
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path.rstrip('/'), query, ''))


def identities(value):
    result=set()
    for key in ('source_url','source_token','source_sha256','quotation_family_id','economic_purchase_group','record_id'):
        if value.get(key):
            raw=str(value[key])
            kind='source' if key in ('source_url','source_token') else key
            if raw.startswith('local-sha256:'):kind,raw='source_sha256',raw.split(':',1)[1]
            if kind == 'source':
                result.update(source_aliases(raw))
            else:
                result.add((kind, raw))
    evidence=value.get('source_evidence') or {}
    if evidence.get('sha256'):result.add(('source_sha256',str(evidence['sha256'])))
    if evidence.get('url'):result.update(source_aliases(evidence['url']))
    return result


def exclude_current_sources(rows, document):
    own=identities(document)
    for row in document.get('rows',[]):own.update(identities(row))
    # Expand through provenance so old versions and alternate links cannot leak back.
    while True:
        expanded=set(own)
        for row in rows:
            ids=identities(row)
            if ids & own:expanded.update(ids)
        if expanded==own:break
        own=expanded
    return [r for r in rows if not identities(r)&own and r.get('is_current_version') is not False]
