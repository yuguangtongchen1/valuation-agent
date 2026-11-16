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

    def test_pending_price_scope_is_visible_but_never_directly_comparable(self):
        from unittest.mock import patch
        w = modules()['workbench']
        row = {'kind': 'bom_line', 'record_status': 'line_fields_verified_price_scope_pending',
               'source_fields_reviewed': True, 'record_id': 'record', 'line_id': 'line',
               'source_token': 'source', 'source_locator': 'row 1',
               'item_name': '施工图绘制', 'unit': '项', 'quantity': 1,
               'unit_price': 1000, 'subtotal': 1000, 'currency': 'CNY'}
        ledger = {'record': {'contract_name': '设计合同', 'sheet': '2025', 'row': 1,
                             'contract_link': '设计合同.docx'}}
        query = {'name': '施工图绘制', 'unit': '项', 'currency': 'CNY'}
        with patch.object(w, 'rejection', return_value=None), patch.object(w, 'reference', side_effect=lambda r, e: dict(r)):
            refs = w.priced_references(Path('.'), [row], ledger, {}, {}, query)
        self.assertEqual(len(refs), 1)
        self.assertFalse(refs[0]['price_comparison_eligible'])
        self.assertEqual(refs[0]['source_review_kind'], 'line_fields_checked')

    def test_zero_quantity_quote_keeps_price_with_explicit_status(self):
        from unittest.mock import patch
        w = modules()['workbench']
        row = {'kind': 'bom_line', 'record_status': 'line_fields_verified_price_scope_pending',
               'record_id': 'record', 'line_id': 'line', 'source_token': 'source',
               'source_locator': 'row 1', 'item_name': '施工图绘制', 'unit': '项',
               'quantity': '0.00', 'unit_price': 10000, 'subtotal': 0, 'currency': 'CNY'}
        ledger = {'record': {'contract_name': '设计合同', 'sheet': '2025', 'row': 1,
                             'contract_link': '设计合同.docx'}}
        with patch.object(w, 'rejection', return_value=None), patch.object(w, 'reference', side_effect=lambda r, e: dict(r)):
            refs = w.priced_references(Path('.'), [row], ledger, {}, {}, {'name': '施工图绘制', 'unit': '项', 'currency': 'CNY'})
        self.assertEqual(len(refs), 1)
        self.assertIn('零数量报价', refs[0]['match_kind'])
        self.assertEqual(refs[0]['unit_price'], 10000)
        self.assertFalse(refs[0]['price_comparison_eligible'])

    def test_structural_component_aliases_keep_scope_boundaries(self):
        from unittest.mock import patch
        w = modules()['workbench']
        def candidate(name, **extra):
            return dict(kind='bom_line', record_status='line_fields_verified_price_scope_pending',
                        record_id='record', line_id=name, source_token='source', source_locator=name,
                        item_name=name, unit='项', quantity=1, unit_price=1000, subtotal=1000,
                        currency='CNY', **extra)
        rows = [candidate('钢结构'), candidate('钢架'), candidate('钢架结构'),
                candidate('大屏钢结构'), candidate('钢结构拆除'), candidate('钢结构计算费')]
        ledger = {'record': {'contract_name': '结构合同', 'sheet': '2025', 'row': 1,
                             'contract_link': '结构合同.docx'}}
        with patch.object(w, 'rejection', return_value=None), patch.object(w, 'reference', side_effect=lambda r, e: dict(r)):
            refs = w.priced_references(Path('.'), rows, ledger, {}, {},
                       {'name':'钢结构框架', 'currency':'CNY'}, component=('钢结构框架',(None,None)))
        self.assertTrue(refs)
        self.assertIn(refs[0]['item_name'], ('钢结构','钢架','钢架结构'))
        self.assertFalse(refs[0]['price_comparison_eligible'])
        for name in ('大屏钢结构','钢结构拆除','钢结构计算费'):
            with patch.object(w, 'rejection', return_value=None), patch.object(w, 'reference', side_effect=lambda r,e:dict(r)):
                refs = w.priced_references(Path('.'), [candidate(name)], ledger, {}, {},
                           {'name':'钢结构框架', 'currency':'CNY'}, component=('钢结构框架',(None,None)))
            self.assertEqual(refs, [], name)

    def test_real_gateway_component_lookup_excludes_source_family(self):
        """Exercise the real dispatch, pool, classification and component lookup."""
        import tempfile
        from valuation_agent.server import Gateway
        def row(key, **identity):
            return dict(kind='bom_line', source_fields_reviewed=True,
                        record_status='line_fields_verified_price_scope_pending',
                        record_id=key, line_id=key, source_token=key,
                        item_name='钢结构', spec='定制', quantity=1, unit='项',
                        unit_price=1000, subtotal=1000, currency='CNY',
                        project_key=key, source_locator='报价表第1行', **identity)
        rows = [row('own', quotation_family_id='family-a'),
                row('old', quotation_family_id='family-a'),
                row('inactive', is_current_version=False), row('independent')]
        ledger = {r['record_id']: {'sheet':'2025', 'row':1, 'contract_name':'结构合同',
                   'contract_link':'结构合同.pdf'} for r in rows}
        quote = {'item_name':'旋转平台及装置', 'description':'内部钢结构框架',
                 'quantity':1, 'unit':'项', 'subtotal':55120,
                 'comparison_components':[{'name':'钢结构框架','source_text':'内部钢结构框架'}]}
        with tempfile.TemporaryDirectory() as directory:
            loaded = (modules(), Path(directory), rows, ledger, {}, {}, None, {})
            app = Gateway(directory, Path(directory)/'unused', loader=lambda **kw:loaded)
            try:
                result = app.dispatch('compare', {'document': {
                    'source_url':'https://tenant.feishu.cn/file/own?from=from_copylink',
                    'rows':[quote]}})
            finally:
                app.executor.shutdown(wait=True)
        refs = result['rows'][0]['references']
        self.assertEqual([r['record_id'] for r in refs], ['independent'])
        self.assertEqual(refs[0]['comparison_role'], 'component')
        self.assertFalse(refs[0]['price_comparison_eligible'])
        self.assertEqual(result['retrieval_corpus']['same_source_rows'], 2)
        self.assertEqual(result['retrieval_corpus']['other_inactive_version_rows'], 1)
