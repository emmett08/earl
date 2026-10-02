"""Expose measurement provenance independently of processing completion."""
from collections import Counter
import os
import sys

from eal import __version__
from .run_state import implementation_digest

from .annotations import _sessions


def processing_provenance() -> dict:
    return {'package_version': __version__, 'revision': os.environ.get('GITHUB_SHA'),
            'implementation_sha256': implementation_digest(), 'python': sys.version,
            'scope': 'Offline reconstruction; original collection provenance is retained separately'}


def annotation_provenance(rows: list[dict]) -> dict:
    counts, assessors = Counter(), []
    for row in rows:
        for session in _sessions(row):
            annotation = session.get('annotation') or {}
            assessor = annotation.get('assessor')
            kind = (assessor or {}).get('kind', annotation.get('status', 'unrecorded'))
            counts[kind] += 1
            if assessor is not None:
                record = {'annotator': annotation.get('annotator'), **assessor}
                if record not in assessors:
                    assessors.append(record)
    return {'schema': 'EAL/annotation-provenance/1', 'session_counts': dict(counts),
            'assessors': assessors, 'contains_ai_assessment': bool(counts['ai']),
            'contains_scripted_assessment': bool(counts['scripted']),
            'qualification': ('Deterministic fixture labels in a scripted rehearsal; no human or model assessment measurements.'
                              if counts['scripted'] else
                              'AI-coded decisions; assessor error has not been independently measured. '
                              'Outcome estimates and allocation calculations are conditional on these labels; '
                              'they do not establish human-validated accuracy.' if counts['ai'] else
                              'Interpret outcome measurements using the recorded assessment methods.')}
