import unittest
from valuation_agent.engine import modules

class ExhibitionKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.relation = modules()['workbench'].relationship
    def test_same_object_different_names(self):
        pairs = [('吊顶','天花'),('轻钢龙骨隔墙','双面石膏板隔断'),('展柜','展示柜'),
                 ('旋转展台','电动转台'),('播控主机','媒体服务器'),('轨道射灯','导轨式射灯'),
                 ('木饰面','木皮饰面'),('展板','图文展板'),('灯控网线','网线'),('定向音响','定向扬声器'),('丝印图文','丝网印制作')]
        for current, old in pairs:
            with self.subTest(current=current):
                self.assertIsNotNone(self.relation({'name':current},{'item_name':old}))
    def test_distinct_deliverables(self):
        pairs = [('吊挂钢结构','LED钢结构'),('中控系统','播放服务器'),('多功能展陈系统','弧形展墙'),
                 ('轨道射灯','轨道接头'),('展柜','展柜灯带'),('定向扬声器','普通音箱'),
                 ('导视立牌','消防指示牌'),('DMX信号线','六类网线'),('投影机','投影机吊架')]
        for current, old in pairs:
            with self.subTest(current=current):
                self.assertIsNone(self.relation({'name':current},{'item_name':old}))
    def test_material_aliases_and_conflicts(self):
        r=self.relation({'name':'图文展板','description':'PVC发泡板UV打印'},
                        {'item_name':'展板','description':'雪弗板UV打印'})
        self.assertFalse(any('材质不同' in d for d in r[2]))
        r=self.relation({'name':'GRG造型吊顶'},{'item_name':'玻璃钢造型吊顶'})
        self.assertTrue(any('材质不同' in d for d in r[2]))
        r=self.relation({'name':'金属立体字'},{'item_name':'泡沫立体字，喷漆'})
        self.assertTrue(any('材质不同' in d for d in r[2]))
    def test_components_are_not_whole_prices(self):
        for current, old in [('灯箱画面','软膜灯箱'),('灯带','线性灯具')]:
            r=self.relation({'name':current},{'item_name':old})
            self.assertIn('整包',r[1]);self.assertTrue(any('不可直接比较' in d for d in r[2]))
    def test_model_context_and_digital_context(self):
        self.assertIsNone(self.relation({'name':'模型制作','description':'数字三维模型绑定'},
                                       {'item_name':'沙盘模型制作','description':'实物3D打印'}))
        self.assertIsNone(self.relation({'name':'弧形展墙内的多功能展陈系统'}, {'item_name':'造型展墙'}))

    def test_location_and_design_do_not_override_deliverable(self):
        for old in ['天花顶部logo','天花两侧双面霓彩屏','原吊顶修复','水管拆装天花穿墙补洞修补等']:
            self.assertIsNone(self.relation({'name':'天花'},{'item_name':old}))
        self.assertIsNone(self.relation({'name':'施工图深化设计（酒瓶造型展墙）'}, {'item_name':'烤漆铝板造型墙'}))
        self.assertIsNone(self.relation({'name':'施工图深化'}, {'item_name':'体验流程深化设计'}))
        self.assertIsNotNone(self.relation({'name':'施工图深化'}, {'item_name':'施工图设计'}))
        self.assertIsNone(self.relation({'name':'施工图深化'}, {'item_name':'定制图文展板'}))
        self.assertIsNone(self.relation({'name':'天花'}, {'item_name':'现有石膏板天花重新刷漆'}))
        self.assertIsNone(self.relation({'name':'丝网印制作'}, {'item_name':'修改丝网印'}))
        self.assertIsNone(self.relation({'name':'型材与LED灯带'}, {'item_name':'LED灯带'}))
        self.assertIsNone(self.relation({'name':'标题金属立体字及正文丝网印'}, {'item_name':'金属立体字'}))
        self.assertIsNone(self.relation({'name':'多段弧形展墙','description':'顶面造型顶及橱窗展台'}, {'item_name':'造型展墙'}))

    def test_equal_dimension_does_not_hide_different_material(self):
        r=self.relation({'name':'GRG造型吊顶','spec':'厚度20mm'},
                        {'item_name':'玻璃钢造型吊顶','spec':'厚度20mm'})
        self.assertNotIn('同规格',r[1]);self.assertNotIn('参数一致',r[1])
        self.assertIn('有差异',r[1])

    def test_appearance_target_is_not_material_identity(self):
        from exhibition_knowledge import material_identities
        m=material_identities('国产亚克力板（效果对标杜邦可丽耐板）')
        self.assertEqual(m,{'亚克力'})
        self.assertNotIn('铜材',material_identities('铜质纹理的树脂构件'))

    def test_model_components_require_source_span(self):
        w=modules()['workbench']
        row={'name':'组合展具','description':'钢架，玻璃橱窗，铝型材灯',
             'comparison_components':[{'name':'展示柜','source_text':'玻璃橱窗'},
                                      {'name':'投影机','source_text':'不存在的投影机'},
                                      {'name':'灯箱','source_text':''}]}
        self.assertEqual(w.quoted_components(row),[('展示柜',(None,None))])

    def test_excluded_components_are_not_supplied(self):
        w=modules()['workbench']
        row={'name':'组合展具','description':'钢架，不含玻璃橱窗',
             'comparison_components':[{'name':'展示柜','source_text':'玻璃橱窗'}]}
        self.assertEqual(w.quoted_components(row),[])

    def test_component_retrieval_preserves_price_scope_and_material(self):
        import json, tempfile
        from pathlib import Path
        from valuation_agent.service import compare
        history={'rows':[{'item_name':'泡沫立体字，喷漆','quantity':'1','unit':'个',
                           'unit_price':'30','subtotal':'30','currency':'CNY'},
                         {'item_name':'Logo立体字体','description':'定制mini无边发光字',
                          'quantity':'1','unit':'个','unit_price':'90','subtotal':'90','currency':'CNY'}]}
        quote={'rows':[{'item_name':'标题金属立体字及正文丝网印',
                        'description':'标题金属立体字；正文丝网印',
                        'comparison_components':[{'name':'金属立体字','source_text':'标题金属立体字'}],
                        'currency':'CNY'}]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'history.json';path.write_text(json.dumps(history,ensure_ascii=False))
            refs=compare(quote,history=path)['rows'][0]['references']
        self.assertEqual(len(refs),1)
        self.assertEqual(refs[0]['comparison_role'],'component')
        self.assertFalse(refs[0]['price_comparison_eligible'])
        self.assertTrue(any('材质不同' in d for d in refs[0]['differences']))

    def test_context_and_uv_graphic_aliases(self):
        self.assertIsNotNone(self.relation({'name':'发光字'}, {'item_name':'Logo立体字体','description':'定制mini无边发光字'}))
        self.assertIsNone(self.relation({'name':'发光字'}, {'item_name':'立体字','description':'不发光'}))
        self.assertIsNotNone(self.relation({'name':'亚克力UV画面'}, {'item_name':'亚克力UV','spec':'2mm亚克力UV印刷'}))
        self.assertIsNone(self.relation({'name':'亚克力UV画面'}, {'item_name':'亚克力雕刻城市剪影造型'}))
        self.assertIsNotNone(self.relation({'name':'产品运输费'}, {'item_name':'物料运输'}))

    def test_price_sensitive_parameters(self):
        from quote_parameters import parameters, parameter_comparison
        a=parameters('20w 3000k 光束角15度 cri90 dali cat6')
        b=parameters('20w 3000k 光束角36度 cri80 dmx512 六类线')
        diff={p['label']:p['different'] for p in parameter_comparison(a,b)}
        self.assertTrue(diff['光束角']);self.assertTrue(diff['显色指数'])
        self.assertTrue(diff['调光协议']);self.assertFalse(diff['网络线类别'])
        self.assertNotIn('光束角',parameters('角钢40mm 风格30度倾斜'))
        self.assertEqual(parameters('cri>=90'),parameters('ra≥90'))
        self.assertNotEqual(parameters('cri≥90'),parameters('cri90'))


    def test_missing_and_different_units_are_not_direct_prices(self):
        import json, tempfile
        from pathlib import Path
        from valuation_agent.service import compare
        history={'rows':[{'item_name':'PVC地胶','quantity':'1','unit':'平方米',
                         'unit_price':'30','subtotal':'30','currency':'CNY'}]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'history.json'
            path.write_text(json.dumps(history,ensure_ascii=False))
            for unit in (None, '项'):
                with self.subTest(unit=unit):
                    quote={'rows':[{'item_name':'PVC地胶','unit':unit,'currency':'CNY'}]}
                    refs=compare(quote,history=path)['rows'][0]['references']
                    self.assertTrue(refs)
                    self.assertTrue(all(not r['price_comparison_eligible'] for r in refs))
                    self.assertTrue(any('计价单位' in d for r in refs for d in r['differences']))
