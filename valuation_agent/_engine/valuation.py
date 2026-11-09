"""Read-only CLI for source-linked procurement price references."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
from functools import lru_cache
import json
from pathlib import Path
from statistics import median
import unicodedata

from estimate import number
from money_units import normalize_money_fields
from finance_view import FinanceView, load_finance_reviewed_bases
from source_registry import SourceRegistry, association_pending

CHECKED_BOM = {'contract_reconciled', 'contract_reconciled_with_adjustments'}
CHECKED_PACKAGE = 'whole_scope_source_checked'
QUERY_FIELDS = ('item_name', 'brand', 'model', 'spec', 'unit', 'currency', 'agreement_type', 'scope')


@lru_cache(maxsize=65536)
def _normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def norm(value):
    return _normalized(str(value or ''))


def load(root):
    def read(name):
        return json.loads((root / name).read_text())

    ledger = read('ledger.json')
    records = {row['record_id']: row for row in ledger}
    if len(records) != len(ledger):
        raise ValueError('台账记录编号重复')
    coverage = read('quote-record-coverage.json')
    if len(coverage) != len(records) or {row['record_id'] for row in coverage} != records.keys():
        raise ValueError('报价覆盖清单与台账不一致')
    hierarchy = read('project-hierarchy.json')
    assignments = [(contract['record_id'], project['main_project_key'])
                   for project in hierarchy['projects'] for group in project['owner_groups']
                   for contract in group['contracts']]
    project_by_record = dict(assignments)
    if len(assignments) != len(records) or project_by_record.keys() != records.keys():
        raise ValueError('项目层级与台账记录不一致')
    rows = read('quote-records.json')
    acceptance_path=root/'contract-acceptance.json'
    acceptance = read('contract-acceptance.json') if acceptance_path.exists() else None
    if acceptance is not None and (root/'source-reviews/finance-reviewed-bases.json').exists():
        # Validate source bytes and ledger ownership at read time, not only at build time.
        reviewed = load_finance_reviewed_bases(root, records)
        for contract in acceptance.get('contracts', []):
            contract['finance_reviewed_bases'] = reviewed.get(contract.get('record_id'), [])
    finance=FinanceView(acceptance) if acceptance is not None else None
    if finance:
        for row in rows:row.update(finance.for_row(row))
    ids = [row['line_id'] for row in rows if row.get('line_id')]
    if len(ids) != len(set(ids)):
        raise ValueError('明细编号重复')
    registry = SourceRegistry.load(root, records)
    linked = registry.linked_tokens()
    for row in rows:
        rid = row['record_id']
        row.update(registry.bind(row))
        if row.get('ledger_amount_cny_tax_inclusive') != records[rid]['ledger_tax_inclusive_amount']:
            raise ValueError(f'台账人民币金额发生漂移 {rid}')
        if row.get('project_key') != project_by_record[rid]:
            raise ValueError(f'报价与台账项目归属不一致 {rid}')
    audit = read('合同复核进度.json')
    duplicate_records = {item['record_id'] for group in audit['重复来源待核'] for item in group['证据']}
    token_records = defaultdict(set)
    for rid, tokens in linked.items():
        for token in tokens:
            token_records[token].add(rid)
    shared_tokens = {token for token, refs in token_records.items() if len(refs) > 1}
    checked = {row['record_id'] for row in rows if is_checked(row)}
    if (audit['台账记录数'] != len(records) or audit['完成原件复核'] != len(checked)
            or {r['record_id'] for r in audit['记录'] if r['已完成原件复核']} != checked):
        raise ValueError('原件复核进度与报价明细不一致，请先重建数据')
    return rows, duplicate_records, shared_tokens, len(records), len(checked)


def is_checked(row):
    if association_pending(row):
        return False
    if row.get('source_document_type')=='cross_project_appendix_quote':
        return False
    if row['kind'] == 'bom_line':
        return row.get('record_status') in CHECKED_BOM and row.get('source_price_version') != '变更前'
    return row['kind'] == 'whole_scope_quote' and row.get('record_status') == CHECKED_PACKAGE


def positive(value):
    parsed = number(value)
    return parsed is not None and parsed > 0


def scope(row):
    return row.get('module') or row.get('work_package')


def comparable_key(row):
    return tuple(norm(row.get(key)) for key in QUERY_FIELDS)


def count_estimate_groups(rows):
    groups = defaultdict(lambda: defaultdict(set))
    for row, reason in rows:
        if reason is None:
            key = comparable_key({**row, 'scope': scope(row)})
            groups[key][row['project_key']].add(number(row['unit_price']))
    return sum(sum(len(prices) == 1 for prices in projects.values()) >= 2
               for projects in groups.values())


def price_role_block(row):
    """Exclude financial/conditional observations, independently of review completion."""
    attrs = row.get('source_attributes') or {}
    for values in (row, attrs):
        if any(values.get(flag) is True for flag in (
                'exclude_from_procurement_price_comparison', 'price_reference_blocked',
                'explicit_non_market_rate', 'user_confirmed_no_charge', 'finance_archive_only')):
            return 'non_procurement_or_conditional_price'
    roles = ' '.join(str(values.get(key) or '').lower()
                     for values in (row, attrs)
                     for key in ('source_document_type', 'amount_role', 'price_role',
                                 'price_basis', 'source_payment_basis'))
    if any(word in roles for word in ('revenue', 'settlement_share', 'balance_payment',
                                      'payment_balance', 'framework_ledger', 'unpriced_framework', 'scope_reduction', 'change_reduction')):
        return 'non_procurement_or_conditional_price'
    if row.get('valuation_eligible') is False and not attrs.get('duplicate_quote_reference_only') and not view_only_variant(row):
        return 'valuation_explicitly_excluded'
    return None


def view_only_variant(row):
    attrs = row.get('source_attributes') or {}
    return bool(row.get('source_document_type') == 'cross_project_appendix_quote'
                or row.get('source_price_version') == '变更前'
                or row.get('version_exclusive')
                or any(values.get(key) for values in (row, attrs)
                       for key in ('source_city_version_conflict', 'source_version_conflict',
                                   'price_variant_scope', 'variant_scope_pending')))


def rejection(row, duplicate_records, shared_tokens):
    if price_role_block(row):
        return price_role_block(row)
    if view_only_variant(row):
        return 'price_variant_scope_reference_only'
    if association_pending(row):
        return 'scope_association_pending'
    if row['kind'] != 'bom_line':
        return 'whole_scope_reference_only'
    if row['record_id'] in duplicate_records or row['source_token'] in shared_tokens:
        return 'shared_source'
    if any(not norm(row.get(k)) for k in ('item_name', 'unit', 'currency', 'agreement_type', 'project_key')) or not norm(scope(row)):
        return 'missing_dimensions'
    if not (norm(row.get('model')) or norm(row.get('spec'))):
        return 'missing_model_and_spec'
    if not positive(row.get('unit_price')) or not positive(row.get('quantity')) or not positive(row.get('subtotal')):
        return 'missing_positive_quantity_or_price'
    if row.get('period') or row.get('billing_period') or any(
        row.get(k) is not None and number(row[k]) != 1 for k in ('billing_multiplier', 'price_multiplier')
    ):
        return 'different_billing_basis'
    if abs(number(row['quantity']) * number(row['unit_price']) - number(row['subtotal'])) > Decimal('0.01'):
        return 'line_arithmetic_mismatch'
    return None


def reference(row, excluded):
    result = {k: row.get(k) for k in (
        'kind', 'project', 'project_id', 'project_key', 'contract_id', 'record_id',
        'supplier', 'signed_date', 'item_name', 'brand', 'model', 'spec', 'description',
        'quantity', 'unit', 'unit_price', 'subtotal', 'currency', 'tax_basis',
        'agreement_type', 'source_token', 'source_locator', 'line_id', 'record_status',
        'ledger_amount_cny_tax_inclusive', 'source_stage', 'source_payment_basis',
        'period', 'billing_period', 'billing_multiplier', 'price_multiplier',
        'source_price_version', 'detail_kind', 'source_material_raw', 'source_attributes',
        'parent_item_name', 'parent_line_id', 'source_fields_reviewed', 'source_document_type',
        'confirmed_rate_to_cny', 'finance_conversion_evidence', 'finance_conversion_status', 'finance_conversion_pending_reason',
        'subtotal_finance_cny_yuan', 'subtotal_finance_evidence',
        'source_role', 'source_cell', 'source_table', 'source_chain', 'source_image_sha256',
        'source_original_path', 'scope_association_pending', 'association_status', 'comparison_eligible',
        'valuation_eligible', 'standard_object_name', 'source_columns', 'amount_role', 'amount_source',
        'price_basis', 'source_variant_id', 'price_variant_scope', 'variant_id', 'version_exclusive',
        'quotation_variant_id', 'quotation_variant_name', 'parent_quote_variant',
        'economic_purchase_group', 'purchase_evidence_group',
        'source_scope', 'source_project_context', 'pricing_relationship',
        'exclude_from_procurement_price_comparison'
    )}
    attrs = row.get('source_attributes') or {}
    for field in ('quotation_variant_id', 'quotation_variant_name', 'parent_quote_variant',
                  'economic_purchase_group', 'purchase_evidence_group'):
        if result.get(field) is None and attrs.get(field) is not None:
            result[field] = attrs[field]
    return normalize_money_fields({**result, 'scope': scope(row), 'estimation_exclusion': excluded}, metadata={'amount_unit':'元'})


def search(rows, phrase, limit):
    terms = norm(phrase).split()
    if not terms:
        raise ValueError('请输入项目、名称、型号或规格关键词')
    direct = []
    contextual = []
    for row, reason in rows:
        context = ' '.join(norm(x.get('description')) for x in row.get('context', []))
        haystack = ' '.join(norm(row.get(k)) for k in (
            'project', 'project_id', 'item_name', 'model', 'brand', 'spec', 'module',
            'description', 'work_package', 'supplier'
        ))
        if all(term in haystack for term in terms):
            direct.append({**reference(row, reason), 'match_scope':'line_fields'})
        elif all(term in f'{haystack} {context}' for term in terms):
            contextual.append({**reference(row, reason), 'match_scope':'contract_context'})
    found = direct or contextual
    return {'match_count': len(found), 'match_scope':'line_fields' if direct else 'contract_context',
            'other_context_matches':len(contextual) if direct else 0, 'references': found[:limit]}


def estimate(rows, query):
    needed = ('item_name', 'unit', 'currency', 'agreement_type', 'scope')
    if any(not norm(query.get(k)) for k in needed) or not (norm(query.get('model')) or norm(query.get('spec'))):
        raise ValueError('估价需要名称、型号或规格、计价单位、币种、协议类型和工作范围')
    if not positive(query.get('quantity')):
        raise ValueError('估价数量须大于零')
    quantity = number(query['quantity'])
    key = comparable_key(query)
    matches = defaultdict(list)
    excluded = Counter()
    for row, reason in rows:
        if row['kind'] != 'bom_line':
            continue
        values = {**row, 'scope': scope(row)}
        if comparable_key(values) != key:
            continue
        if reason:
            excluded[reason] += 1
        else:
            matches[row['project_key']].append(row)
    # Different unit prices in the same project are an ambiguity, not independent observations.
    samples = []
    for project_rows in matches.values():
        prices = {number(row['unit_price']) for row in project_rows}
        if len(prices) != 1:
            excluded['conflicting_prices_within_project'] += len(project_rows)
            continue
        samples.append(project_rows[0])
        excluded['repeated_price_within_project'] += len(project_rows) - 1
    prices = [number(row['unit_price']) for row in samples]
    result = {'status': 'estimated' if len(prices) >= 2 else 'single_reference' if prices else 'insufficient_evidence',
              'independent_project_count': len(prices), 'currency': query['currency'],
              'quantity': str(quantity), 'references': [reference(row, None) for row in samples],
              'excluded': {k: v for k, v in excluded.items() if v}}
    if len(prices) >= 2:
        result['unit_price_range'] = [str(min(prices)), str(max(prices))]
        result['reference_unit_price'] = str(median(prices))
        result['estimated_total_range'] = [str(min(prices)*quantity), str(max(prices)*quantity)]
        result['estimated_total'] = str(median(prices)*quantity)
    return result


def main():
    parser = argparse.ArgumentParser(description='采购历史报价检索与估价')
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parents[1] / 'data')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('audit')
    lookup = commands.add_parser('search')
    lookup.add_argument('phrase')
    lookup.add_argument('--limit', type=int, default=10)
    lookup.add_argument('--include-pending', action='store_true',
                        help='同时查待复核原件明细，仅供回查')
    price = commands.add_parser('estimate')
    price.add_argument('query', type=Path)
    args = parser.parse_args()
    try:
        data, duplicates, shared, total, checked = load(args.data)
        rows = [(row, rejection(row, duplicates, shared)) for row in data if is_checked(row)]
        if args.command == 'audit':
            result = {'ledger_records': total, 'source_checked_records': checked,
                      'other_ledger_records': total - checked,
                      'checked_bom_lines': sum(row['kind'] == 'bom_line' for row, _ in rows),
                      'checked_whole_scope_quotes': sum(row['kind'] == 'whole_scope_quote' for row, _ in rows),
                      'bom_lines_eligible_for_matching': sum(reason is None for _, reason in rows),
                      'comparable_groups_with_multiple_projects': count_estimate_groups(rows),
                      'exclusions_by_first_reason': dict(Counter(reason for _, reason in rows if reason))}
        elif args.command == 'search':
            if args.limit < 1:
                raise ValueError('结果条数须大于零')
            if args.include_pending:
                rows.extend((row, 'scope_association_pending' if association_pending(row)
                             else 'pending_source_review') for row in data if not is_checked(row))
            result = search(rows, args.phrase, args.limit)
        else:
            query = json.loads(args.query.read_text())
            if not isinstance(query, dict):
                raise ValueError('估价输入须为 JSON 对象')
            result = estimate(rows, query)
    except (OSError, KeyError, ValueError) as exc:
        parser.exit(2, f'{exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
