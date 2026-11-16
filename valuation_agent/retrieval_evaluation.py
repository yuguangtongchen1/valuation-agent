"""Offline quality metrics over independently labelled retrieval results.

IDs must identify independent historical observations, not UI cards. Unjudged
results are reported separately and are never silently counted as correct.
"""
import math


def evaluate(cases, k=5):
    """Return per-query and macro metrics; no corpus or network access needed.

    Each case has query_id, relevant_ids, retrieved_ids, optionally judged_ids
    (defaults to relevant_ids), forbidden_ids, and elapsed_ms.
    """
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError('k must be a positive integer')
    results, seen_queries, latencies = [], set(), []
    for case in cases:
        query_id = case['query_id']
        if not query_id or query_id in seen_queries:
            raise ValueError('query_id must be nonempty and unique')
        seen_queries.add(query_id)
        relevant = set(case['relevant_ids'])
        judged = set(case.get('judged_ids', relevant))
        forbidden = set(case.get('forbidden_ids', []))
        if not relevant <= judged or relevant & forbidden:
            raise ValueError('inconsistent relevance judgments')
        raw = list(case['retrieved_ids'])
        unique = list(dict.fromkeys(raw))
        top = unique[:k]
        hits = len(relevant.intersection(top))
        elapsed = case.get('elapsed_ms')
        if elapsed is not None:
            if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError('elapsed_ms must be finite and nonnegative')
            latencies.append(elapsed)
        results.append({
            'query_id': query_id, 'returned_at_k': len(top),
            'confirmed_hits_at_k': hits,
            'recall_at_k': hits / len(relevant) if relevant else None,
            'confirmed_precision_at_k': hits / len(top) if top else None,
            'unjudged_at_k': len(set(top) - judged - forbidden),
            'judged_wrong_at_k': len((set(top) & judged) - relevant),
            'forbidden_at_k': len(set(top) & forbidden),
            'forbidden_anywhere': len(set(raw) & forbidden),
            'duplicate_results': len(raw) - len(unique),
            'empty_relevant_set_with_results': not relevant and bool(top),
        })
    def mean(field):
        values = [r[field] for r in results if r[field] is not None]
        return sum(values) / len(values) if values else None
    def percentile(p):
        values = sorted(latencies)
        return values[max(0, math.ceil(p * len(values)) - 1)] if values else None
    return {'k': k, 'queries': len(results), 'per_query': results,
            'macro_recall_at_k': mean('recall_at_k'),
            'macro_confirmed_precision_at_k': mean('confirmed_precision_at_k'),
            'unjudged_at_k': sum(r['unjudged_at_k'] for r in results),
            'forbidden_anywhere': sum(r['forbidden_anywhere'] for r in results),
            'duplicate_results': sum(r['duplicate_results'] for r in results),
            'latency_samples': len(latencies), 'p50_ms': percentile(.5),
            'p95_ms': percentile(.95)}


def main():
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases', type=Path, help='JSON list of independently labelled cases')
    parser.add_argument('--k', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(json.loads(args.cases.read_text(encoding='utf-8')), args.k)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
