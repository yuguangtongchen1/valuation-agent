"""Read cached BIFF values and merged ranges without executing workbook content."""
import math


def legacy_xls_document(payload):
    if len(payload) > 30 * 1024 * 1024:
        raise ValueError('文件超过 30 MB，请拆分后导入。')
    if payload[:8] != bytes.fromhex('d0cf11e0a1b11ae1'):
        raise ValueError('无法识别旧版 Excel 文件，请确认文件未损坏。')
    try:
        import xlrd
    except ImportError as exc:
        raise ValueError('读取旧版 Excel 需要安装 xlrd，请先安装 Excel 支持组件。') from exc
    try:
        book = xlrd.open_workbook(file_contents=payload, formatting_info=True, on_demand=True)
    except (xlrd.XLRDError, xlrd.compdoc.CompDocError) as exc:
        raise ValueError('无法解析旧版 Excel 文件，请确认文件未损坏或加密。') from exc
    output, cells = [], 0
    try:
        for sheet in book.sheets():
            if sheet.nrows * sheet.ncols > 5000000:
                raise ValueError('工作表格式范围过大，请清理空白格式后导入。')
            # Old Excel files often format all 255 columns despite ten real columns.
            # Trim only format-only edges; retain blank cells inside actual tables.
            last_row, last_col = 0, 0
            for n, row in enumerate(sheet.get_rows()):
                active = [i for i, cell in enumerate(row) if cell.ctype not in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK)]
                if active:
                    last_row, last_col = n+1, max(last_col, max(active)+1)
            merged = [m for m in sheet.merged_cells if sheet.cell(m[0],m[2]).ctype not in (xlrd.XL_CELL_EMPTY,xlrd.XL_CELL_BLANK)]
            for _, end, _, right in merged:
                last_row, last_col = max(last_row,end), max(last_col,right)
            merged = [m for m in sheet.merged_cells if m[1] <= last_row and m[3] <= last_col]
            if last_row > 5000 or last_col > 60:
                raise ValueError('工作表超过 5000 行或 60 列，请拆分后导入。')
            cells += last_row * last_col
            if cells > 1000000:
                raise ValueError('工作簿内容过多，请拆分后导入。')
            rows = []
            for n in range(last_row):
                values = []
                for cell in sheet.row(n)[:last_col]:
                    value = cell.value
                    if cell.ctype == xlrd.XL_CELL_ERROR:
                        raise ValueError(f'工作表“{sheet.name}”第 {n+1} 行存在公式错误，请修正后导入。')
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        value = xlrd.xldate_as_datetime(value, book.datemode).isoformat()
                    if isinstance(value, float) and not math.isfinite(value):
                        raise ValueError('Excel 包含无效数值，请修正后导入。')
                    values.append(value)
                rows.append({'row':n+1, 'values':values})
            output.append({'name':sheet.name, 'rows':rows, 'merged_ranges':merged})
        return {'sheets':output}
    finally:
        book.release_resources()
