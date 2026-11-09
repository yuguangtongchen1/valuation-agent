"""Explicit monetary scales and evidenced CNY conversion; never infer an FX rate."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
import unicodedata


SCHEMA = 'money-unit-v1'
CURRENCIES = {
    'CNY': 'CNY', 'RMB': 'CNY', '人民币': 'CNY', '人民币元': 'CNY',
    'HKD': 'HKD', '港币': 'HKD', '港元': 'HKD', 'HK$': 'HKD',
    'USD': 'USD', '美元': 'USD', '美金': 'USD', 'US$': 'USD',
    'SGD': 'SGD', '新加坡币': 'SGD', '新加坡元': 'SGD', '新币': 'SGD', 'S$': 'SGD',
}
SCALES = {'元': Decimal(1), '万元': Decimal(10000)}
CURRENCY_PATTERN = '|'.join(re.escape(k) for k in sorted(CURRENCIES, key=len, reverse=True))
VALUE = re.compile(r'^(?P<prefix>' + CURRENCY_PATTERN + r')?\s*(?P<symbol>[¥￥$])?\s*'
                   r'(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*'
                   r'(?P<scale>万元|元|万)?\s*(?P<suffix>' + CURRENCY_PATTERN + r')?\s*(?P<tail>元)?$', re.I)


def decimal(value, label):
    if isinstance(value, bool):
        raise ValueError(f'{label} cannot be boolean')
    try:
        amount = Decimal(str(value).replace(',', '').replace('，', '').strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'{label} must be an explicit number: {value}') from exc
    if not amount.is_finite():
        raise ValueError(f'{label} must be finite')
    return amount


def currency_code(value):
    value = unicodedata.normalize('NFKC', str(value or '')).strip()
    return CURRENCIES.get(value.upper(), CURRENCIES.get(value, value.upper() if re.fullmatch('[A-Za-z]{3}', value) else None))


def unit_details(value):
    """Return explicit scale and currency, accepting e.g. 人民币万元/套."""
    if value in (None, ''):
        return None, None
    raw = unicodedata.normalize('NFKC', str(value)).strip()
    # A denominator describes the billing unit, not the monetary scale.
    raw = re.split(r'[/／]', raw, maxsplit=1)[0].strip().replace(' ', '')
    currencies = []
    for token in sorted(CURRENCIES, key=len, reverse=True):
        if token.casefold() in raw.casefold():
            currencies.append(CURRENCIES[token])
            raw = re.sub(re.escape(token), '', raw, flags=re.I)
    if len(set(currencies)) > 1:
        raise ValueError(f'Conflicting currencies in monetary unit: {value}')
    raw = raw.strip('()（）')
    if raw == '万' and currencies:
        raw = '万元'
    if not raw and currencies:
        raw = '元'
    if raw not in SCALES:
        raise ValueError(f'Unsupported or unclear monetary unit: {value}')
    return raw, currencies[0] if currencies else None


def normalize_money(value, currency=None, amount_unit=None, confirmed_rate_to_cny=None,
                    source_evidence=None, finance_conversion_evidence=None):
    """Scale a value to original-currency 元, then separately convert to CNY.

    For foreign currencies the named confirmed rate AND source/finance evidence
    are required. A normalized result can be passed again without rescaling it.
    The function does not infer currency from a bare 元, ¥, $, or amount size.
    """
    if isinstance(value, dict) and value.get('schema') == SCHEMA:
        prior = value
        item = normalize_money(prior.get('raw_value'), prior.get('raw_currency'), prior.get('raw_unit'),
                               prior.get('confirmed_rate_to_cny'), prior.get('source_evidence'),
                               prior.get('finance_conversion_evidence'))
        return _associate_ledger_total(item, prior.get('ledger_cny_yuan'), prior.get('ledger_cny_evidence'))
    raw_value = str(value) if isinstance(value, Decimal) else value
    result = {'schema': SCHEMA, 'raw_value': raw_value, 'raw_unit': amount_unit,
              'raw_currency': currency, 'base_amount': None, 'base_unit': '元',
              'base_currency': currency_code(currency), 'cny_yuan': None,
              'confirmed_rate_to_cny': str(confirmed_rate_to_cny) if confirmed_rate_to_cny is not None else None,
              'source_evidence': deepcopy(source_evidence),
              'finance_conversion_evidence': deepcopy(finance_conversion_evidence),
              'conversion_evidence': [], 'status': 'missing_amount'}
    if value is None or str(value).strip() in ('', '—', '-', '/'):
        return result
    if isinstance(value, bool):
        raise ValueError('Money cannot be boolean')
    unit, unit_currency = unit_details(amount_unit)
    raw = unicodedata.normalize('NFKC', str(value)).strip().replace(',', '').replace('，', '')
    match = VALUE.fullmatch(raw)
    if not match:
        raise ValueError(f'Money must be numeric with an explicit supported unit: {value}')
    inline_currency = {currency_code(match[k]) for k in ('prefix', 'suffix') if match[k]}
    declared_currency = {code for code in (currency_code(currency), unit_currency, *inline_currency) if code}
    if len(declared_currency) > 1:
        raise ValueError(f'Conflicting currency labels for amount: {value} / {currency} / {amount_unit}')
    code = next(iter(declared_currency), None)
    if match['symbol'] and not code:
        # A symbol alone is not enough to choose a currency.
        result['currency_symbol_unresolved'] = match['symbol']
    inline_unit = '万元' if match['scale'] in ('万', '万元') else '元' if match['scale'] or match['tail'] else None
    if inline_unit and unit and inline_unit != unit:
        raise ValueError(f'Conflicting monetary scales: {value} / {amount_unit}')
    scale_unit = inline_unit or unit or '元'
    factor = SCALES[scale_unit]
    amount = decimal(match['number'], 'Money')
    base = amount * factor
    result.update(base_amount=str(base), base_currency=code,
                  source_numeric_value=str(amount), source_scale_unit=scale_unit,
                  status='awaiting_confirmed_fx' if code else 'missing_currency')
    result['conversion_evidence'].append({
        'step': 'scale_to_original_currency_base_unit', 'from_unit': scale_unit,
        'to_unit': '元', 'factor': str(factor),
        'basis': 'explicit_value_unit' if inline_unit else 'explicit_column_or_field_unit' if unit else 'unscaled_numeric_base_unit',
        'evidence': deepcopy(source_evidence),
    })
    if code == 'CNY':
        result.update(cny_yuan=str(base), status='cny_ready')
        result['conversion_evidence'].append({'step': 'currency_to_cny', 'rate': '1', 'basis': 'explicit_CNY_identity'})
    elif confirmed_rate_to_cny is not None:
        rate = decimal(confirmed_rate_to_cny, 'Confirmed rate to CNY')
        if rate <= 0:
            raise ValueError('Confirmed rate to CNY must be positive')
        evidence = finance_conversion_evidence or source_evidence
        if code and evidence:
            result.update(cny_yuan=str(base * rate), status='cny_ready')
            result['conversion_evidence'].append({'step': 'currency_to_cny', 'from_currency': code,
                                                 'rate': str(rate), 'basis': 'explicit_confirmed_rate',
                                                 'evidence': deepcopy(evidence)})
        else:
            result['conversion_evidence'].append({'step': 'currency_to_cny', 'status': 'not_applied',
                                                 'reason': 'missing_currency_or_confirmation_evidence'})
    return result


def _associate_ledger_total(item, amount, proof, owner=None):
    """A verified CNY whole-scope association is not an exchange-rate operation."""
    if not isinstance(proof, dict) or amount is None:
        return item
    required = (proof.get('basis') == 'user_finance_confirmed_contract_mapping'
                and proof.get('mapping_kind') == 'linked_whole_scope_ledger_total'
                and proof.get('source_validation_status') == 'passed'
                and proof.get('scope_relation') == 'same_whole_scope_as_finance_ledger'
                and proof.get('applies_to_field') == 'subtotal'
                and proof.get('target_currency') == 'CNY'
                and proof.get('source_sha256') and proof.get('source_locator')
                and proof.get('source_token') and proof.get('ledger_record_id'))
    if not required:
        return item
    if owner is not None:
        for source_key, row_key in (('ledger_record_id','record_id'), ('source_token','source_token'),
                                    ('source_locator','source_locator'), ('source_line_id','line_id')):
            if proof.get(source_key) is not None and proof.get(source_key) != owner.get(row_key):
                # A normalized object copied to another BOM row must lose the parent's ledger total.
                return normalize_money(item.get('raw_value'), item.get('raw_currency'), item.get('raw_unit'),
                                       item.get('confirmed_rate_to_cny'), item.get('source_evidence'),
                                       item.get('finance_conversion_evidence'))
    value = decimal(amount, 'Associated ledger CNY total')
    if value <= 0 or value != decimal(proof.get('ledger_total_cny_tax_inclusive'), 'Reviewed ledger total'):
        return item
    original = normalize_money(proof.get('source_amount'), proof.get('source_currency'),
                               proof.get('source_amount_unit'))
    if (original.get('base_amount') != item.get('base_amount')
            or original.get('base_currency') != item.get('base_currency')):
        return item
    result = deepcopy(item)
    result.update(cny_yuan=str(value), status='cny_ready',
                  ledger_cny_yuan=str(value), ledger_cny_evidence=deepcopy(proof))
    result['conversion_evidence'] = [step for step in result['conversion_evidence']
                                     if step.get('step') != 'associate_finance_ledger_CNY_total']
    result['conversion_evidence'].append({'step':'associate_finance_ledger_CNY_total',
                                         'not_exchange_rate':True, 'not_currency_inference':True,
                                         'not_unit_price_allocation':True, 'evidence':deepcopy(proof)})
    return result


def normalize_money_fields(row, metadata=None, fields=('unit_price', 'subtotal')):
    """Return a copy with base-unit money, CNY columns, and original evidence.

    Field-specific ``unit_price_amount_unit`` / ``subtotal_amount_unit`` override
    shared ``amount_unit`` / ``money_unit`` / ``金额单位``. The current fields are
    then labelled 元, so repeated import never multiplies normalized values again.
    ``money_normalization[field]`` retains the original raw value/unit/currency.
    """
    metadata = metadata or {}
    result = deepcopy(row)
    previous = result.get('money_normalization') or {}
    normalized = {}
    common_currency = result.get('currency') or metadata.get('currency')
    attrs = result.get('source_attributes') or {}
    for field in fields:
        value = result.get(field)
        unit = (result.get(field + '_amount_unit') or result.get(field + '_money_unit')
                or result.get('amount_unit') or result.get('money_unit') or result.get('金额单位')
                or attrs.get(field + '_amount_unit') or attrs.get('amount_unit') or attrs.get('money_unit')
                or metadata.get(field + '_amount_unit') or metadata.get('amount_unit') or metadata.get('money_unit'))
        code = result.get(field + '_currency') or common_currency
        rate = result.get(field + '_confirmed_rate_to_cny', result.get('confirmed_rate_to_cny',
                     attrs.get('confirmed_rate_to_cny', metadata.get('confirmed_rate_to_cny'))))
        source = result.get('source_evidence') or attrs.get('source_evidence') or metadata.get('source_evidence')
        finance = (result.get('finance_conversion_evidence') or attrs.get('finance_conversion_evidence')
                   or metadata.get('finance_conversion_evidence'))
        old = previous.get(field)
        # Only reuse a prior conversion when the present value explicitly is its
        # normalized base amount; a changed value is processed as a new reading.
        if (isinstance(old, dict) and old.get('schema') == SCHEMA
                and old.get('base_amount') is None and value is None and old.get('raw_value') is None):
            item = normalize_money(old)
        elif (isinstance(old, dict) and old.get('schema') == SCHEMA and old.get('base_amount') is not None
                and unit_details(unit)[0] == '元' and currency_code(code) == old.get('base_currency')
                and decimal(value, field) == decimal(old['base_amount'], field)):
            item = normalize_money(old)
            # Newly supplied finance evidence may finish a previously pending FX conversion.
            if rate is not None and (finance or source):
                item = normalize_money(old['raw_value'], old.get('raw_currency'), old.get('raw_unit'),
                                       rate, source or old.get('source_evidence'), finance or old.get('finance_conversion_evidence'))
        else:
            item = normalize_money(value, code, unit, rate, source, finance)
        if field == 'subtotal':
            item = _associate_ledger_total(item,
                                           result.get('subtotal_finance_cny_yuan', item.get('ledger_cny_yuan')),
                                           result.get('subtotal_finance_evidence') or item.get('ledger_cny_evidence'),
                                           owner=result)
        normalized[field] = item
        result[field] = item['base_amount']
        result[field + '_amount_unit'] = '元'
        result[field + '_currency'] = item['base_currency']
        result[field + '_cny_yuan'] = item['cny_yuan']
        if not common_currency and item['base_currency']:
            common_currency = item['base_currency']
    result['money_normalization'] = normalized
    price_currency = normalized.get('unit_price', {}).get('base_currency')
    if price_currency or common_currency:
        result['currency'] = price_currency or currency_code(common_currency) or common_currency
    return result
