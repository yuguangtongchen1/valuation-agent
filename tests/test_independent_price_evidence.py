"""Repeated ledger associations must not inflate independent price evidence."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'valuation_agent' / '_engine'))
from valuation import count_estimate_groups

def quote(project, source, price='100', reason=None):
    return ({'project_key':project, 'source_token':source, 'unit_price':price,
             'item_name':'施工图绘制', 'unit':'项', 'currency':'CNY'}, reason)

class IndependentEvidence(unittest.TestCase):
    def test_shared_original_is_one_sample_even_with_different_projects(self):
        self.assertEqual(count_estimate_groups([quote('a','x'),quote('b','x')]),0)
    def test_distinct_originals_and_projects_count(self):
        self.assertEqual(count_estimate_groups([quote('a','x'),quote('b','y')]),1)
    def test_distinct_originals_in_same_project_do_not_count(self):
        self.assertEqual(count_estimate_groups([quote('a','x'),quote('a','y')]),0)
    def test_missing_source_and_rejected_price_do_not_count(self):
        for other in (quote('b',None), quote('b','y',reason='pending'),quote('b','y',price=None)):
            self.assertEqual(count_estimate_groups([quote('a','x'),other]),0)
    def test_conflicting_project_prices_are_not_resolved_by_dedup(self):
        self.assertEqual(count_estimate_groups([quote('a','x'),quote('a','y','200'),quote('b','z')]),0)
    def test_shared_source_does_not_hide_additional_independent_evidence(self):
        self.assertEqual(count_estimate_groups([quote('a','x'),quote('b','x'),quote('b','y')]),1)

if __name__ == '__main__': unittest.main()
