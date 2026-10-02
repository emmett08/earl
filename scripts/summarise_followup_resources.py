"""Recompute the completed follow-up resource ledger without response text."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output-directory', required=True, type=Path)
    args = parser.parse_args()
    rows = json.loads((args.source / 'rows.json').read_text())
    calls = json.loads((args.source / 'calls.json').read_text())
    metadata = {}
    for block in rows:
        metadata[block['donor_session_id']] = ('common_donor', block['donor_result'])
        for variant in block['variants']:
            metadata[variant['session_id']] = (variant['level'], variant['result'])
    if len(metadata) != 128 or {call['session_id'] for call in calls} != set(metadata):
        raise ValueError('Resource session coverage differs from the frozen allocation')
    groups = {key: {'context': key, 'sessions': 0, 'api_attempts': 0,
                   'input_tokens': 0, 'output_tokens': 0, 'cached_input_tokens': 0,
                   'reasoning_tokens': 0, 'configured_cost_usd': Decimal('0'),
                   'sum_api_attempt_seconds': 0.0, 'sum_session_seconds': 0.0,
                   'sum_context_seconds': 0.0}
              for key in ('common_donor', 'facts', 'eal', 'conventional')}
    for group, session in metadata.values():
        target = groups[group]
        target['sessions'] += 1
        target['sum_session_seconds'] += session['elapsed_seconds']
        target['sum_context_seconds'] += session['context_seconds']
    tolerance = Decimal('0.000000000001')
    for call in calls:
        target = groups[metadata[call['session_id']][0]]
        usage = call['response']['usage']
        target['api_attempts'] += 1
        target['input_tokens'] += usage['input_tokens']
        target['output_tokens'] += usage['output_tokens']
        target['cached_input_tokens'] += usage.get('input_tokens_details', {}).get('cached_tokens', 0)
        target['reasoning_tokens'] += usage.get('output_tokens_details', {}).get('reasoning_tokens', 0)
        estimate = (Decimal(usage['input_tokens']) * Decimal('0.10') +
                    Decimal(usage['output_tokens']) * Decimal('0.40')) / Decimal('1000000')
        if any(abs(estimate - Decimal(str(call[field]))) > tolerance
               for field in ('cost_estimate_usd', 'charged_or_reserved_usd')):
            raise ValueError('Retained cost differs from configured usage arithmetic')
        target['configured_cost_usd'] += estimate
        target['sum_api_attempt_seconds'] += call['elapsed_seconds']
    total = sum(target['configured_cost_usd'] for target in groups.values())
    if total != Decimal('0.0204097'):
        raise ValueError('Unexpected completed-run cost')
    for target in groups.values():
        target['configured_cost_usd'] = str(target['configured_cost_usd'])
        target['total_tokens'] = target['input_tokens'] + target['output_tokens']
    record = {'schema': 'EAL/followup-resource-summary/1',
              'source_calls_sha256': sha(args.source / 'calls.json'),
              'source_rows_sha256': sha(args.source / 'rows.json'),
              'calculator_sha256': sha(Path(__file__)),
              'input_rate_usd_per_million': '0.10', 'output_rate_usd_per_million': '0.40',
              'groups': list(groups.values()), 'total_configured_cost_usd': str(total),
              'budget_usd': '2', 'cost_complete': True,
              'ledger_float_comparison_tolerance_usd': str(tolerance),
              'native_tool_calls': 0, 'host_raw_snapshot_reads': 120,
              'total_collector_calls': 168,
              'interpretation': 'Configured-rate estimates ignore cached-input discounts and are not '
                                'invoices or net adoption costs. Session, attempt and context times '
                                'are sums across concurrent work, not wall-clock runtime. The eight '
                                'common donor costs are not duplicated into recipient-context groups.'}
    with (args.output_directory / 'resource-summary.json').open('x') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
    with (args.output_directory / 'resource-totals.csv').open('x') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(record['groups'][0]))
        writer.writeheader()
        writer.writerows(record['groups'])
    print(json.dumps({'sessions': len(metadata), 'attempts': len(calls), 'configured_cost_usd': str(total)}))


if __name__ == '__main__':
    main()
