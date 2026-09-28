"""Independent checks of answer measurement, masked coding and format interventions."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.model_transfer.annotations import AnnotationExchange, SCHEMA
from experiments.model_transfer.answers import response_format
from experiments.model_transfer.cases import CASES
from experiments.model_transfer.scoring import ReferenceScorer


@pytest.mark.parametrize(('text', 'decision'), [
    ('Ready.', 'ready'),
    ('Not ready.', 'not_ready'),
    ('Undetermined.', 'undetermined'),
    ('The service is ready.', 'ready'),
    ('The service is currently not ready.', 'not_ready'),
    ('Decision: undetermined.', 'undetermined'),
    ('not_ready', 'not_ready'),
    ('  ASSESSMENT: READY.\n', 'ready'),
])
def test_prose_codes_only_complete_canonical_decisions_without_schema(text, decision):
    result = response_format('prose').parse(text)
    assert result['answer']['decision'] == decision
    assert result['format_valid'] is None
    assert result['annotation']['status'] == 'automatic'
    assert result['annotation']['method'] == 'canonical-prose-decision/1'
    assert result['files'] == []
    score = ReferenceScorer().score(CASES[0], 0, result)
    assert score['task_match'] is (decision == 'ready')
    assert score['grounded_match'] is None
    assert score['decision_and_basis_match'] is None


@pytest.mark.parametrize('text', [
    'Ready — provided the new probe confirms the old reading.',
    'The service is ready. That conclusion is unsupported; readiness remains unknown.',
    'The service is ready. Its measured latency is below the limit.',
    'The service is currently not ready. The threshold is exceeded.',
    '**Decision: undetermined.** The operating assumption has expired.',
    'The service is ready. This is an example of an incorrect answer.',
    'The old assessment: ready.',
    'Undetermİned.',
    '{"decision":"ready","explanation":"This conclusion is unsupported."}',
    'Ready if the new probe confirms the old reading.',
    'The service was ready earlier.',
    'The service is ready. The service is not ready.',
    'The service is not ready; however, it is ready under the other assumption.',
    'The old note says "ready". I cannot determine the current state.',
    'The measurement falls comfortably inside the acceptable region.',
    'Readiness cannot be established from the available information.',
    "The service is ready. No, it isn't.",
    'Ready: probably.',
    'Ready? There is no measurement.',
    'The service is ready? The measurement is missing.',
    'Ready. No.',
    'Ready? The reading is 180 ms.',
    'The service is ready. I retract that conclusion.',
])
def test_uncoded_prose_is_pending_measurement_not_failure(text):
    parsed = response_format('prose').parse(text)
    score = ReferenceScorer().score(CASES[0], 0, parsed)
    assert parsed['annotation']['status'] == 'pending'
    assert score['task_match'] is None
    assert score['decision_match'] is None
    assert score['false_definitive'] is None
    assert not score['no_answer']


def test_empty_answer_is_observed_failure():
    parsed = response_format('prose').parse('  ')
    score = ReferenceScorer().score(CASES[0], 0, parsed)
    assert score['task_match'] is False
    assert score['no_answer']


def test_format_interventions_do_not_require_reasoning_or_tools():
    prose = response_format('prose')
    prompted = response_format('json_prompted')
    schema = response_format('json_schema')
    assert 'JSON' not in prose.instructions
    assert 'timestamp' not in prose.instructions and 'file' not in prose.instructions
    assert prose.provider_format is None and prompted.provider_format is None
    assert prompted.instructions == schema.instructions
    assert schema.provider_format['type'] == 'json_schema'
    for mode in ('json_prompted', 'json_schema'):
        result = response_format(mode).parse('The service is ready.')
        assert result['format_valid'] is False
        assert ReferenceScorer().score(CASES[0], 0, result)['task_match'] is None
    with pytest.raises(ValueError, match='Unknown response mode'):
        response_format('automatic')


def test_partial_json_task_decision_is_independent_of_format_and_grounding():
    parsed = response_format('json_prompted').parse('{"decision":"ready"}')
    assert parsed['annotation']['status'] == 'pending'
    assert ReferenceScorer().score(CASES[0], 0, parsed)['task_match'] is None
    parsed['annotation'] = {'status': 'human', 'annotator': 'fixture-coder'}
    score = ReferenceScorer().score(CASES[0], 0, parsed)
    assert not parsed['format_valid']
    assert score['task_match']
    assert score['grounded_match'] is None
    assert score['internally_consistent'] is None
    volunteered = response_format('prose').parse('{"decision":"ready","files":[{"name":"bad"}]}')
    assert volunteered['answer'] is None
    assert volunteered['annotation']['status'] == 'pending'
    assert volunteered['files'] == []
    assert volunteered['format_valid'] is None
    assert ReferenceScorer().score(CASES[0], 0, volunteered)['task_match'] is None


def _run(tmp_path: Path, text: str = 'The available data cannot establish readiness.'):
    root = tmp_path / 'run'
    root.mkdir()
    parsed = response_format('prose').parse(text)
    session = {'session_id': 'revealing-arm-and-model-id', 'session': 0,
               'raw_answer': text, 'model': 'model-name', **parsed}
    session['score'] = ReferenceScorer().score(CASES[0], 0, session)
    rows = [{'case': CASES[0].identifier, 'arm': 'eal', 'sessions': [session]}]
    (root / 'rows.json').write_text(json.dumps(rows))
    (root / 'cases.json').write_text(json.dumps([asdict(CASES[0])]))
    return root, rows


@pytest.mark.parametrize('text', [
    'Ready — provided the new probe confirms the old reading.',
    'The service is ready. That conclusion is unsupported; readiness remains unknown.',
    '{"decision":"ready","explanation":"Readiness remains unknown."}',
])
def test_qualified_or_contradicted_answers_enter_default_blind_annotation(tmp_path, text):
    run, rows = _run(tmp_path, text)
    session = rows[0]['sessions'][0]
    assert session['score']['task_match'] is None
    assert session['annotation']['status'] == 'pending'
    bundle = tmp_path / 'coding'
    assert AnnotationExchange().export(run, bundle)['exported'] == 1
    assert json.loads((bundle / 'items.json').read_text())['items'][0]['text'] == text


def _labels(bundle: Path, text: str, decision: str = 'undetermined') -> Path:
    items = json.loads((bundle / 'items.json').read_text())
    items['annotator'] = 'independent-assessor-A'
    items['items'][0].update(decision=decision, quote=text, note='Explicit inability to establish readiness.')
    labels = bundle / 'coded.json'
    labels.write_text(json.dumps(items))
    return labels


def test_blind_annotation_roundtrip_retains_raw_and_supplies_no_unobserved_basis(tmp_path):
    run, rows = _run(tmp_path)
    original = (run / 'rows.json').read_bytes()
    bundle = tmp_path / 'coding'
    exchange = AnnotationExchange()
    assert exchange.export(run, bundle)['exported'] == 1
    public = json.loads((bundle / 'items.json').read_text())
    assert public['schema'] == SCHEMA
    item = public['items'][0]
    assert set(item) == {'id', 'text', 'decision', 'quote', 'note'}
    assert 'revealing-arm-and-model-id' not in json.dumps(public)
    assert 'reference' not in item and 'model' not in item and 'arm' not in item and 'case' not in item
    raw_text = rows[0]['sessions'][0]['raw_answer']
    labels = _labels(bundle, raw_text)
    output = tmp_path / 'annotated-rows.json'
    assert exchange.import_labels(run, bundle, labels, output)['annotated'] == 1
    annotated = json.loads(output.read_text())[0]['sessions'][0]
    assert (run / 'rows.json').read_bytes() == original
    assert annotated['raw_answer'] == raw_text
    assert annotated['answer'] == {'decision': 'undetermined'}
    assert annotated['score']['task_match'] is False
    assert annotated['score']['abstention_when_reference_decisive']
    assert annotated['score']['grounded_match'] is None
    with pytest.raises(ValueError, match='new annotated output'):
        exchange.import_labels(run, bundle, labels, output)


@pytest.mark.parametrize(('decision', 'expected', 'no_answer'), [
    ('ambiguous', None, False), ('no_answer', False, True), ('ready', True, False)])
def test_annotation_codes_preserve_unknown_and_no_answer_distinction(tmp_path, decision, expected, no_answer):
    run, rows = _run(tmp_path)
    bundle = tmp_path / 'coding'
    exchange = AnnotationExchange()
    exchange.export(run, bundle)
    labels = _labels(bundle, rows[0]['sessions'][0]['raw_answer'], decision)
    output = tmp_path / 'annotated.json'
    exchange.import_labels(run, bundle, labels, output)
    score = json.loads(output.read_text())[0]['sessions'][0]['score']
    assert score['task_match'] is expected
    assert score['no_answer'] is no_answer


@pytest.mark.parametrize('corruption', ['changed_rows', 'unknown_id', 'duplicate_id', 'invalid_quote', 'invalid_code'])
def test_annotation_rejects_unlinked_or_unsupported_labels(tmp_path, corruption):
    run, rows = _run(tmp_path)
    bundle = tmp_path / 'coding'
    exchange = AnnotationExchange()
    exchange.export(run, bundle)
    labels = _labels(bundle, rows[0]['sessions'][0]['raw_answer'])
    contents = json.loads(labels.read_text())
    if corruption == 'changed_rows':
        (run / 'rows.json').write_text(json.dumps(rows) + '\n')
    elif corruption == 'unknown_id':
        contents['items'][0]['id'] = 'unknown'
    elif corruption == 'duplicate_id':
        contents['items'].append(copy.deepcopy(contents['items'][0]))
    elif corruption == 'invalid_quote':
        contents['items'][0]['quote'] = 'invented content'
    else:
        contents['items'][0]['decision'] = 'successful'
    labels.write_text(json.dumps(contents))
    output = tmp_path / 'annotated.json'
    with pytest.raises(ValueError):
        exchange.import_labels(run, bundle, labels, output)
    assert not output.exists()


def test_annotation_commands_execute_without_model_calls(tmp_path):
    run, rows = _run(tmp_path)
    bundle = tmp_path / 'coding'
    prefix = [sys.executable, '-m', 'experiments.model_transfer.annotations']
    subprocess.run(prefix + ['export', str(run), '--output', str(bundle)], check=True, capture_output=True)
    labels = _labels(bundle, rows[0]['sessions'][0]['raw_answer'])
    output = tmp_path / 'annotated.json'
    subprocess.run(prefix + ['import', str(run), str(bundle), str(labels), '--output', str(output)],
                   check=True, capture_output=True)
    assert output.exists()


def test_annotation_roundtrip_supports_nested_diagnostic_donor_and_variants(tmp_path):
    run, rows = _run(tmp_path)
    donor = rows[0]['sessions'][0]
    variant = copy.deepcopy(donor)
    variant.update(session_id='diagnostic-variant', session=1)
    rows = [{'case': CASES[0].identifier, 'donor_result': donor,
             'variants': [{'variant': 'compact', 'result': variant}, {'variant': 'full', 'result': None}]}]
    (run / 'rows.json').write_text(json.dumps(rows))
    raw = (run / 'rows.json').read_bytes()
    exchange = AnnotationExchange()
    bundle = tmp_path / 'diagnostic-coding'
    assert exchange.export(run, bundle)['exported'] == 2
    labels = json.loads((bundle / 'items.json').read_text())
    labels['annotator'] = 'independent coder'
    for item in labels['items']:
        item.update(decision='undetermined', quote=item['text'], note='Explicit inability to establish readiness.')
    label_file = bundle / 'coded.json'
    label_file.write_text(json.dumps(labels))
    output = tmp_path / 'annotated-diagnostics.json'
    exchange.import_labels(run, bundle, label_file, output)
    annotated = json.loads(output.read_text())[0]
    assert annotated['donor_result']['annotation']['status'] == 'human'
    assert annotated['variants'][0]['result']['annotation']['status'] == 'human'
    assert annotated['variants'][0]['result']['score']['task_match'] is False
    assert annotated['variants'][1]['result'] is None
    assert (run / 'rows.json').read_bytes() == raw
