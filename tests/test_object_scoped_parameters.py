import unittest
from valuation_agent._engine.quote_parameters import parameters, parameter_comparison


class ObjectScopedParametersTests(unittest.TestCase):
    def test_wall_and_letters_do_not_share_height(self):
        result = parameters('墙面范围：1350×3200mm；中文字高32mm；英文大写字高30mm')
        self.assertEqual(set(result), {'墙面范围', '中文字高', '英文大写字高'})
        self.assertEqual(list(result['中文字高']), [32])
        self.assertEqual(list(result['墙面范围']), [(1350, 3200)])

    def test_equivalent_units_and_real_difference(self):
        a = parameters('墙面高度3200mm；中文字高32mm')
        b = parameters('墙面高度320cm；中文字高1.8cm')
        comparison = {r['label']: r for r in parameter_comparison(a, b)}
        self.assertFalse(comparison['墙面高度']['different'])
        self.assertTrue(comparison['中文字高']['different'])

    def test_missing_unit_not_invented(self):
        self.assertEqual(parameters('中文字高32；墙面范围：1350×3200'), {})
        self.assertEqual(list(parameters('中文字高32', 'mm')['中文字高']), [32])

    def test_generic_dimensions_still_work(self):
        result = parameters('直径3500mm；高度300mm；LED 18W')
        self.assertEqual(list(result['直径']), [3500])
        self.assertEqual(list(result['功率']), [18])

    def test_title_and_body_roles_are_distinct(self):
        result = parameters('中文大标题字高250mm；英文副标题字高60mm；中文正文字高30mm')
        self.assertEqual(set(result), {'中文大标题字高', '英文副标题字高', '中文正文字高'})
        self.assertEqual(list(result['中文正文字高']), [30])

    def test_explicit_objects_keep_separate_body_heights(self):
        result = parameters('【对象：入口墙】中文正文字高46mm；【对象：时间墙】中文正文字高35mm')
        self.assertEqual(set(result), {'入口墙 · 中文正文字高', '时间墙 · 中文正文字高'})
        self.assertEqual(list(result['入口墙 · 中文正文字高']), [46])
        self.assertEqual(list(result['时间墙 · 中文正文字高']), [35])

    def test_object_parameters_compare_equivalent_units(self):
        current = parameters('【对象：入口墙】中文正文字高46mm')
        history = parameters('【对象：入口墙】中文正文字高4.6cm；【对象：时间墙】中文小文字字高35mm')
        result = {r['label']: r for r in parameter_comparison(current, history)}
        self.assertFalse(result['入口墙 · 中文正文字高']['different'])
        self.assertEqual(result['时间墙 · 中文小文字字高']['current'], '')

    def test_unscoped_wall_and_missing_units_survive_object_sections(self):
        result = parameters('墙面范围：6000×3000mm；【对象：入口墙】中文字高32；【对象：时间墙】中文字高35mm')
        self.assertEqual(set(result), {'墙面范围', '时间墙 · 中文字高'})

    def test_english_title_not_collapsed_into_generic_height(self):
        result = parameters('中文大标题字高11cm；英文大标题字高8.5cm；中文小文字字高5.1cm')
        self.assertEqual(set(result), {'中文大标题字高', '英文大标题字高', '中文小文字字高'})
        self.assertEqual(list(result['英文大标题字高']), [85])
        self.assertEqual(list(result['中文小文字字高']), [51])

    def test_english_lowercase_title_and_body_are_separate(self):
        current = parameters('中文大标题字高430mm；英文大标题小写字高220mm；中文正文字高170mm；英文正文字高76mm')
        history = parameters('中文大标题字高43cm；英文大标题小写字高22cm；中文正文字高17cm；英文正文字高8cm')
        self.assertEqual(set(current), {'中文大标题字高', '英文大标题小写字高', '中文正文字高', '英文正文字高'})
        compared = {r['label']: r for r in parameter_comparison(current, history)}
        self.assertFalse(compared['英文大标题小写字高']['different'])
        self.assertTrue(compared['英文正文字高']['different'])
