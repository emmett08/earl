"""Conservative, reviewable coding aid for the masked September 2026 pilot.

This is an AI-authored rule aid with explicit per-answer AI adjudications, not a
validated human assessor or a general-purpose semantic classifier. It reads only
the masked items and never consults assignment mappings or reference outcomes.
Unresolved cases are retained as ambiguous. The CLI requires an existing output
parent and refuses to overwrite an assessment.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

TERM = re.compile(r'(?<!\w)(not[_ -]ready|undetermined|ready)(?!\w)', re.I)


def normal(value: str) -> str:
    return value.lower().replace(' ', '_').replace('-', '_')


def candidate(text: str) -> tuple[str, str, str]:
    """Return a provisional code, exact excerpt and auditable rule identifier."""
    clean = re.sub(r'[*`]', '', text)
    terms = {normal(m.group()) for m in TERM.finditer(clean)}
    # These are review triggers, not inferred alternative labels.
    hazard = re.search(r'not\s+(?:(?:yet|currently|fully|necessarily|be|considered|deemed|confirmed)\s+)+ready'
                       r'|ready\?|retract|cannot (?:confirm|declare|establish)|can.t (?:confirm|declare)'
                       r'|was ready|would be ready|could be ready|ready or not', clean, re.I)
    if len(terms) == 1 and not hazard:
        return next(iter(terms)), text, 'single_explicit_category'
    signals = set()
    for sentence in re.split(r'(?<=[.!?])\s+|\n+', clean):
        s = sentence.strip().lower()
        matches = list(TERM.finditer(s))
        if not matches:
            continue
        # A list of the three allowed codes is not itself an assessment.
        if re.search(r'ready\s*[,/]\s*not[_ -]ready\s*[,/]?\s*(?:or\s+)?undetermined', s):
            continue
        for match in matches:
            before, after = s[:match.start()], s[match.end():]
            label = normal(match.group())
            if re.search(r'\b(?:if|unless|would|could)\b', before):
                continue
            if re.search(r'\b(?:requires?|required|criterion|rules?|considered)\b.*\bif\b', after):
                continue
            if re.search(r'\b(?:was|were|previously|earlier|historical|hypothetical)\b[^.!?;]*$', before):
                continue
            if re.search(r'(?:cannot|can.t|unable to|not enough|insufficient|no)\b[^.!?;]*'
                         r'(?:confirm|determine|establish|declare|conclude|classify|assess|justify|evidence|support)', before):
                if label == 'ready':
                    signals.add('undetermined')
                continue
            if re.search(r'\b(?:cannot|can.t|not)\s+(?:be\s+)?(?:considered|deemed|declared|established|confirmed)\s*$', before):
                continue
            if re.search(r'(?:not|no longer)\s*$', before):
                continue
            if re.search(r'\b(?:rather than|instead of|or)\s*$', before):
                continue
            # A general readiness rule, request or prerequisite is not a current decision.
            if re.search(r'\b(?:to be|to declare|to assess as|to consider|for declaring|for determining)\s*$', before):
                continue
            if label == 'ready' and re.match(r'\s+(?:if|only if|when|requires)\b', after):
                continue
            if re.search(r'\b(?:a|any|an|one)\s+(?:eligible\s+)?(?:failure|failed|missing)\b', before):
                continue
            if re.search(r'\b(?:whether|unclear|unknown|not possible)\b', before):
                continue
            if re.search(r'\b(?:to (?:be |be considered |consider |declare |mark )|for (?:being |the release to be |the task to be ))[^.!?;]*$', before):
                continue
            # Keep explicit current conclusions, not incidental mentions of a code.
            explicit = (not before.strip(' -:;,\"\'') or
                        re.match(r'^(?:assessment|decision|result|status)(?: at [^:]+(?::\d+){0,2}z)?\s*:', s) or
                        re.search(r'\b(?:is|are|remains?|as|indicates?|means|considered|deemed|conclude|conclusion|status|assessment)\b[^.!?;:]{0,50}$', before))
            if explicit:
                signals.add(label)
    if len(signals) == 1 and not re.search(r'ready\?|retract|not\s+(?:currently|yet|fully)\s+ready', clean, re.I):
        return next(iter(signals)), text, 'consistent_current_decision_mentions'
    return 'ambiguous', text, 'requires_semantic_review'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('items', type=Path)
    parser.add_argument('adjudications', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    raw = args.items.read_bytes()
    payload = json.loads(raw)
    adjudications = json.loads(args.adjudications.read_text())
    overrides = adjudications['items']
    ids = {item['id'] for item in payload['items']}
    if set(overrides) - ids:
        raise ValueError('Adjudication does not belong to this masked export')
    counts = Counter()
    for item in payload['items']:
        decision, quote, rule = candidate(item['text'])
        note = ('Rule-assisted AI coding: ' + rule + '. Code only the stated decision; '
                'factual correctness is assessed separately. Unresolved alternatives remain ambiguous.')
        if item['id'] in overrides:
            decision, quote, note = (overrides[item['id']][key] for key in ('decision', 'quote', 'note'))
        if decision not in {'ready', 'not_ready', 'undetermined', 'no_answer', 'ambiguous'}:
            raise ValueError('Invalid decision')
        if not quote.strip() or quote not in item['text'] or not note.strip():
            raise ValueError('Every code requires a retained exact quote and explanation')
        item.update(decision=decision, quote=quote, note=note)
        counts[decision] += 1
    payload['annotator'] = 'OpenAI ChatGPT/Codex, AI-assisted masked coding, 2026-09-28'
    payload['assessor'] = {
        'kind': 'ai', 'model': 'OpenAI ChatGPT/Codex; exact serving model identifier not exposed',
        'method': 'masked-ai-rule-assisted-decision/1',
        'validation': 'No independent human validation or measured assessor error rate',
        'protocol': 'annotations/AI-CODING.md',
        'source_items_sha256': hashlib.sha256(raw).hexdigest(),
        'coding_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'adjudications_sha256': hashlib.sha256(args.adjudications.read_bytes()).hexdigest(),
        'masking': 'Only exported answer text used for coding; answer wording can reveal the workflow',
        'collection_changed': False,
    }
    with args.output.open('x') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'items':len(payload['items']), 'codes':dict(counts), 'ai_adjudications':len(overrides)}))


if __name__ == '__main__':
    main()
