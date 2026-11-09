"""Read-only CNY display ratios from a finance-confirmed contract/ledger mapping.

The ratio is a ledger allocation basis, not a bank FX quote or an original
individual transaction price.  Original quote prices/currencies are never edited.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, localcontext
import re


BASIS = 'user_finance_confirmed_contract_mapping'
_CURRENCIES = {'CNY', 'HKD', 'USD', 'SGD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD',
               'NZD', 'CHF', 'KRW', 'THB', 'MYR', 'TWD', 'MOP'}
_ALIASES = {'RMB': 'CNY', '人民币': 'CNY', '人民币元': 'CNY', '港币': 'HKD',
            '港元': 'HKD', '美元': 'USD', '美金': 'USD', '新加坡元': 'SGD',
            '新加坡币': 'SGD', '新币': 'SGD', '欧元': 'EUR', '英镑': 'GBP',
            '日元': 'JPY', '澳元': 'AUD', '加元': 'CAD'}
# Scope flags concern what total is being allocated, not tax/financial approval.
_EXCLUDED_SCOPES = {'payment_application', 'payment', 'installment', 'progress_payment',
                    'original_contract', 'prior_contract', 'subtotal', 'partial',
                    'rate_card', 'quotation', 'invoice', 'original_agreement'}
_EXCLUDED_LABEL = re.compile(r'原合同|变更前|调整前|分期|本期|已付|未付|预付款|尾款|进度款|小计|刊例')
_VERSION_CONFLICT = re.compile(r'^(?:old|original|prior|superseded|draft|alternative)$', re.I)


def _currency(value):
    label = str(value or '').strip()
    code = _ALIASES.get(label, label.upper())
    return code if code in _CURRENCIES else None


def _amount(value, scale=None):
    """Read explicit base amounts/scales only; a prior base amount is not rescaled."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        if value.get('base_amount') is not None:
            return _amount(value['base_amount'], '元')
        return None
    raw = str(value).strip().replace(',', '').replace('，', '')
    match = re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(万元|元)?', raw)
    if not match or scale not in (None, '', '元', '万元'):
        return None
    inline = match[2]
    if inline and scale and inline != scale:
        return None
    try:
        number = Decimal(match[1])
        return number * (10000 if (inline or scale) == '万元' else 1) if number.is_finite() else None
    except InvalidOperation:
        return None


def _plain(value):
    return format(value, 'f')


def _is_whole(review):
    return (review.get('source_table_covers_this_agreement') is True
            and review.get('scope') not in _EXCLUDED_SCOPES
            and not _EXCLUDED_LABEL.search(str(review.get('label') or ''))
            and not _VERSION_CONFLICT.fullmatch(str(review.get('price_version') or '')))


class FinanceView:
    """Build once for a quote collection; return only display conversion metadata."""
    def __init__(self, acceptance):
        contracts = acceptance.get('contracts', []) if isinstance(acceptance, dict) else acceptance
        self.contracts = {}
        self.duplicate_records = set()
        for contract in contracts or []:
            rid = contract.get('record_id')
            if rid in self.contracts:
                self.duplicate_records.add(rid)
            self.contracts[rid] = contract

    def for_row(self, row):
        code = _currency(row.get('currency'))
        output = {'finance_conversion_status': 'pending', 'confirmed_rate_to_cny': None,
                  'finance_conversion_evidence': None}
        def pending(reason):
            return {**output, 'finance_conversion_pending_reason': reason}
        if not code:
            return pending('unknown_or_missing_source_currency')
        field_codes = {_currency(row.get(field + '_currency'))
                       for field in ('unit_price', 'subtotal') if row.get(field + '_currency')}
        if field_codes and field_codes != {code}:
            return pending('conflicting_line_money_currencies')
        if code == 'CNY':
            return {**output, 'finance_conversion_status': 'cny_identity',
                    'confirmed_rate_to_cny': '1',
                    'finance_conversion_evidence': {'basis': 'explicit_CNY_identity',
                                                    'source_currency': 'CNY', 'target_currency': 'CNY'}}
        rid, token = row.get('record_id'), row.get('source_token')
        if not rid or not token:
            return pending('missing_record_or_source_token')
        if rid in self.duplicate_records:
            return pending('ambiguous_ledger_record')
        contract = self.contracts.get(rid)
        if not contract:
            return pending('missing_contract_acceptance')
        if _currency(contract.get('ledger_currency')) != 'CNY':
            return pending('ledger_currency_not_explicit_CNY')
        ledger = _amount(contract.get('ledger_tax_inclusive_amount'))
        if ledger is None or ledger <= 0:
            return pending('missing_or_nonpositive_ledger_CNY_total')
        row_ledger = _amount(row.get('ledger_amount_cny_tax_inclusive'))
        if row.get('ledger_amount_cny_tax_inclusive') not in (None, '') and row_ledger != ledger:
            return pending('conflicting_ledger_CNY_totals')
        if row.get('scope_association_pending') or row.get('association_review_needed'):
            return pending('source_contract_association_pending')
        attrs = row.get('source_attributes') or {}
        if (_VERSION_CONFLICT.fullmatch(str(row.get('price_version') or attrs.get('price_version') or ''))
                or row.get('source_document_type') in ('rate_card', 'payment_application', 'invoice')):
            return pending('line_price_scope_not_current_contract')
        # Reviewed agreement totals take precedence over raw parser candidates.
        # Unreviewed candidates require their own explicit full-agreement flag.
        reviewed = [v for v in contract.get('visually_reviewed_contract_totals', [])
                    if v.get('source_token') == token]
        candidates = reviewed or [v for v in contract.get('contract_total_candidates', [])
                                  if v.get('source_token') == token]
        if not candidates:
            return pending('no_total_for_exact_source_token')
        eligible = [v for v in candidates if _is_whole(v)]
        if not eligible:
            return pending('no_explicit_whole_agreement_total')
        if any(not v.get('source_locator') for v in eligible):
            return pending('contract_total_source_locator_missing')
        currencies = {_currency(v.get('currency')) for v in eligible}
        if None in currencies or currencies != {code}:
            return pending('ambiguous_or_conflicting_contract_total_currency')
        totals = [_amount(v.get('amount'), v.get('amount_unit') or v.get('money_unit')) for v in eligible]
        if any(v is None or v <= 0 for v in totals):
            return pending('missing_or_nonpositive_original_contract_total')
        if len(set(totals)) != 1:
            return pending('multiple_original_contract_totals_or_versions')
        versions = {str(v.get('price_version')) for v in eligible if v.get('price_version')}
        if len(versions) > 1:
            return pending('multiple_original_contract_totals_or_versions')
        original = totals[0]
        # Store an exact rational basis as well as a high-precision decimal view.
        # This avoids binary floats and preserves non-terminating ratios honestly.
        with localcontext() as context:
            context.prec = 80
            ratio = ledger / original
        proof = {'basis': BASIS, 'label': '财务台账折算比例',
                 'display_only': True, 'not_bank_exchange_rate': True,
                 'not_original_item_transaction_price': True,
                 'ledger_record_id': rid, 'source_token': token,
                 'source_currency': code, 'target_currency': 'CNY',
                 'original_contract_total': _plain(original), 'original_contract_amount_unit': '元',
                 'ledger_total_cny_tax_inclusive': _plain(ledger),
                 'ratio_numerator_cny_yuan': _plain(ledger),
                 'ratio_denominator_original_currency_yuan': _plain(original),
                 'source_locators': list(dict.fromkeys(v['source_locator'] for v in eligible)),
                 'original_contract_total_evidence': deepcopy(eligible),
                 'selection': 'visually_reviewed_whole_agreement' if reviewed else 'explicit_whole_agreement_total',
                 'note': '按用户已确认的合同与财务台账对应关系作比例展示；原币原价不变。'}
        return {**output, 'finance_conversion_status': 'finance_proportional_view',
                'confirmed_rate_to_cny': _plain(ratio), 'finance_conversion_evidence': proof}


def finance_conversion_for_row(row, acceptance):
    """Convenience wrapper; prefer FinanceView for a batch."""
    return FinanceView(acceptance).for_row(row)
