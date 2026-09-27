"""Independent examples and adversarial cases for the trial's Python measure."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

from cognitive_complexity import collect, compare, score_source


class CognitiveComplexityTests(unittest.TestCase):
    def score(self, code: str, name: str = "f") -> int:
        result = score_source(textwrap.dedent(code))
        return next(row["score"] for row in result["functions"] if row["qualname"] == name)

    def test_reference_if_else_and_nesting(self) -> None:
        self.assertEqual(self.score('''
            def f(x):
                if x:
                    pass
                elif x == 1:
                    pass
                else:
                    pass
        '''), 3)
        self.assertEqual(self.score('''
            def f(x):
                if x:
                    pass
                else:
                    if x == 1:
                        pass
        '''), 4)
        self.assertEqual(self.score('''
            def f(x):
                if x:
                    if x:
                        if x:
                            pass
        '''), 6)
        self.assertEqual(self.score('''
            def f(x):
                if x:
                    pass
                elif x == 1:
                    if x > 1:
                        pass
        '''), 4)
        self.assertEqual(self.score('''
            def f(x):
                if x:
                    pass
                elif(x == 1):
                    pass
        '''), 2)

    def test_reference_loop_else_and_early_exits(self) -> None:
        self.assertEqual(self.score('''
            def f(xs):
                for x in xs:
                    pass
                else:
                    if xs:
                        return 1
        '''), 4)
        self.assertEqual(self.score('''
            def f(x):
                if x:
                    return
                elif x == 1:
                    return 42
                while x:
                    if x == 1:
                        break
                    elif x == 2:
                        continue
        '''), 6)

    def test_reference_exception_handlers_and_transparent_finally(self) -> None:
        self.assertEqual(self.score('''
            def f(x):
                try:
                    if x:
                        pass
                except ValueError:
                    if x:
                        pass
                except (TypeError, KeyError):
                    if x:
                        pass
                finally:
                    if x:
                        pass
        '''), 8)
        self.assertEqual(self.score('''
            def f(x):
                try:
                    pass
                except ValueError:
                    pass
                else:
                    if x:
                        pass
        '''), 4)
        self.assertEqual(self.score('''
            async def f(x):
                async for item in x:
                    if item:
                        pass
        '''), 3)

    def test_reference_boolean_runs_and_nested_ternaries(self) -> None:
        self.assertEqual(self.score('''
            def f(a, b, c, d):
                sink(a and b and c and d)
                sink(a or b or c or d)
                sink(a and b or c or d)
                sink(a and b or c and d)
        '''), 7)
        self.assertEqual(self.score('''
            def f(a, b, c):
                return a and not (b and c)
        '''), 2)
        self.assertEqual(self.score('''
            def f(a, b, c):
                return a if b else (b if c else c)
        '''), 3)

    def test_reference_nested_functions_class_and_decorator_exception(self) -> None:
        self.assertEqual(self.score('''
            def f(x):
                if x:
                    pass
                def nested():
                    if x:
                        pass
        '''), 3)
        self.assertEqual(self.score('''
            def f(x):
                def wrapper():
                    if x:
                        return x
                return wrapper
        '''), 1)
        self.assertEqual(self.score('''
            def f(x):
                value = x
                def wrapper():
                    if x:
                        return x
                return wrapper
        '''), 2)
        self.assertEqual(self.score('''
            def f(x):
                def inner():
                    return 1 if x else 2
                class C:
                    def method(self):
                        return 1 if x else 2
                return 1 if x else 2
        '''), 4)
        self.assertEqual(self.score('''
            def f(x):
                return lambda y: 1 if y else 2
        '''), 2)
        module_result = score_source(textwrap.dedent('''
            if active:
                def f(x):
                    if x:
                        pass
        '''))
        self.assertEqual(module_result["total"], 2)
        self.assertEqual(module_result["functions"][0]["score"], 1)

    def test_white_paper_recursion_extension(self) -> None:
        self.assertEqual(self.score('''
            def f(x):
                if x:
                    return f(x - 1)
        '''), 2)
        result = score_source(textwrap.dedent('''
            def f(x):
                return g(x) if x else x
            def g(x):
                return f(x) if x else x
        '''))
        self.assertEqual({r["qualname"]: r["score"] for r in result["functions"]}, {"f": 2, "g": 2})
        self.assertEqual(result["total"], 4)
        self.assertEqual(self.score('''
            class C:
                def f(self, x):
                    if x:
                        return self.f(x - 1)
        ''', "C.f"), 2)
        self.assertEqual(self.score('''
            def f(x):
                f = x
                return f()
        '''), 0)  # local rebinding does not establish recursion
        self.assertEqual(self.score('''
            class C:
                def f(self):
                    return g()
                def g(self):
                    return self.f()
        ''', "C.f"), 0)  # a bare name in a method does not resolve to C.g

    def test_switch_like_match_and_guard(self) -> None:
        self.assertEqual(self.score('''
            def f(x):
                match x:
                    case 1:
                        pass
                    case 2:
                        pass
                    case _:
                        pass
        '''), 1)
        self.assertEqual(self.score('''
            def f(x):
                match x:
                    case int() if x > 0:
                        if x > 10:
                            return x
                    case _:
                        return 0
        '''), 5)

    def test_comprehension_shorthand_and_expression_logic(self) -> None:
        self.assertEqual(self.score('''
            def f(xs):
                return [x for x in xs if x > 0]
        '''), 0)
        self.assertEqual(self.score('''
            def f(xs):
                return [x for x in xs if x > 0 and x < 10]
        '''), 1)

    def test_collection_provenance_no_double_count_and_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.py").write_text(textwrap.dedent('''
                def outer(x):
                    def inner(y):
                        if y:
                            return x
                    return inner
            '''), encoding="utf-8")
            report = collect(root, 0)
        self.assertEqual(report["schema"], "python-cognitive-complexity/1")
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["maximum"], 1)
        self.assertEqual(report["function_count"], 2)
        self.assertEqual(report["threshold_breaches"], 2)
        self.assertEqual(report["functions"][1]["included_in"], "outer")
        self.assertEqual(len(report["files"][0]["sha256"]), 64)

    def test_comparison_separates_matching_added_and_removed_functions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "old"
            new = root / "new"
            old.mkdir()
            new.mkdir()
            (old / "a.py").write_text("def f(x):\n    if x:\n        return x\n\ndef retired():\n    pass\n", encoding="utf-8")
            (new / "a.py").write_text("def f(x):\n    if x:\n        if x > 1:\n            return x\n\ndef added():\n    pass\n", encoding="utf-8")
            delta = compare(collect(old), collect(new))
        self.assertEqual(delta["total_delta"], 2)
        self.assertEqual(delta["matched_score_delta"], 2)
        self.assertEqual(delta["matched_function_count"], 1)
        self.assertEqual([row["qualname"] for row in delta["added"]], ["added"])
        self.assertEqual([row["qualname"] for row in delta["removed"]], ["retired"])
        self.assertEqual(delta["changed_files"], ["a.py"])

    def test_fail_closed_parse_error_and_eal_envelope(self) -> None:
        script = Path(__file__).with_name("cognitive_complexity.py")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "module.py"
            source.write_text("def f(x):\n    if x:\n        return x\n", encoding="utf-8")
            request = {
                "evidence_id": "baseline_complexity",
                "environment": "trial",
                "tool": "cognitive_complexity",
                "tool_version": "1",
                "input": {"path": str(source), "max_function_score": 0},
                "context": {"trial": "base"},
            }
            result = subprocess.run([sys.executable, str(script)], input=json.dumps(request), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            envelope = json.loads(result.stdout)
            self.assertEqual(envelope["value"]["threshold_breaches"], 1)
            self.assertEqual(envelope["request"]["input"], request["input"])
            self.assertEqual(envelope["context"], request["context"])
            self.assertIn("+00:00", envelope["observed_at"])
            source.write_text("def broken(:\n", encoding="utf-8")
            failure = subprocess.run([sys.executable, str(script), str(source)], text=True, capture_output=True)
            self.assertEqual(failure.returncode, 2)
            self.assertEqual(failure.stdout, "")


if __name__ == "__main__":
    unittest.main()
