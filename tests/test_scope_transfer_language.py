"""Transfer is explicit, conditional, typed and scoped throughout assessment."""
from copy import deepcopy
import pytest
from eal.parser import parse
from eal.semantics import validate
from eal.evaluator import evaluate, environment_fingerprint, canonical_digest
from _provenance import synthetic_provenance
from eal.formatter import semantic_ir, format_program
from test_typed_propositions import SOURCE, VALUE
from test_evaluator import record, NOW


def source():
    claim = SOURCE[SOURCE.index('claim raised {'):SOURCE.index('argument contrast')]
    target = claim.replace('claim raised', 'claim deployed').replace('environment lab','environment production').replace('scope "experiment-v1"','scope "production-v1"')
    return SOURCE + '''environment production {
  require site == "production"
}
evidence qualification {
  environment production
  tool readings
  kind test
  max_age 60
  require equivalent == true
}
assumption equivalent {
  statement "The reviewed transfer relation applies to these two environments."
  environment production
  validate qualification
}
reasoning transport {
  method "structured/1"
  rationale "Conditional scope transfer under the declared qualification."
  transfer from lab to production assuming equivalent reviewed "review/transfer-1"
}
''' + target + 'argument deployment = [assumptions equivalent, premises raised] via transport => deployed\n'


def run(qualification=True, context=None):
    program = parse(source())
    assert not validate(program)
    assert semantic_ir(program) == semantic_ir(parse(format_program(program)))
    records = {'trial': record(program, 'trial', deepcopy(VALUE)),
               'qualification': record(program, 'qualification', {'equivalent':qualification})}
    records['qualification'].update(synthetic_provenance(program,'qualification',{'site':'production'}),
                                     environment_fingerprint=environment_fingerprint('production',{'site':'production'}))
    return evaluate(program,records,now=NOW,context=context or {'$environments':{'lab':{'site':'bench'},'production':{'site':'production'}}})


def test_reviewed_transfer_preserves_proposition_and_checks_both_scopes():
    result = run()
    assert result['claims']['deployed']['status'] == 'supported'
    binding = result['arguments']['deployment']['reasoning_result']['binding']
    assert binding['kind'] == 'scope_transfer'
    assert binding['correspondence_checked'] is True
    assert binding['transport_justification_verified'] is False
    assert run(False)['claims']['deployed']['status'] == 'unsupported'
    assert run(context={'$environments':{'lab':{'site':'elsewhere'},'production':{'site':'production'}}})['claims']['deployed']['status'] == 'unsupported'


@pytest.mark.parametrize('old,new', [('assuming equivalent reviewed','assuming missing reviewed'),
    ('[assumptions equivalent, premises raised]','[premises raised]'),
    ('transfer from lab to production','transfer from lab to lab'),
    ('review/transfer-1','')])
def test_invalid_transfer_metadata_is_rejected_before_execution(old,new):
    assert validate(parse(source().replace(old,new)))


def test_transfer_cannot_change_the_question_or_strengthen_the_result():
    text = source()
    before, target = text.split('claim deployed',1)
    for changed in [target.replace('>= 5','>= 6'),target.replace('pump-A','pump-B'),
                    target.replace('2026-09-23T11:00:00Z','2026-09-23T12:00:00Z')]:
        assert 'invalid_scope_transfer' in {d.code for d in validate(parse(before+'claim deployed'+changed))}
