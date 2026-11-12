import json
import tempfile
import unittest
from pathlib import Path
from valuation_agent.io import read_input

class HeaderTests(unittest.TestCase):
    def test_summary_mixed_and_zero(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'quote.xlsx'
            book=openpyxl.Workbook(); sheet=book.active
            sheet.append(['报价分类','明细行数','金额（元）'])
            sheet.append(['图文',3,300])
            sheet.append(['分类','区域／展馆','分项','项目／展项','制作工艺','尺寸数量','厚度参数','单位','数量','综合单价（元）','原表金额（元）'])
            sheet.append(['图文','展厅','导视','入口','立体字','L850*H250mm*2套','15mm',None,None,None,300])
            sheet.append(['图文','展厅','组合','画面','UV','L350*H200mm*17套\nL600*H1350mm*6套',None,None,None,None,700])
            sheet.append(['硬装','展厅','墙体','展墙','进口板',None,None,'项',1,100,0])
            sheet.append(['硬装','展厅','墙体',None,'国产板',None,None,'项',1,80,80])
            book.save(p); result=read_input(p); rows=result['rows']
            self.assertEqual(len(rows),4)
            self.assertEqual(rows[0]['quantity'],'2')
            self.assertEqual(rows[0]['unit'],'套')
            self.assertIn('15mm',rows[0]['spec'])
            self.assertIsNone(rows[1]['quantity'])
            self.assertTrue(rows[1]['configuration'])
            self.assertEqual(float(rows[2]['subtotal']),0)
            self.assertEqual(rows[3]['item_name'],'展墙')
            self.assertIsNone(rows[3]['source_original_fields']['项目／展项'])
            self.assertEqual(len(result['non_item_rows']),2)
    def test_no_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.csv'; p.write_text('项目名称,金额\n某项目,100\n')
            with self.assertRaises(ValueError):read_input(p)
if __name__=='__main__': unittest.main()
