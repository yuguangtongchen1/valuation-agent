import unittest
from pathlib import Path
from valuation_agent.engine import modules

class ExperimentRegressions(unittest.TestCase):
    def test_parent_design_is_not_specific_deliverable(self):
        w=modules()['workbench']
        r=w.relationship({'name':'施工图深化设计','unit':'项'}, {'item_name':'深化设计','unit':'项','description':'展具深化、施工图节点、选材、现场设计指导'})
        self.assertIsNotNone(r)
        self.assertIn('上位服务范围',r[1])
    def test_light_component_requires_source_evidence(self):
        w=modules()['workbench']
        q={'name':'定制圆环LED灯','description':'钢构铜饰面，内嵌4段圆环LED灯',
           'comparison_components':[{'name':'LED灯','source_text':'圆环LED灯'}]}
        self.assertIn(('LED灯',(None,None)),w.quoted_components(q))
        q['description']='钢构铜饰面，不含圆环LED灯'
        self.assertNotIn(('LED灯',(None,None)),w.quoted_components(q))
    def test_service_components_survive_input_without_allocating_price(self):
        import json
        import tempfile
        from valuation_agent.io import read_input
        row = {'item_name': '安装运输综合服务', 'description': '测试、调试、运维、安装、运输等',
               'quantity': 1, 'unit': '项', 'subtotal': 10600, 'currency': 'CNY',
               'comparison_components': [{'name': '安装调试', 'source_text': '测试、调试、运维、安装、运输等'},
                                         {'name': '运输', 'source_text': '运输等'}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'quote.json'
            path.write_text(json.dumps({'rows': [row]}))
            parsed = read_input(path)['rows'][0]
        self.assertEqual(parsed['comparison_components'], row['comparison_components'])
        parts = modules()['workbench'].quoted_components({**parsed, 'name': parsed['item_name']})
        self.assertEqual(dict(parts), {'安装调试': (None, None), '运输': (None, None)})
        self.assertTrue(all('unit_price' not in part for part in parsed['comparison_components']))

    def test_excluded_service_is_not_a_package_component(self):
        w = modules()['workbench']
        for text in ('不含运输', '运输另计', '甲方提供运输'):
            q = {'name': '安装综合服务', 'description': text,
                 'comparison_components': [{'name': '运输', 'source_text': '运输'}]}
            self.assertNotIn(('运输', (None, None)), w.quoted_components(q))

    def test_whole_ring_is_not_strip(self):
        w=modules()['workbench']
        self.assertIsNone(w.relationship({'name':'可调圆形嵌入式LED灯'}, {'item_name':'LED灯带','unit':'米'}))
    def test_suffix_dimension_axes_are_not_watts(self):
        from valuation_agent._engine.quote_parameters import parameters
        p=parameters('3000L×1800W')
        self.assertNotIn('功率',p)
        self.assertNotIn('宽',p)  # No invented length unit.
        p=parameters('3000L×1800W mm；LED 18W')
        self.assertEqual(list(p['宽']),[1800])
        self.assertEqual(list(p['功率']),[18])
        self.assertEqual(list(parameters('1.2kW')['功率']),[1200])
    def test_share_url_excludes_token_and_version_family(self):
        from valuation_agent.source_identity import exclude_current_sources
        history=[{'source_token':'Abc123FileToken','quotation_family_id':'revision-a'},
                 {'source_token':'OlderToken','quotation_family_id':'revision-a'},
                 {'source_token':'IndependentSupplier','quotation_family_id':'revision-b'}]
        kept=exclude_current_sources(history,{'source_url':'https://tenant.feishu.cn/file/Abc123FileToken?from=from_copylink','rows':[]})
        self.assertEqual([r['source_token'] for r in kept],['IndependentSupplier'])
        # A lookalike host must not establish a trusted token identity.
        kept=exclude_current_sources(history,{'source_url':'https://feishu.cn.attacker.example/file/Abc123FileToken'})
        self.assertEqual(len(kept),3)

    def test_geometry_is_not_automatically_a_screen(self):
        from valuation_agent._engine.quote_parameters import parameters
        for text in ('弧形展墙，预留LED灯带', '超宽玻璃橱窗', '多楼层钢结构', '弧形展墙；另配显示屏'):
            self.assertNotIn('屏幕形态', parameters(text))
        self.assertIn('曲面/弧形屏', parameters('弧形LED显示屏')['屏幕形态'])
        self.assertIn('超宽屏', parameters('超宽拼接屏')['屏幕形态'])
