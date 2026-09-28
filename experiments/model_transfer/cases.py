"""Fixed synthetic task specifications and external measurement timelines."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

FIRST = '2026-09-28T10:00:00Z'
EARLY = '2026-09-28T10:01:00Z'
LATE = '2026-09-28T10:10:00Z'


@dataclass(frozen=True)
class Case:
    identifier: str
    initial_reading: float
    later_reading: float | None
    later_at: str
    assumption_until: str | None = None
    assumption_from: str = FIRST
    metric: str = 'latency'
    unit: str = 'ms'
    threshold: float = 200
    direction: str = 'at_most'
    cohort: str = 'diagnostic'

    def time(self, session: int) -> str:
        if session == 0:
            return FIRST
        return (datetime.fromisoformat(self.later_at.replace('Z', '+00:00')) +
                timedelta(seconds=60 * (session - 1))).isoformat()

    def measurement(self, session: int) -> dict:
        reading = self.initial_reading if session == 0 else self.later_reading
        observed_at = FIRST if session == 0 or self.later_at == EARLY else self.later_at
        value = {'threshold': self.threshold, 'direction': self.direction}
        if reading is not None:
            value['reading'] = reading
        return {'value': value, 'observed_at': observed_at}

    def specification(self) -> str:
        relation = 'at most' if self.direction == 'at_most' else 'at least'
        assumption = (f'The operating assumption applies from {self.assumption_from} '
                      f'inclusive until {self.assumption_until} exclusive. '
                      if self.assumption_until else 'No additional operating assumption applies. ')
        return (f'Assess readiness of the service. A measured {self.metric} {relation} '
                f'{self.threshold} {self.unit} establishes ready; a measured failure of that '
                'criterion establishes not_ready. The probe value\'s reading uses those units. '
                'Reports are usable for 300 seconds after observed_at, inclusively, and never '
                'before observed_at. Missing, stale or unavailable measurements require '
                'undetermined. An expired or not-yet-applicable operating assumption takes '
                'precedence and requires undetermined. ' + assumption)

    def source(self) -> str:
        assumption = (f'assumption window {{ statement "The operating assumption applies."; '
                      f'environment scope; validate report; valid_from "{self.assumption_from}"; '
                      f'valid_until "{self.assumption_until}"; }}' if self.assumption_until else '')
        return f'''language "EAL/2";
environment scope {{ require "service" == "orders"; }}
tool probe {{ version "1"; }}
evidence report {{ tool probe; kind threshold_measurement; environment scope; max_age 300;
  require "reading" >= 0; require "threshold" == {self.threshold};
  require "direction" == "{self.direction}"; }}
{assumption}
reasoning threshold {{ method "experiment/threshold/1";
  rationale "Compare the measurement with the specified inclusive threshold. Positive and negative findings are completed calculations.";
  require "reading" >= 0; }}
claim criterion_evaluated {{ statement "The measurement has been compared with the readiness criterion within its applicability conditions."; environment scope; }}
argument result {{ conclusion criterion_evaluated; reasoning threshold; evidence report;
  {'assumptions window;' if self.assumption_until else ''} }}
'''


CASES = (
    Case('fresh_positive', 180, 180, EARLY),
    Case('fresh_negative', 240, 240, EARLY),
    Case('refresh_positive', 240, 180, LATE),
    Case('refresh_negative', 180, 240, LATE),
    Case('missing_measurement', 180, None, LATE),
    Case('expired_assumption', 180, 180, EARLY, '2026-09-28T10:00:30Z'),
    Case('capacity_boundary', 20, 20, EARLY, metric='free storage', unit='GB',
         threshold=20, direction='at_least', cohort='additional'),
    Case('capacity_drop', 25, 15, LATE, metric='free storage', unit='GB',
         threshold=20, direction='at_least', cohort='additional'),
)
