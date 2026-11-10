import unittest,tempfile
from pathlib import Path
from valuation_agent.excel_export import export_comparison
from valuation_agent.io import read_input
from openpyxl import Workbook,load_workbook
class DeliveryTests(unittest.TestCase):
 def test_title_rows_and_source_position(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'quote.xlsx';b=Workbook();s=b.active;s.append(['项目标题']);s.append([]);s.append(['物料','数量','单位','单价','小计']);s.append(['灯',2,'个',10,20]);b.save(p)
   r=read_input(p)['rows'][0];self.assertEqual(r['item_name'],'灯');self.assertTrue(r['source_locator'].endswith('row 4'))
 def test_sections_summaries_and_unnamed_price(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'quote.xlsx';b=Workbook();s=b.active
   s.append(['序号','物料','数量','单价','小计'])
   s.append(['制作物料']);s.append([1,'灯',2,10,20]);s.append([None,None,'合计',None,20]);b.save(p)
   r=read_input(p);self.assertEqual(len(r['rows']),1);self.assertEqual(len(r['non_item_rows']),2)
   self.assertTrue(r['rows'][0]['source_locator'].endswith('row 3'))
   s.append([2,None,1,30,30]);b.save(p)
   with self.assertRaisesRegex(ValueError,'缺物料'):read_input(p)
 def test_package_and_formula_text(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'out.xlsx';export_comparison({'rows':[{'quote':{'item_name':'=SUM(1,2)','currency':'CNY','unit_price':'8'},'references':[{'kind':'whole_scope_quote','unit_price':'100','subtotal':'100','currency':'CNY'}]}]},p)
   b=load_workbook(p);self.assertEqual(b['当前报价']['C2'].data_type,'s');self.assertIsNone(b['历史参考']['H2'].value);self.assertEqual(b['历史参考']['I2'].value,100)
if __name__=='__main__':unittest.main()
