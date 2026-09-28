"""Validate prospective decision, precision and simulation settings."""
import math


def _fraction(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 < value < 1


def validate_decision_specification(decision: dict) -> None:
    if not isinstance(decision, dict):
        raise ValueError('Declare the practical decision specification')
    if type(decision.get('recipient_horizon')) is not int or not 1 <= decision['recipient_horizon'] <= 10:
        raise ValueError('Invalid recipient horizon')
    if not all(_fraction(decision.get(key)) for key in ('correctness_margin', 'minimum_token_reduction', 'minimum_correctness')):
        raise ValueError('Practical decision fractions must be in (0, 1)')


def validate_information_target(target: dict) -> None:
    if not isinstance(target, dict) or target.get('method') != 'precision':
        raise ValueError('Declare the prospective precision method')
    if not all(_fraction(target.get(key)) for key in ('confidence', 'correctness_half_width', 'token_reduction_half_width', 'assurance')):
        raise ValueError('Precision fractions must be in (0, 1)')


def validate_information_design(config: dict) -> dict:
    if config.get('schema') != 'EAL/model-transfer-information-design/1':
        raise ValueError('Invalid information-design schema')
    if type(config.get('seed')) is not int or type(config.get('simulations')) is not int or not 100 <= config['simulations'] <= 10000:
        raise ValueError('Use a seed and between 100 and 10000 simulation replications')
    if type(config['budget_usd']) not in (int, float) or not math.isfinite(config['budget_usd']) or not 0 < config['budget_usd'] <= 2:
        raise ValueError('Allocation simulations retain the USD 2 budget ceiling')
    if type(config.get('time_limit_seconds', 7200)) not in (int, float) or not 0 < config.get('time_limit_seconds', 7200) <= 7200:
        raise ValueError('Time limit must be at most the 7200-second workflow deadline')
    if type(config.get('workflow_overhead_seconds', 0)) not in (int, float) or not 0 <= config.get('workflow_overhead_seconds', 0) < config.get('time_limit_seconds', 7200):
        raise ValueError('Declare a nonnegative workflow overhead allowance below the deadline')
    validate_decision_specification(config.get('practical_decision'))
    validate_information_target(config.get('information_target'))
    if not config.get('candidates') or not config.get('scenarios'):
        raise ValueError('Declare precision targets, candidate allocations and sensitivity scenarios')
    for candidate in config['candidates']:
        if any(type(candidate.get(k)) is not int or candidate[k] < 1 for k in ('cases', 'repetitions')):
            raise ValueError('Candidate case and repetition counts must be positive integers')
        if candidate['repetitions'] > 512:
            raise ValueError('Candidate repetitions exceed the executable plan limit')
    names = [s['name'] for s in config['scenarios']]
    if len(set(names)) != len(names):
        raise ValueError('Scenario names must be unique')
    if not any(s.get('purpose', 'design') == 'design' for s in config['scenarios']):
        raise ValueError('At least one scenario must define allocation feasibility')
    for scenario in config['scenarios']:
        if scenario.get('purpose', 'design') not in ('design', 'stress'):
            raise ValueError('Scenario purpose must be design or stress')
        for key in ('token_reduction', 'correctness_difference', 'missing_probability', 'cost_multiplier'):
            if type(scenario.get(key)) not in (int, float) or not math.isfinite(scenario[key]):
                raise ValueError('Scenario values must be finite numbers')
        if not (-1 <= scenario['token_reduction'] < 1 and -1 <= scenario['correctness_difference'] <= 1
                and 0 <= scenario['missing_probability'] <= 1 and scenario['cost_multiplier'] > 0):
            raise ValueError('Invalid effect, missingness or cost scenario')
        if any(type(scenario.get(key, default)) not in (int, float) or not math.isfinite(scenario.get(key, default))
               for key, default in (('resource_tail_probability', 0), ('resource_tail_multiplier', 1))):
            raise ValueError('Resource tail parameters must be finite')
        if not (0 <= scenario.get('resource_tail_probability', 0) < 1 and scenario.get('resource_tail_multiplier', 1) >= 1):
            raise ValueError('Invalid resource tail sensitivity')
        if type(scenario.get('elapsed_multiplier', 1)) not in (int, float) or not 0 < scenario.get('elapsed_multiplier', 1) <= 100:
            raise ValueError('Elapsed time multiplier must be positive and at most 100')
    return config
