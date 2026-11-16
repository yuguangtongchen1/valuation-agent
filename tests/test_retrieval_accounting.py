import unittest
from pathlib import Path
from valuation_agent.engine import modules


class RetrievalAccountingTests(unittest.TestCase):
    def test_invalid_name_is_not_reported_as_completed_search(self):
        w = modules()['workbench']
        for name in ('', ' ', '墙' * 121):
            with self.subTest(name_length=len(name)), self.assertRaises(ValueError):
                w.lookup(Path('.'), [], {}, {}, {}, {'name': name}, False)

    def test_semantic_rejection_is_counted_without_claiming_no_scan(self):
        w = modules()['workbench']
        trace = []
        rows = [{'line_id': 'hardware', 'record_id': 'r', 'item_name': '交换机',
                 'unit': '台', 'spec': '24口'},
                {'line_id': 'excluded', 'record_id': 'own', 'item_name': '拍摄服务',
                 'unit': '项'}]
        refs = w.priced_references(Path('.'), rows, {}, {}, {},
            {'name': '视频素材拍摄服务', 'unit': '项', 'exclude': 'own'}, trace=trace)
        self.assertEqual(refs, [])
        counts = trace[0]
        self.assertEqual(counts['rows_examined'], 2)
        self.assertEqual(counts['semantic_rejected'], 1)
        self.assertEqual(counts['excluded_or_already_selected'], 1)
        self.assertEqual(counts['semantic_candidates'], 0)
        self.assertEqual(counts['candidates_beyond_return_limit'], 0)
        self.assertEqual(counts['rows_examined'], sum(counts[k] for k in
            ('blocked_price_roles', 'excluded_or_already_selected',
             'semantic_rejected', 'semantic_candidates')))
