import unittest
from valuation_agent.engine import modules

class ClassificationPathTests(unittest.TestCase):
    def test_parts_have_own_paths_and_are_not_whole_prices(self):
        m = modules()
        for part, whole in [('LED显示屏模组', 'LED显示屏'), ('投影机吊架', '投影机')]:
            with self.subTest(part=part):
                path = m['classification'].classify_row({'item_name': part})
                self.assertTrue(path)
                self.assertNotEqual(path, m['classification'].classify_row({'item_name': whole}))
                self.assertIsNone(m['workbench'].relationship({'name': part}, {'item_name': whole}))

    def test_generic_module_does_not_imply_led(self):
        modules()
        from exhibition_knowledge import concept
        self.assertIsNone(concept('模组'))

    def test_value_changes_do_not_override_core_function(self):
        classify = modules()['classification'].classify_row
        base = {'item_name': '旋转平台', 'spec': '钢结构，电机驱动，铜质饰面'}
        self.assertEqual(classify(dict(base, subtotal=100)), classify(dict(base, subtotal=100000)))
        self.assertEqual(classify(base), classify({'item_name': '电动转台', 'spec': '钢结构'}))
        self.assertNotEqual(classify(base), classify({'item_name': '地台', 'spec': '钢木承重基层'}))

    def test_digital_delivery_is_not_playback_hardware(self):
        m = modules()
        a = {'item_name': '数字内容制作', 'description': '三维动画影片'}
        b = {'item_name': '播控服务器', 'description': '用于三维动画影片播放'}
        self.assertNotEqual(m['classification'].classify_row(a), m['classification'].classify_row(b))
        self.assertIsNone(m['workbench'].relationship({'name': a['item_name'], 'description': a['description']}, b))
