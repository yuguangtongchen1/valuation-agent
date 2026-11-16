import unittest
from valuation_agent.engine import modules
from valuation_agent.server import safe_reference

class DerivedRateProvenance(unittest.TestCase):
    def test_remote_reference_retains_basis_without_private_path(self):
        row = {'kind':'bom_line','unit_price':'1200.00','subtotal':'10800',
               'quantity':'9','unit':'人天','currency':'CNY',
               'unit_price_derivation':{'method':'verified_original_amount_divided_by_billing_quantity',
                   'amount':'10800','quantity':'9','unit':'人天','basis':'原报价，优惠另计',
                   'review':'private/source-review.json'}}
        result = safe_reference(modules()['valuation'].reference(row, 'shared_source'))
        self.assertEqual(result['unit_price_derivation']['amount'], '10800')
        self.assertEqual(result['unit_price_derivation']['basis'], '原报价，优惠另计')
        self.assertNotIn('review', result['unit_price_derivation'])
        self.assertIsNone(result['source_unit_price_original'])
    def test_direct_source_price_does_not_get_derivation(self):
        result = modules()['valuation'].reference({'unit_price':'1200','currency':'CNY'}, None)
        self.assertNotIn('unit_price_derivation', result)

    def test_billing_context_preserves_both_quantity_dimensions(self):
        row = dict(quantity='47', unit='平方米', unit_price='3085', subtotal='145000', currency='CNY',
                   verified_billing_context=dict(physical_quantity='18', physical_unit='片',
                       billing_quantity='47', billing_unit='平方米', pricing_basis='contract_fixed_total',
                       fixed_total_cny='145000', included_services=['木箱费'], review='/private/review.json',
                       comparison_eligible=True))
        result = safe_reference(modules()['valuation'].reference(row, 'scope_pending'))
        context = result['verified_billing_context']
        self.assertEqual((result['quantity'], result['unit']), ('47', '平方米'))
        self.assertEqual(context['physical_quantity'], '18')
        self.assertEqual(context['fixed_total_cny'], '145000')
        self.assertEqual(context['included_services'], ['木箱费'])
        self.assertNotIn('review', context)
        self.assertNotIn('comparison_eligible', context)
