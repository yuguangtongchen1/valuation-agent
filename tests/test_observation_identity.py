import unittest
from valuation_agent.engine import modules


class ObservationIdentityTests(unittest.TestCase):
    def test_different_product_or_billing_is_not_a_duplicate(self):
        key = modules()['workbench'].quote_observation_key
        row = dict(project_key='p', item_name='灯具', spec='定制', model='A',
                   brand='甲', unit='米', quantity=2, unit_price=100, subtotal=200,
                   currency='CNY', kind='bom')
        for field, value in [('unit', '套'), ('brand', '乙'), ('quantity', 3),
                             ('currency', 'USD'), ('kind', 'whole_scope_quote'),
                             ('billing_multiplier', 2)]:
            with self.subTest(field=field):
                self.assertNotEqual(key(row), key(dict(row, **{field: value})))
        self.assertNotEqual(key(row, '盖章'), key(row, '未盖章'))
        self.assertNotEqual(key(row), key(dict(row, source_attributes={'monthly_fee_cny': 100})))

    def test_identical_observation_from_another_attachment_collapses(self):
        key = modules()['workbench'].quote_observation_key
        row = dict(project_key='p', item_name='灯具', unit='米', quantity=2,
                   unit_price=100, subtotal=200)
        self.assertEqual(key(row), key(dict(row, source_token='another', source_locator='page2')))


if __name__ == '__main__':
    unittest.main()
