"""Small, self-contained regression inputs for the runtime and MCP interfaces.

These are test data, not empirical study cases or public examples.
"""
from __future__ import annotations

import json
from pathlib import Path

PRESSURE_SOURCE = """// Synthetic data and two model-conditional estimates.
language "EAL/2";
environment bench { require "site" == "bench"; require "revision" == "A"; }
tool pressure_trial_tool { version "1"; mode deterministic; }
evidence pressure_trial { tool pressure_trial_tool; kind experiment; environment bench; max_age 7200; require "schema" == "EAL/typed-input/1"; }

reasoning pressure_difference { method "causal/1"; rationale "Difference of means for the identified pressure trial; units convert before checking the claim."; }
claim pressure_increase { statement "The estimated pump-A pressure increase is at least five kilopascals for this trial interval."; environment bench;
  proposition { subject "pump-A"; quantity "pressure"; unit "kPa"; scope "pressure-trial-A"; valid_from "2026-09-23T10:00:00Z"; valid_until "2026-09-23T11:00:00Z"; query {"assignment":"randomised"}; result "estimate" >= 5; }
}
claim pressure_bounded { statement "The estimated pump-A pressure increase is at most ten kilopascals for this trial interval."; environment bench;
  proposition { subject "pump-A"; quantity "pressure"; unit "kPa"; scope "pressure-trial-A"; valid_from "2026-09-23T10:00:00Z"; valid_until "2026-09-23T11:00:00Z"; query {"assignment":"randomised"}; result "estimate" <= 10; }
}

// One typed definition serves both conclusions. Each use binds the same trial.
pattern estimate_from_trial(c: claim, r: reasoning, e: evidence) {
  conclusion c;
  reasoning r;
  evidence e;
  binding e;
}
apply pressure_argument = estimate_from_trial(c=pressure_increase, r=pressure_difference, e=pressure_trial);
apply upper_argument = estimate_from_trial(c=pressure_bounded, r=pressure_difference, e=pressure_trial);
"""

PRESSURE_OBSERVATION = json.loads("""{
  "value": {
    "schema": "EAL/typed-input/1",
    "method": "causal/1",
    "subject": "pump-A",
    "quantity": "pressure",
    "unit": "Pa",
    "scope": "pressure-trial-A",
    "valid_from": "2026-09-23T10:00:00Z",
    "valid_until": "2026-09-23T11:00:00Z",
    "payload": {
      "assignment": "randomised",
      "treatment": [
        10000,
        12000
      ],
      "control": [
        3000,
        4000
      ]
    }
  },
  "observed_at": "2026-09-23T10:00:00Z",
  "context": {
    "site": "bench",
    "revision": "A"
  },
  "request": {
    "tool": "pressure_trial_tool",
    "tool_version": "1",
    "mode": "deterministic",
    "input": {},
    "context": {
      "site": "bench",
      "revision": "A"
    }
  }
}""")

RMS_SOURCE = """language "EAL/2";
environment lab { require "site" == "bench"; }
tool readings { version "1"; mode deterministic; }
evidence series {
  tool readings;
  kind measurement_series;
  environment lab;
  max_age 3600;
  require "schema" == "EAL/typed-input/1";
}
reasoning rms_method {
  method "engineering/rms/1";
  rationale "Compute RMS deviation from zero over the supplied pressure samples.";
}
claim bounded_rms {
  statement "RMS pressure relative to zero is at most 5 kPa for this sample.";
  environment lab;
  proposition {
    subject "pump-A";
    quantity "pressure";
    unit "kPa";
    scope "sample-episode-v1";
    valid_from "2026-09-23T10:00:00Z";
    valid_until "2026-09-23T11:00:00Z";
    query {"origin":0};
    result "rms" <= 5;
  }
}
argument sampled_rms {
  conclusion bounded_rms;
  reasoning rms_method;
  evidence series;
  binding series;
}
"""

RMS_OBSERVATION = json.loads("""{
  "observed_at": "2026-09-23T12:00:00Z",
  "context": {
    "site": "bench"
  },
  "value": {
    "schema": "EAL/typed-input/1",
    "method": "engineering/rms/1",
    "subject": "pump-A",
    "quantity": "pressure",
    "unit": "kPa",
    "scope": "sample-episode-v1",
    "valid_from": "2026-09-23T10:00:00Z",
    "valid_until": "2026-09-23T11:00:00Z",
    "payload": {
      "origin": 0,
      "samples": [
        3,
        4
      ]
    }
  },
  "request": {
    "tool": "readings",
    "tool_version": "1",
    "mode": "deterministic",
    "input": {},
    "context": {
      "site": "bench"
    }
  }
}""")

REACHABILITY_SOURCE = """language "EAL/2";
environment controller_bench { require "site" == "simulation"; }
tool graph_reader { version "1"; mode deterministic; }
evidence graph_record {
  tool graph_reader; kind finite_graph; environment controller_bench;
  max_age 3600; require "schema" == "EAL/typed-input/1";
}
reasoning finite_check {
  method "engineering/reachability/1";
  rationale "Search every state reachable in at most three transitions in the recorded model.";
}
claim bounded_safe {
  statement "The supplied controller transition model has no path to state three within three steps.";
  environment controller_bench;
  proposition {
    subject "controller-X"; quantity "proposition"; unit "1"; scope "controller-model-X";
    valid_from "2040-01-01T08:00:00Z"; valid_until "2040-01-01T10:00:00Z";
    query {"start":0,"forbidden":[3],"horizon":3};
    result "reachable" == false;
  }
}
argument safety_route {
  conclusion bounded_safe; reasoning finite_check; evidence graph_record; binding graph_record;
}
"""

REACHABILITY_OBSERVATION = json.loads("""{
  "observed_at": "2040-01-01T09:00:00Z",
  "context": {
    "site": "simulation"
  },
  "request": {
    "tool": "graph_reader",
    "tool_version": "1",
    "mode": "deterministic",
    "input": {},
    "context": {
      "site": "simulation"
    }
  },
  "value": {
    "schema": "EAL/typed-input/1",
    "method": "engineering/reachability/1",
    "subject": "controller-X",
    "quantity": "proposition",
    "unit": "1",
    "scope": "controller-model-X",
    "valid_from": "2040-01-01T08:00:00Z",
    "valid_until": "2040-01-01T10:00:00Z",
    "payload": {
      "node_count": 4,
      "edges": [
        [
          0,
          1
        ],
        [
          1,
          2
        ]
      ],
      "start": 0,
      "forbidden": [
        3
      ],
      "horizon": 3
    }
  }
}""")

def write_case(workspace: Path, name: str) -> tuple[Path, Path, Path]:
    """Install a deterministic JSON-file tool inside the temporary test workspace."""
    sources = {
        'pressure': (PRESSURE_SOURCE, PRESSURE_OBSERVATION, 'pressure_trial_tool'),
        'rms': (RMS_SOURCE, RMS_OBSERVATION, 'readings'),
        'reachability': (REACHABILITY_SOURCE, REACHABILITY_OBSERVATION, 'graph_reader'),
    }
    source, observation, tool = sources[name]
    directory = workspace / "cases"
    directory.mkdir(exist_ok=True)
    source_path = directory / f"{name}.eal"
    source_path.write_text(source)
    observation_path = directory / f"{name}.json"
    observation_path.write_text(json.dumps(observation))
    registry_path = directory / f"{name}.toml"
    registry_path.write_text(
        f'[tools.{tool}]\nkind = "json_file"\npath = "cases/{name}.json"\n'
        'version = "1"\nmode = "deterministic"\n'
    )
    return source_path, observation_path, registry_path


def write_suite(workspace: Path, *, split: str = "development") -> Path:
    """One generated task for harness regression tests; not a model study."""
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "pressure.eal").write_text(PRESSURE_SOURCE)
    (workspace / "observations.json").write_text(json.dumps({"pressure_trial": PRESSURE_OBSERVATION}))
    suite = {
        "schema": "EAL/engineering-tasks/1",
        "version": "synthetic-interface-regression",
        "tasks": [{
            "id": "pressure-trial", "family": "typed_measurement", "split": split,
            "question": "Assess the declared claims for this supplied measurement.",
            "source": "pressure.eal", "observations": "observations.json",
            "context": {"site": "bench", "revision": "A"},
            "now": "2026-09-23T10:30:00Z",
            "expected": {"claims": {"pressure_increase": "supported", "pressure_bounded": "supported"}},
            "oracle": "Only the test harness sees this withheld answer key.",
        }],
    }
    filename = workspace / "suite.json"
    filename.write_text(json.dumps(suite))
    return filename
