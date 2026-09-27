"""Controls for the assessor, excluded from the coding clone."""

import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / "source"
HOST = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load("v4_reservation_fixture_source", SOURCE / "service.py")
previous_service = sys.modules.get("service")
sys.modules["service"] = base
try:
    ReferenceService = load("v4_reservation_reference", HOST / "reference.py").ReferenceService
finally:
    if previous_service is None:
        sys.modules.pop("service", None)
    else:
        sys.modules["service"] = previous_service
assessor = load("v4_reservation_host_assessor", HOST / "assess.py")
CASES, assess = assessor.CASES, assessor.assess


class AssessorContractTests(unittest.TestCase):
    def test_reference_passes_every_cumulative_stage(self):
        reference = SimpleNamespace(**{**vars(base), "ReservationService": ReferenceService})
        for stage in "BCD":
            due = CASES["B"] + (CASES["C"] if stage in "CD" else []) + (CASES["D"] if stage == "D" else [])
            for name, case in due:
                with self.subTest(stage=stage, case=name):
                    case(reference)

    def test_unextended_source_passes_baseline_and_fails_future_features(self):
        result = assess(Path(__file__).resolve().parents[1] / "source", "D")
        self.assertTrue(result["valid"])
        self.assertEqual(result["checks"][0]["status"], "pass")
        self.assertEqual(result["passed"], 1)
        self.assertEqual(result["total"], 9)


if __name__ == "__main__":
    unittest.main()
