import unittest
from valuation_agent.engine import modules
from valuation_agent.io import derive_unit_price

class QuoteRelevanceTests(unittest.TestCase):
 def test_scope_warning_cannot_create_match(self):
  relation=modules()['workbench'].relationship
  history={'item_name':'过道保护','spec':'','module':'撤场拆除清单'}
  for name in ('多段弧形展墙','可调圆形嵌入式LED灯','金属立体字'):
   self.assertIsNone(relation({'name':name},history))
 def test_package_cannot_create_match(self):
  relation=modules()['workbench'].relationship
  self.assertIsNone(relation({'name':'金属立体字'},{'item_name':'无关整包','spec':'布景整包套装'}))
 def test_related_object_still_retained(self):
  relation=modules()['workbench'].relationship
  self.assertIsNotNone(relation({'name':'金属立体字'},{'item_name':'金属立体字','spec':''}))
 def test_price_and_source(self):
  r=derive_unit_price({'quantity':'3','unit':'套','subtotal':'100','unit_price':None,'currency':'CNY'})
  self.assertEqual(r['unit_price'],'33.33');self.assertEqual(r['subtotal'],'100')
  self.assertIn('计算值',r['unit_price_source'])
 def test_existing_zero_and_bundle(self):
  for r in [{'quantity':2,'unit':'套','subtotal':100,'unit_price':0},
            {'quantity':0,'unit':'套','subtotal':100,'unit_price':None},
            {'quantity':None,'unit':'','subtotal':100,'unit_price':None},
            {'quantity':2,'unit':'套','subtotal':100,'unit_price':None,'configuration':'两种尺寸，分别计数'}]:
   before=r['unit_price'];self.assertEqual(derive_unit_price(r)['unit_price'],before)
if __name__=='__main__':unittest.main()

class RemoteGuardTests(unittest.TestCase):
 def test_remote_scope_references_filtered_per_row(self):
  from unittest.mock import patch
  from valuation_agent.cli import remote_compare
  response={'rows':[{'references':[{'item_name':'过道保护','module':'撤场清单','match_kind':'交易或作业范围参考'},{'item_name':'金属立体字','match_kind':'同细类参考'}]}]}
  with patch('valuation_agent.remote.remote_call',return_value=response):
   result=remote_compare({'rows':[{'item_name':'金属立体字'}]},'unused')
  self.assertEqual([r['item_name'] for r in result['rows'][0]['references']],['金属立体字'])

class ProcurementObjectTests(unittest.TestCase):
 def test_wall_is_not_shoelace_or_media(self):
  relation=modules()['workbench'].relationship
  query={'name':'多段弧形展墙','description':'金属烤漆饰面、钢架支撑'}
  for name in ('鞋带制作','造型墙LED服务器','序厅门头主题墙面影片转制'):
   self.assertIsNone(relation(query,{'item_name':name,'spec':'金属喷漆'}))
  self.assertIsNotNone(relation(query,{'item_name':'烤漆铝板造型墙','spec':'金属喷漆'}))
 def test_ring_light_is_not_lightbox(self):
  self.assertIsNone(modules()['workbench'].relationship({'name':'可调圆形嵌入式LED灯'}, {'item_name':'装饰-背面圆环灯箱和'}))
