import copy
import random
import unittest
from valuation_agent.source_identity import identities, exclude_current_sources


def baseline(rows, document):
    own = identities(document)
    for row in document.get('rows', []):
        own.update(identities(row))
    while True:
        expanded = set(own)
        for row in rows:
            ids = identities(row)
            if ids & own:
                expanded.update(ids)
        if expanded == own:
            break
        own = expanded
    return [r for r in rows if not identities(r) & own
            and r.get('is_current_version') is not False]


class SourceGraphTests(unittest.TestCase):
    def test_random_graph_equivalence_and_no_mutation(self):
        rng = random.Random(42)
        for _ in range(100):
            rows = []
            for i in range(80):
                row = {'name': str(i)}
                for field in ('source_token', 'quotation_family_id', 'record_id'):
                    if rng.random() < .65:
                        row[field] = str(rng.randrange(40))
                row['is_current_version'] = rng.choice([True, False, None])
                rows.append(row)
            doc = {'rows': [{'source_token': str(rng.randrange(40))}]}
            saved = copy.deepcopy((rows, doc))
            self.assertEqual(exclude_current_sources(rows, doc), baseline(rows, doc))
            self.assertEqual((rows, doc), saved)

    def test_inactive_bridge_and_reverse_chain(self):
        rows = [{'source_token': str(i), 'source_url': str(i+1),
                 'is_current_version': i != 250} for i in reversed(range(500))]
        unrelated = {'name': 'same name', 'source_token': 'unrelated'}
        rows += [unrelated, {'name': 'no source'}]
        self.assertEqual(exclude_current_sources(rows, {'source_token': '0'}), rows[-2:])

    def test_empty_source_does_not_exclude_unrelated(self):
        rows = [{'name': 'same'}, {'name': 'same', 'is_current_version': False}]
        self.assertEqual(exclude_current_sources(rows, {}), rows[:1])

if __name__ == '__main__':
    unittest.main()
