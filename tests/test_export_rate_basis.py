import tempfile
import unittest
from pathlib import Path
from valuation_agent.excel_export import export_comparison
from openpyxl import load_workbook

class RateBasisExport(unittest.TestCase):
    def test_calculated_price_basis_survives_excel(self):
        ref = dict(item_name='模型制作', currency='CNY', unit='人天', quantity=9,
                   unit_price=1200, subtotal=10800, unit_price_derivation={
                       'method':'verified_original_amount_divided_by_billing_quantity',
                       'amount':'10800','quantity':'9','unit':'人天','basis':'原报价，优惠另计'})
        with tempfile.TemporaryDirectory() as tmp:
            path = export_comparison({'rows':[{'quote':{'item_name':'模型制作'},'references':[ref]}]}, Path(tmp)/'result.xlsx')
            book = load_workbook(path)
            sheet = book['历史参考']
            self.assertEqual(sheet.cell(2,8).value,1200)
            self.assertEqual(sheet.cell(1,18).value,'单价依据')
            self.assertEqual(sheet.cell(2,18).value,'计算单价：10800元 ÷ 9人天；原报价，优惠另计')
            book.close()

    def test_package_total_is_not_exported_as_unit_price(self):
        ref = dict(item_name='整包制作', currency='CNY', unit_price=10000,
                   reference_price_type='package_total', reference_total_cny_yuan=10000)
        with tempfile.TemporaryDirectory() as tmp:
            path = export_comparison({'rows':[{'quote':{'item_name':'制作'},'references':[ref]}]}, Path(tmp)/'result.xlsx')
            book = load_workbook(path)
            sheet = book['历史参考']
            self.assertIsNone(sheet.cell(2,8).value)
            self.assertEqual(sheet.cell(2,9).value,10000)
            self.assertIsNone(sheet.cell(2,18).value)
            book.close()
