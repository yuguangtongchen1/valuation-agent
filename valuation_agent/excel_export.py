"""Table-only Excel delivery from the same comparison JSON as the CLI."""
from pathlib import Path
from decimal import Decimal,InvalidOperation

def number(value):
    if value is None or value=='':return None
    try:
        n=Decimal(str(value))
        return float(n) if n.is_finite()else None
    except InvalidOperation:return None

def export_comparison(result,path):
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    from openpyxl.utils import get_column_letter
    book=Workbook();current=book.active;current.title='当前报价';history=book.create_sheet('历史参考')
    current.append(['项目','清单编号','物料','规格/型号','工艺/配置','数量','单位','单价（人民币元）','小计（人民币元）','参考条数'])
    history.append(['当前清单编号','当前物料','历史项目','历史物料','规格/型号','数量','单位','单价（人民币元）','整包或小计（人民币元）','匹配类型','匹配依据','差异','供应商','合同记录','明细标识','原件位置','报价版本'])
    for i,item in enumerate(result['rows'],1):
        q=item['quote'];refs=item.get('references',[]);key=q.get('row_id')or q.get('source_locator')or i
        def cny(row,field):
            return number(row.get(field+'_cny_yuan',row.get(field)if row.get('currency')=='CNY'else None))
        current.append([result.get('project'),str(key),q['item_name'],' / '.join(dict.fromkeys(filter(None,[q.get('spec'),q.get('model')]))),' · '.join(filter(None,[q.get('description'),q.get('configuration')])),number(q.get('quantity')),q.get('unit'),cny(q,'unit_price'),cny(q,'subtotal'),len(refs)])
        for r in refs:
            package=r.get('reference_price_type')=='package_total'or r.get('kind')=='whole_scope_quote'
            history.append([str(key),q['item_name'],r.get('project')or r.get('value'),r.get('item_name'),r.get('spec'),number(r.get('quantity')),r.get('unit'),None if package else cny(r,'unit_price'),number(r.get('reference_total_cny_yuan'))if package and r.get('reference_total_cny_yuan')is not None else cny(r,'subtotal'),r.get('match_kind'),r.get('match_reason'),'；'.join(r.get('differences',[])),r.get('supplier'),r.get('record_id'),r.get('line_id'),r.get('source_locator') or ('%s %s'%(r.get('sheet',''),r.get('address',''))).strip(),r.get('quotation_variant_name')])
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
