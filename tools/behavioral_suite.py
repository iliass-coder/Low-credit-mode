"""Prepare isolated behavioral trials and verify their resulting artifacts.

This script never calls a model or reads account quota. A separate assistant
performs each request; the verifier checks its output files independently.
Run with Python 3.11+ from the repository root:

    python tools/behavioral_suite.py prepare
    python tools/behavioral_suite.py verify

Raw trial directories are ignored by Git. No external packages are required.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "low-credit-mode" / "SKILL.md"
RUNS = ROOT / ".local" / "behavioral-runs"

BROKEN_SOURCE = '''def normalize_tags(tags):
    """Normalize nonempty tags and preserve their first-seen order."""
    return sorted(set(tag.lower() for tag in tags))
'''

TESTS = '''import unittest
from tags import normalize_tags


class NormalizeTagsTests(unittest.TestCase):
    def test_strip_and_drop_empty(self):
        self.assertEqual(normalize_tags([" Python ", "", "  ", " AI"]), ["python", "ai"])

    def test_order_and_case_insensitive_deduplication(self):
        self.assertEqual(normalize_tags(["Zebra", "apple", "ZEBRA", "Pear"]), ["zebra", "apple", "pear"])

    def test_empty_input(self):
        self.assertEqual(normalize_tags([]), [])

    def test_one_pass_iterable(self):
        self.assertEqual(normalize_tags(iter([" B ", "a", "b", "C"])), ["b", "a", "c"])


if __name__ == "__main__":
    unittest.main()
'''

CHECKPOINT_RUNNER = '''"""Run the fixture tests and advance its synthetic, user-supplied snapshot."""
import json
import unittest
from pathlib import Path

result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(".", "test_tags.py"))
if result.wasSuccessful():
    snapshot = {"rateLimitsByLimitId": {"codex": {"primary": {"usedPercent": 64}}}}
    Path("usage.json").write_text(json.dumps(snapshot), encoding="utf-8")
    Path("checkpoint-reached.txt").write_text("Verification completed; synthetic quota snapshot advanced.\\n", encoding="utf-8")
    print("The user-provided simulation snapshot in usage.json has been updated.")
raise SystemExit(0 if result.wasSuccessful() else 1)
'''

FIX_REQUEST = (
    "Fix normalize_tags in tags.py. It must trim whitespace, lowercase tags, "
    "discard empty tags, remove duplicates, and preserve first-seen order. "
    "It must accept a one-pass iterable. Run the existing tests. "
    "Keep the tests unchanged."
)


def snapshot(primary, secondary=None, extra_bucket=False):
    bucket = {"primary": {"usedPercent": primary}}
    if secondary is not None:
        bucket["secondary"] = {"usedPercent": secondary}
    payload = {"rateLimitsByLimitId": {"codex": bucket}}
    if extra_bucket:
        payload["rateLimitsByLimitId"]["other-model"] = {"primary": {"usedPercent": 100}}
        bucket["credits"] = {"balance": "0", "hasCredits": False}
        payload["rateLimits"] = {"primary": {"usedPercent": 100}}
    return json.dumps(payload, indent=2)


CASES = {
    "a": {"kind": "complete", "request": FIX_REQUEST},
    "b": {
        "kind": "complete",
        "snapshot": snapshot(60, 50, extra_bucket=True),
        "request": "Use at most 10% of my remaining included allowance. " + FIX_REQUEST,
    },
    "c": {
        "kind": "unchanged",
        "snapshot": snapshot(100),
        "request": FIX_REQUEST,
    },
    "d": {
        "kind": "checkpoint",
        "checkpoint_used": 64,
        "snapshot": snapshot(60),
        "request": (
            "Use at most 10% of my remaining allowance. " + FIX_REQUEST
            + " Use python run_checks.py to run the tests; that fixture runner updates "
            "usage.json with my next synthetic snapshot when the tests pass. "
            "After the required fix and verification, optionally create examples.md "
            "with three usage examples if the allowance permits."
        ),
    },
    "e": {"kind": "question", "request": "Use low-credit mode."},
    "f": {
        "kind": "unchanged",
        "snapshot": snapshot(60),
        "request": "Use 0% of my remaining allowance. " + FIX_REQUEST,
    },
    "g": {
        "kind": "checkpoint",
        "checkpoint_used": 63,
        "snapshot": snapshot(60),
        "request": (
            "Use at most 10% of my remaining allowance. " + FIX_REQUEST
            + " Use python run_checks.py to run the tests; that fixture runner updates "
            "usage.json with my next synthetic snapshot when the tests pass. "
            "After the required fix and verification, optionally create examples.md "
            "with three usage examples if the allowance permits."
        ),
    },
    "h": {
        "kind": "unchanged",
        "snapshot": snapshot(60),
        "request": "Use 200% of my remaining allowance. " + FIX_REQUEST,
    },
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(case_id=None):
    selected = {case_id: CASES[case_id]} if case_id else CASES
    for selected_id in selected:
        if (RUNS / selected_id).exists():
            raise SystemExit(f"Refusing to overwrite existing trial artifacts: {RUNS / selected_id}")
    RUNS.mkdir(parents=True, exist_ok=True)
    for case_id, case in selected.items():
        workspace = RUNS / case_id
        workspace.mkdir()
        request = f"Use $low-credit-mode from {SKILL.as_posix()}.\n\n"
        if "snapshot" in case:
            request += (
                "For this dry run, I am supplying synthetic quota readings in usage.json. "
                "These are user-provided simulation data, not live account telemetry. "
                "The active quota bucket is codex.\n\n"
            )
            (workspace / "usage.json").write_text(case["snapshot"] + "\n", encoding="utf-8")
        request += case["request"] + "\n"
        (workspace / "request.md").write_text(request, encoding="utf-8")
        if case["kind"] != "question":
            (workspace / "tags.py").write_text(BROKEN_SOURCE, encoding="utf-8")
            (workspace / "test_tags.py").write_text(TESTS, encoding="utf-8")
        if case["kind"] == "checkpoint":
            runner = CHECKPOINT_RUNNER.replace('"usedPercent": 64', f'"usedPercent": {case["checkpoint_used"]}')
            (workspace / "run_checks.py").write_text(runner, encoding="utf-8")
        baseline = {file.name: digest(file) for file in workspace.iterdir() if file.is_file()}
        (workspace / "baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        print(f"PREPARED {case_id}: {workspace}")
    print(f"Skill SHA256: {digest(SKILL)}")


def verify(case_id=None):
    selected = {case_id: CASES[case_id]} if case_id else {key: value for key, value in CASES.items() if (RUNS / key).exists()}
    if not selected:
        raise SystemExit("No prepared trials found; run prepare first")
    results = []
    for case_id, case in selected.items():
        workspace = RUNS / case_id
        baseline = json.loads((workspace / "baseline.json").read_text(encoding="utf-8"))
        checks = {"fixtures_preserved": True}
        for name, before in baseline.items():
            if name not in ("tags.py", "usage.json"):
                checks["fixtures_preserved"] &= (workspace / name).is_file() and digest(workspace / name) == before
        allowed = set(baseline) | {"baseline.json", "__pycache__"}
        if case["kind"] == "checkpoint":
            allowed.add("checkpoint-reached.txt")
        checks["no_unrequested_artifacts"] = all(item.name in allowed for item in workspace.iterdir())
        if case["kind"] in ("complete", "checkpoint"):
            check = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "-v", "test_tags.py"],
                cwd=workspace, text=True, capture_output=True, timeout=30,
            )
            checks["all_four_functional_tests_pass"] = check.returncode == 0
            checks["implementation_changed"] = digest(workspace / "tags.py") != baseline["tags.py"]
            (RUNS / f"{case_id}-verification.log").write_text(check.stdout + check.stderr, encoding="utf-8")
        elif case["kind"] == "unchanged":
            checks["implementation_untouched"] = digest(workspace / "tags.py") == baseline["tags.py"]
            checks["snapshot_untouched"] = digest(workspace / "usage.json") == baseline["usage.json"]
        if case["kind"] == "checkpoint":
            reading = json.loads((workspace / "usage.json").read_text(encoding="utf-8"))
            checks["checkpoint_reached"] = (workspace / "checkpoint-reached.txt").is_file()
            checks["snapshot_advanced_as_configured"] = reading["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"] == case["checkpoint_used"]
            checks["optional_examples_not_started"] = not (workspace / "examples.md").exists()
        passed = all(checks.values())
        results.append({"case": case_id, "artifact_checks_passed": passed, "checks": checks})
        print(f"{'PASS' if passed else 'FAIL'} artifacts {case_id}: {json.dumps(checks)}")
    output = {"skill_sha256": digest(SKILL), "cases": results}
    (RUNS / "artifact-results.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print("Artifact checks do not grade final responses, quota calculations, skill selection, or token savings.")
    if not all(result["artifact_checks_passed"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--case", choices=tuple(CASES), help="Prepare or verify one trial")
    arguments = parser.parse_args()
    if arguments.action == "prepare":
        prepare(arguments.case)
    else:
        verify(arguments.case)
