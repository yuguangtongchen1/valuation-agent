import unittest
from valuation_agent.retrieval_evaluation import evaluate


class RetrievalEvaluationTests(unittest.TestCase):
    def test_duplicates_and_unknowns_cannot_inflate_quality(self):
        report = evaluate([{'query_id': 'wall', 'relevant_ids': ['a', 'b'],
            'judged_ids': ['a', 'b', 'wrong'], 'forbidden_ids': ['own'],
            'retrieved_ids': ['a', 'a', 'unknown', 'wrong', 'own'], 'elapsed_ms': 12}], 3)
        row = report['per_query'][0]
        self.assertEqual(row['recall_at_k'], .5)
        self.assertEqual(row['confirmed_precision_at_k'], 1/3)
        self.assertEqual(row['unjudged_at_k'], 1)
        self.assertEqual(row['judged_wrong_at_k'], 1)
        self.assertEqual(row['duplicate_results'], 1)
        self.assertEqual(row['forbidden_at_k'], 0)
        self.assertEqual(report['forbidden_anywhere'], 1)

    def test_no_reference_and_empty_queries_are_not_perfect_recall(self):
        report = evaluate([{'query_id': 'missing', 'relevant_ids': [],
                            'retrieved_ids': ['candidate']}])
        self.assertIsNone(report['macro_recall_at_k'])
        self.assertTrue(report['per_query'][0]['empty_relevant_set_with_results'])
        self.assertEqual(report['unjudged_at_k'], 1)
        self.assertIsNone(evaluate([])['macro_confirmed_precision_at_k'])

    def test_invalid_gold_and_timings_fail_explicitly(self):
        base = {'query_id': 'a', 'relevant_ids': ['a'], 'retrieved_ids': []}
        for extra in ({'judged_ids': []}, {'forbidden_ids': ['a']}, {'elapsed_ms': float('nan')}):
            with self.assertRaises(ValueError):
                evaluate([dict(base, **extra)])
        with self.assertRaises(ValueError):
            evaluate([base, base])

    def test_latency_percentile_uses_only_measured_samples(self):
        cases = [{'query_id': str(i), 'relevant_ids': [], 'retrieved_ids': [],
                  'elapsed_ms': i} for i in range(1, 21)]
        report = evaluate(cases)
        self.assertEqual(report['p50_ms'], 10)
        self.assertEqual(report['p95_ms'], 19)

    def test_component_recall_is_not_comparable_price_quality(self):
        report = evaluate([{'query_id': 'ring-light', 'relevant_ids': ['strip'],
            'retrieved_ids': ['strip', 'package'], 'judged_ids': ['strip', 'package'],
            'expected_scopes': {'strip': 'component', 'package': 'package'},
            'displayed_scopes': {'strip': 'comparable'}}])
        self.assertEqual(report['macro_recall_at_k'], 1)
        self.assertEqual(report['scope_overclaims'], 1)
        self.assertEqual(report['scope_missing_at_k'], 1)
        self.assertEqual(report['per_query'][0]['scope_overclaimed_ids'], ['strip'])

    def test_scope_labels_require_explicit_valid_judgment(self):
        base = {'query_id': 'x', 'relevant_ids': [], 'retrieved_ids': ['a']}
        for extra in ({'expected_scopes': {'a': 'component'}},
                      {'displayed_scopes': {'a': 'guessed'}}):
            with self.assertRaises(ValueError):
                evaluate([dict(base, **extra)])
