import hashlib
import json

import pytest

from experiments.model_transfer.annotations import AnnotationExchange
from experiments.model_transfer.annotation_provenance import annotation_provenance
from test_model_transfer_answers import _run, _labels


def labels_for_ai(bundle, text):
    path = _labels(bundle, text)
    labels = json.loads(path.read_text())
    labels['assessor'] = {'kind': 'ai', 'model': 'fixture-model',
                          'method': 'masked-ai-test/1', 'validation': 'synthetic fixture only',
                          'protocol': 'Code explicit decisions only',
                          'source_items_sha256': hashlib.sha256((bundle / 'items.json').read_bytes()).hexdigest()}
    path.write_text(json.dumps(labels))
    return path


def test_ai_import_preserves_provenance_raw_text_and_unknown_codes(tmp_path):
    run, raw = _run(tmp_path)
    original = (run / 'rows.json').read_bytes()
    bundle = tmp_path / 'bundle'
    AnnotationExchange().export(run, bundle)
    labels = labels_for_ai(bundle, raw[0]['sessions'][0]['raw_answer'])
    output = tmp_path / 'derived.json'
    AnnotationExchange().import_labels(run, bundle, labels, output)
    rows = json.loads(output.read_text())
    session = rows[0]['sessions'][0]
    assert session['annotation']['status'] == 'ai'
    assert session['annotation']['method'] == 'masked-ai-test/1'
    assert session['score']['assessment_status'] == 'assessed'
    assert (run / 'rows.json').read_bytes() == original
    assert annotation_provenance(rows)['session_counts'] == {'ai': 1}
    supplied = json.loads(labels.read_text())
    supplied['items'][0]['decision'] = 'ambiguous'
    labels.write_text(json.dumps(supplied))
    unresolved = tmp_path / 'unresolved.json'
    AnnotationExchange().import_labels(run, bundle, labels, unresolved)
    rows = json.loads(unresolved.read_text())
    assert rows[0]['sessions'][0]['score']['task_match'] is None
    assert annotation_provenance(rows)['contains_ai_assessment']


@pytest.mark.parametrize('corruption', ['kind', 'model', 'method', 'validation', 'protocol',
                                      'source_items_sha256', 'text'])
def test_ai_import_rejects_missing_or_changed_measurement_provenance(tmp_path, corruption):
    run, rows = _run(tmp_path)
    bundle = tmp_path / 'bundle'
    AnnotationExchange().export(run, bundle)
    labels = labels_for_ai(bundle, rows[0]['sessions'][0]['raw_answer'])
    supplied = json.loads(labels.read_text())
    if corruption == 'text':
        supplied['items'][0]['text'] = 'A different answer'
    else:
        supplied['assessor'][corruption] = ''
    labels.write_text(json.dumps(supplied))
    with pytest.raises(ValueError):
        AnnotationExchange().import_labels(run, bundle, labels, tmp_path / 'derived.json')
