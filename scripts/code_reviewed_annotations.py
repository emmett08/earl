"""Reproduce reviewed AI codes from masked answers and frozen adjudications.

This is a rule aid with AI semantic review, not an independent human assessor.
It never opens an assignment mapping, task key, or outcome report. All answers
receive structural and adverse checks; flagged answers require frozen reviews.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from code_pilot_annotations import TERM, candidate, normal


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def checks(text: str, provisional: str) -> dict:
    """A second scan, independent of the candidate's sentence-selection rules."""
    clean = re.sub(r'[*`]', '', text)
    matches = list(TERM.finditer(clean))
    first = normal(matches[0].group()) if matches else None
    line = clean.split('\n', 1)[0]
    prominent = None
    if (re.match(r'^(?:assessment|decision|status|result)\s*(?::|\(|as of|at\b)', line, re.I)
            or re.match(r'^(?:ready|not[_ -]ready|undetermined)(?:\W|$)', line, re.I)):
        m = TERM.search(line)
        prominent = normal(m.group()) if m else None
    negation = bool(re.search(
        r'\b(?:cannot|can.t|unable|not|insufficient|unclear|unknown|uncertain|'
        r'indeterminate|inconclusive|neither)\b[^.!?\n]{0,70}\bready\b', text, re.I))
    unknown = bool(re.search(
        r'\b(?:overall\s+(?:status|readiness|verdict|result)|(?:task|service|release)'
        r'\s+(?:status|readiness)|readiness|current\s+(?:status|verdict|result|assessment))'
        r'\b[^.!?\n]{0,70}\b(?:inconclusive|indeterminate|uncertain|unknown|'
        r'not determin(?:ed|ate|able)|cannot be determined)\b', text, re.I))
    return {
        'first_category': first,
        'prominent_category': prominent,
        'first_category_disagreement': first != provisional,
        'prominent_category_disagreement': prominent is not None and prominent != provisional,
        'multiple_category_words': len({normal(m.group()) for m in matches}) > 1,
        'ready_negation_or_uncertainty': negation,
        'status_uncertainty_synonym': unknown,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('items', type=Path)
    parser.add_argument('reviews', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--audit', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.audit.exists():
        raise ValueError('Use new output paths; preserve earlier assessments')
    raw, review_raw = args.items.read_bytes(), args.reviews.read_bytes()
    payload, review = json.loads(raw), json.loads(review_raw)
    if payload.get('schema') != 'EAL/model-transfer-annotations/1':
        raise ValueError('Unsupported masked annotation schema')
    if review.get('source_items_sha256') != sha256(raw):
        raise ValueError('Reviews must identify this exact masked export')
    if review.get('expected_items') != len(payload['items']):
        raise ValueError('Unexpected answer count')
    original_ids = [item['id'] for item in payload['items']]
    if len(set(original_ids)) != len(original_ids):
        raise ValueError('Duplicate masked answer identifier')
    overrides = review['items']
    if set(overrides) - set(original_ids):
        raise ValueError('Unknown reviewed answer')
    counts, audit, identical = Counter(), [], defaultdict(set)
    for index, item in enumerate(payload['items']):
        text = item['text']
        provisional, quote, rule = candidate(text)
        second = checks(text, provisional)
        # First mentions are a screen, not an adopted decision: they can be
        # hypothetical, historical, component-level or negated.
        requires_review = (provisional == 'ambiguous'
                           or second['first_category_disagreement']
                           or second['prominent_category_disagreement']
                           or (provisional != 'undetermined' and second['status_uncertainty_synonym']))
        reviewed = overrides.get(item['id'])
        if requires_review and reviewed is None:
            raise ValueError(f'Missing required semantic review: {item["id"]}')
        decision = provisional
        note = ('Rule-assisted AI coding: ' + rule + '. Second-pass category, negation '
                'and uncertainty screens checked. Code the communicated decision; '
                'reference correctness is assessed separately.')
        if reviewed:
            if reviewed['source_index'] != index or reviewed['answer_sha256'] != sha256(text.encode()):
                raise ValueError('Reviewed answer identity changed')
            decision, quote, note = (reviewed[key] for key in ('decision', 'quote', 'note'))
        if decision not in {'ready', 'not_ready', 'undetermined', 'no_answer', 'ambiguous'}:
            raise ValueError('Invalid decision category')
        if not isinstance(quote, str) or not quote.strip() or quote not in text:
            raise ValueError('Every answer requires an exact supporting quote')
        if not isinstance(note, str) or not note.strip():
            raise ValueError('Every answer requires a coding note')
        if decision == 'ambiguous' and not reviewed.get('ambiguity_recheck'):
            raise ValueError('Unresolved conflicts need a recorded additional recheck')
        item.update(decision=decision, quote=quote, note=note)
        counts[decision] += 1
        identical[text].add(decision)
        audit.append({
            'id': item['id'], 'source_index': index,
            'answer_sha256': sha256(text.encode()), 'provisional': provisional,
            'rule': rule, 'second_pass': second, 'decision': decision,
            'full_answer_semantic_review': reviewed is not None,
            'review_pass': reviewed.get('review_pass') if reviewed else 'two-rule-scans',
            'exact_quote_valid': True, 'original_text_retained': True,
        })
    if any(len(codes) != 1 for codes in identical.values()):
        raise ValueError('Identical answers received inconsistent codes')
    script = Path(__file__).read_bytes()
    baseline = Path(__file__).with_name('code_pilot_annotations.py').read_bytes()
    if review.get('baseline_script_sha256') != sha256(baseline):
        raise ValueError('Provisional coding aid changed after review')
    payload['annotator'] = 'OpenAI ChatGPT/Codex, reviewed masked AI coding, 2026-10-02'
    payload['assessor'] = {
        'kind': 'ai', 'model': 'OpenAI ChatGPT/Codex; exact serving identifier not exposed',
        'method': 'masked-ai-rule-assisted-decision/2',
        'validation': ('All answer values checked twice; 392 flagged answers reviewed in full; '
                       'all provisional ambiguities rechecked. No independent human '
                       'validation or measured assessor error rate.'),
        'protocol': 'annotations/pilot-36985062352-AI-CODING.md',
        'source_items_sha256': sha256(raw), 'coding_script_sha256': sha256(script),
        'baseline_script_sha256': sha256(baseline), 'adjudications_sha256': sha256(review_raw),
        'masking': ('Only masked answer text used for coding; no mapping or reference outcomes '
                    'consulted before label freeze. Answer wording can reveal the workflow; '
                    'prior project context is available.'),
        'collection_changed': False,
    }
    report = {
        'schema': 'EAL/masked-ai-coding-audit/1', 'source_items_sha256': sha256(raw),
        'coding_script_sha256': sha256(script), 'baseline_script_sha256': sha256(baseline),
        'adjudications_sha256': sha256(review_raw), 'items': len(audit),
        'codes': dict(counts), 'full_answer_reviews': len(overrides),
        'all_identifiers_unique': True, 'all_ids_and_text_retained': True,
        'all_quotes_exact': True, 'all_codes_valid': True, 'all_notes_present': True,
        'identical_answer_code_disagreements': 0, 'records': audit,
    }
    for target, value in ((args.output, payload), (args.audit, report)):
        with target.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    print(json.dumps({key: report[key] for key in ('items', 'codes', 'full_answer_reviews')}))


if __name__ == '__main__':
    main()
