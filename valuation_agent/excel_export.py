"""Table-only Excel delivery from the same comparison JSON as the CLI."""
from pathlib import Path
from decimal import Decimal,InvalidOperation

def number(value):
    if value is None or value=='':return None
    try:
        n=Decimal(str(value))
        return float(n) if n.is_finite()else None
    except InvalidOperation:return None

def derived_rate_basis(row):
    derivation = row.get('unit_price_derivation') or {}
    if derivation.get('method') not in ('subtotal_div_quantity', 'verified_original_amount_divided_by_billing_quantity'):
        return derivation.get('basis') or ''
    amount, quantity = derivation.get('amount'), derivation.get('quantity')
    unit = derivation.get('unit') or row.get('unit') or ''
    return f"计算单价：{amount}元 ÷ {quantity}{unit}" + (f"；{derivation['basis']}" if derivation.get('basis') else '')

def rate_basis(row):
    parts = [derived_rate_basis(row)]
    context = row.get('verified_billing_context')
    if isinstance(context, dict):
        for prefix, label in (('physical', '实物数量'), ('billing', '计费数量')):
            quantity, unit = context.get(prefix + '_quantity'), context.get(prefix + '_unit')
            if quantity is not None and unit:
                parts.append(f"{label}：{quantity}{unit}")
        if context.get('fixed_total_cny') is not None:
            parts.append(f"固定总额：{context['fixed_total_cny']}元")
        for key in ('pricing_basis', 'settlement_terms'):
            if context.get(key):
                parts.append(str(context[key]))
        services = context.get('included_services')
        if isinstance(services, list) and services:
            parts.append('包含：' + '、'.join(str(v) for v in services))
    return '；'.join(dict.fromkeys(p for p in parts if p))

def export_comparison(result,path):
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    from openpyxl.utils import get_column_letter
    book=Workbook();current=book.active;current.title='当前报价';history=book.create_sheet('历史参考')
    current.append(['项目','清单编号','物料','规格/型号','工艺/配置','数量','单位','单价（人民币元）','小计（人民币元）','参考条数'])
    history.append(['当前清单编号','当前物料','历史项目','历史物料','规格/型号','数量','单位','单价（人民币元）','整包或小计（人民币元）','匹配类型','匹配依据','差异','供应商','合同记录','明细标识','原件位置','报价版本','单价依据'])
    for i,item in enumerate(result['rows'],1):
        q=item['quote'];refs=item.get('references',[]);key=q.get('row_id')or q.get('source_locator')or i
        def cny(row,field):
            return number(row.get(field+'_cny_yuan',row.get(field)if row.get('currency')=='CNY'else None))
        current.append([result.get('project'),str(key),q['item_name'],' / '.join(dict.fromkeys(filter(None,[q.get('spec'),q.get('model')]))),' · '.join(filter(None,[q.get('description'),q.get('configuration')])),number(q.get('quantity')),q.get('unit'),cny(q,'unit_price'),cny(q,'subtotal'),len(refs)])
        for r in refs:
            package=r.get('reference_price_type')=='package_total'or r.get('kind')=='whole_scope_quote'
            history.append([str(key),q['item_name'],r.get('project')or r.get('value'),r.get('item_name'),r.get('spec'),number(r.get('quantity')),r.get('unit'),None if package else cny(r,'unit_price'),number(r.get('reference_total_cny_yuan'))if package and r.get('reference_total_cny_yuan')is not None else cny(r,'subtotal'),r.get('match_kind'),r.get('match_reason'),'；'.join(r.get('differences',[])),r.get('supplier'),r.get('record_id'),r.get('line_id'),r.get('source_locator') or ('%s %s'%(r.get('sheet',''),r.get('address',''))).strip(),r.get('quotation_variant_name'),rate_basis(r)])
    for sheet in book:
        sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='20634F')
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                # Preserve source text as text, including formula-looking names.
                if isinstance(cell.value,str):cell.data_type='s'
                cell.alignment=Alignment(vertical='top',wrap_text=True)
        for i in range(1,sheet.max_column+1):sheet.column_dimensions[get_column_letter(i)].width=24
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);book.save(path)
    return path
