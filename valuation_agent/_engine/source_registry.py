"""Bind quotation evidence to its original ledger record and source cell."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


REGISTRY_FILE = 'source-registry.json'
ATTACHMENT = 'ledger_attachment'
QUOTE_IMAGE = 'ledger_quote_image'
CELL = re.compile(r"(?:(?P<sheet>[^!]+)!)?(?P<column>[A-Za-z]{1,3})(?P<row>[1-9]\d*)$")
LOCATOR_CELL = re.compile(
    r'(?<![A-Za-z0-9])(?:(?P<sheet>[A-Za-z0-9_-]+)!)?'
    r'(?P<cell>[A-Z]{1,3}[1-9]\d*)(?![A-Za-z0-9])')


def parse_cell(value):
    match = CELL.fullmatch(str(value or '').strip())
    if not match:
        raise ValueError('Source requires an exact A1 ledger cell')
    return (match['sheet'].strip(" '\"") if match['sheet'] else None,
            match['column'].upper(), int(match['row']))


def column_number(column):
    number = 0
    for letter in column:
        number = number * 26 + ord(letter) - ord('A') + 1
    return number


def association_pending(row):
    """Scope confirmation cannot be bypassed by a reconciled price status."""
    return (row.get('scope_association_pending') is True
            or row.get('comparison_eligible') is False
            or row.get('association_status') in {
                'scope_association_pending',
                'source_project_city_differs_from_ledger_main_project',
                'cross_contract_or_attachment_scope_needs_confirmation',
            })


class SourceRegistry:
    def __init__(self, ledger, document=None):
        self.ledger = ledger if isinstance(ledger, dict) else {r['record_id']: r for r in ledger}
        self.attachments = {rid: {a['token'] for a in row.get('attachments', [])}
                            for rid, row in self.ledger.items()}
        self.images = {}
        if document is None:
            return
        if document.get('schema_version') != 1:
            raise ValueError('Unsupported source registry version')
        origins = {o['spreadsheet_token']: o for o in document.get('origins', [])}
        seen = set()
        for entry in document.get('sources', []):
            rid, token, role = entry['record_id'], entry['source_token'], entry['source_role']
            table = entry.get('source_table', {})
            origin = origins.get(table.get('spreadsheet_token'))
            if rid not in self.ledger or not token or not origin or not entry.get('source_chain'):
                raise ValueError('Registry source has no ledger record or original table lineage')
            sheet, column, row = parse_cell(entry.get('source_cell'))
            record = self.ledger[rid]
            if (table.get('sheet_id') not in origin.get('sheet_ids', [])
                    or table.get('wiki_url') != origin.get('wiki_url')
                    or table.get('sheet_id') != rid.rsplit(':', 1)[0]
                    or row != int(rid.rsplit(':', 1)[1])
                    or table.get('row') != row or table.get('column') != column
                    or (record.get('row') is not None and record['row'] != row)
                    or (record.get('sheet') and record['sheet'] != table.get('sheet_name'))
                    or (sheet and sheet not in {table.get('sheet_name'), table.get('sheet_id')})):
                raise ValueError('Registry source cell does not belong to its ledger record')
            expected_chain = [f"wiki:{origin['wiki_url'].rstrip('/').rsplit('/', 1)[-1]}",
                              f"sheet:{table['spreadsheet_token']}",
                              f"{table['sheet_id']}!{column}{row}"]
            if entry['source_chain'][:3] != expected_chain:
                raise ValueError('Registry source lineage does not identify the original table cell')
            key = rid, token, role, column, row
            if key in seen:
                raise ValueError('Duplicate source registry binding')
            seen.add(key)
            if role == ATTACHMENT:
                if column != 'D' or token not in self.attachments[rid]:
                    raise ValueError('Registry attachment is not present in the original ledger')
            elif role == QUOTE_IMAGE:
                if column_number(column) < 14 or not entry.get('sha256') or not entry.get('original_path'):
                    raise ValueError('Ledger quotation image requires an original image and source cell')
                self.images.setdefault((rid, token), []).append(entry)
            else:
                raise ValueError('Unsupported registered source role')

    @classmethod
    def load(cls, root, ledger=None):
        root = Path(root)
        if ledger is None:
            ledger = json.loads((root / 'ledger.json').read_text())
        path = root / REGISTRY_FILE
        return cls(ledger, json.loads(path.read_text()) if path.exists() else None)

    def linked_tokens(self):
        linked = {rid: set(tokens) for rid, tokens in self.attachments.items()}
        for rid, token in self.images:
            linked[rid].add(token)
        return linked

    def bind(self, row):
        """Validate source identity; attach immutable provenance to image-derived rows."""
        rid, token, locator = row.get('record_id'), row.get('source_token'), row.get('source_locator')
        if not isinstance(locator, str) or not locator.strip():
            raise ValueError('Review row requires an exact source position')
        if token in self.attachments.get(rid, set()):
            if row.get('source_role') not in (None, ATTACHMENT, 'contract_source'):
                raise ValueError('Review source role conflicts with its ledger attachment')
            return dict(row)
        candidates = self.images.get((rid, token), [])
        if not candidates or row.get('source_role') not in (None, QUOTE_IMAGE):
            raise ValueError(f'Review row has no source linked to this ledger record: {rid}')
        explicit = row.get('source_cell')
        if explicit:
            sheet, column, number = parse_cell(explicit)
            candidates = [e for e in candidates if e['source_table']['column'] == column
                          and e['source_table']['row'] == number
                          and (not sheet or sheet in {e['source_table']['sheet_name'],
                                                     e['source_table']['sheet_id']})]
        mentioned_cells = list(LOCATOR_CELL.finditer(locator))
        if mentioned_cells:
            candidates = [e for e in candidates
                          if any(m['cell'] == f"{e['source_table']['column']}{e['source_table']['row']}"
                                 and (not m['sheet'] or m['sheet'] in {
                                     e['source_table']['sheet_name'], e['source_table']['sheet_id']})
                                 for m in mentioned_cells)]
        elif not explicit:
            raise ValueError('Image evidence must identify its registered ledger source cell')
        if len(candidates) != 1:
            raise ValueError('Review source cell is not registered for this record and image token')
        entry = candidates[0]
        if row.get('source_table') and row['source_table'] != entry['source_table']:
            raise ValueError('Review row conflicts with registered original table lineage')
        if row.get('source_image_sha256') and row['source_image_sha256'] != entry['sha256']:
            raise ValueError('Review row image checksum conflicts with the source registry')
        result = {**row, 'source_role': QUOTE_IMAGE, 'source_cell': entry['source_cell'],
                  'source_table': entry['source_table'], 'source_chain': entry['source_chain'],
                  'source_image_sha256': entry['sha256'],
                  'source_original_path': entry['original_path']}
        if association_pending(entry) or association_pending(row):
            result.update(scope_association_pending=True, comparison_eligible=False,
                          association_status='scope_association_pending')
        return result


def build(root, audit):
    """Build registrations from the verified live table inventory, never from candidate prices."""
    root = Path(root).resolve()
    ledger = json.loads((root / 'ledger.json').read_text())
    scope = audit['scope']
    wiki = scope['only_authorized_origin']
    token = scope['underlying_sheet_token']
    sheets = {s['sheet_id']: s for s in audit['live_sheet_coverage']}
    if not sheets or not all(s.get('all_coordinates_verified') for s in sheets.values()):
        raise ValueError('Source registration requires complete verified original sheet coverage')
    document = {'schema_version': 1, 'origins': [{'wiki_url': wiki, 'spreadsheet_token': token,
                  'sheet_ids': list(sheets)}], 'sources': []}

    def entry(rid, source_token, role, column, number):
        sid = rid.rsplit(':', 1)[0]
        s = sheets[sid]
        return {'record_id': rid, 'source_token': source_token, 'source_role': role,
                'source_cell': f"{s['sheet']}!{column}{number}",
                'source_table': {'wiki_url': wiki, 'spreadsheet_token': token, 'sheet_id': sid,
                                 'sheet_name': s['sheet'], 'row': number, 'column': column},
                'source_chain': [f"wiki:{wiki.rstrip('/').rsplit('/', 1)[-1]}", f'sheet:{token}',
                                 f'{sid}!{column}{number}', f'{role}:{source_token}']}

    for record in ledger:
        rid = record['record_id']
        number = int(rid.rsplit(':', 1)[1])
        for attachment in record['attachments']:
            document['sources'].append(entry(rid, attachment['token'], ATTACHMENT, 'D', number))
    pending = {(r['record_id'], r['source_token']) for r in audit.get('candidate_lines', [])
               if association_pending(r)}
    for image in audit['live_quote_image_source_registry']:
        rid, image_token = image['record_id'], image['source_image_token']
        item = entry(rid, image_token, QUOTE_IMAGE, image['column'], image['row'])
        path = Path(image['original_path'])
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if image.get('source_state') != 'original_downloaded_cache_available' or sha != image.get('sha256'):
            raise ValueError('Audited original image is unavailable or its bytes changed')
        try:
            original_path = str(path.resolve().relative_to(root))
        except ValueError:
            original_path = str(path.resolve())
        item.update(sha256=sha, original_path=original_path)
        if (rid, image_token) in pending:
            item.update(scope_association_pending=True, comparison_eligible=False,
                        association_status='scope_association_pending')
        document['sources'].append(item)
    SourceRegistry(ledger, document)
    document['summary'] = dict(Counter(e['source_role'] for e in document['sources']))
    return document


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path)
    parser.add_argument('--audit', type=Path, required=True)
    args = parser.parse_args()
    document = build(args.data, json.loads(args.audit.read_text()))
    path = args.data / REGISTRY_FILE
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'source_registry': str(path), 'bindings': len(document['sources']),
                      'roles': document['summary']}, ensure_ascii=False))
