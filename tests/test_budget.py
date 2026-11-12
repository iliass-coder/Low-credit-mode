"""Behavior checks for real helper code, using synthetic quota snapshots."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/low-credit-mode/scripts/budget.py"
SPEC = importlib.util.spec_from_file_location("budget", SCRIPT)
budget = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(budget)


def reading(primary=60, secondary=None, **metadata):
    windows = {"primary": {"usedPercent": primary, **metadata}}
    if secondary is not None:
        windows["secondary"] = {"usedPercent": secondary}
    return {"rateLimitsByLimitId": {"codex": windows}}


class SnapshotTests(unittest.TestCase):
    def test_preferred_map_wins_over_contradictory_legacy(self):
        payload = reading(25)
        payload["rateLimits"] = {"primary": {"usedPercent": 100}}
        result = budget.read_snapshot(payload)
        self.assertEqual(result["windows"]["primary"]["remaining_percent"], 75)
        self.assertEqual(result["source"], "preferred")

    def test_unusable_preferred_maps_do_not_get_favorable_fallback(self):
        for preferred in ({}, [], "invalid", {"codex": None}):
            with self.subTest(preferred=preferred):
                result = budget.read_snapshot({"rateLimitsByLimitId": preferred, "rateLimits": {"primary": {"usedPercent": 0}}})
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["source"], "preferred")

    def test_missing_and_null_map_allow_legacy(self):
        for payload in ({"rateLimits": {"primary": {"usedPercent": 10}}}, {"rateLimitsByLimitId": None, "rateLimits": {"primary": {"usedPercent": 10}}}):
            self.assertEqual(budget.read_snapshot(payload)["windows"]["primary"]["remaining_percent"], 90)

    def test_multiple_buckets_require_relevance(self):
        payload = reading(30)
        payload["rateLimitsByLimitId"]["other"] = {"primary": {"usedPercent": 100}}
        self.assertEqual(budget.read_snapshot(payload)["reason"], "ambiguous_limit_id")
        self.assertEqual(budget.make_plan(payload, limit_id="codex")["action"], "continue")
        self.assertEqual(budget.read_snapshot(payload, "missing")["status"], "unknown")

    def test_invalid_usage_remains_unknown(self):
        for value in (None, True, False, "60", float("nan"), float("inf"), {}, []):
            with self.subTest(value=value):
                result = budget.read_snapshot(reading(value))
                self.assertEqual(result["status"], "unknown")
                self.assertNotIn("remaining_percent", result["windows"]["primary"])

    def test_valid_usage_is_clamped(self):
        for used, expected in ((-10, 100), (110, 0), (25.5, 74.5)):
            with self.subTest(used=used):
                result = budget.read_snapshot(reading(used))
                self.assertEqual(result["windows"]["primary"]["remaining_percent"], expected)

    def test_unknown_window_is_retained(self):
        payload = reading(40)
        payload["rateLimitsByLimitId"]["codex"]["secondary"] = None
        result = budget.read_snapshot(payload)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["windows"]["secondary"]["status"], "unknown")
        self.assertEqual(budget.make_plan(payload)["action"], "conserve")

    def test_zero_additional_balance_is_not_exhaustion(self):
        payload = reading(25)
        payload["rateLimitsByLimitId"]["codex"]["credits"] = {"balance": "0", "hasCredits": False}
        plan = budget.make_plan(payload)
        self.assertEqual(plan["snapshot"]["additional_credits_balance"], "0")
        self.assertEqual(plan["action"], "continue")

    def test_private_fields_and_invalid_balances_are_not_echoed(self):
        payload = reading(25)
        payload["accountId"] = "synthetic-account"
        payload["rateLimitsByLimitId"]["codex"]["credits"] = {"balance": "not a balance", "token": "synthetic-secret"}
        result = budget.read_snapshot(payload)
        self.assertIsNone(result["additional_credits_balance"])
        self.assertNotIn("synthetic-", json.dumps(result))

    def test_missing_payload_does_not_fabricate_allowance(self):
        for payload in (None, {}, [], "invalid", {"rateLimits": {}}):
            self.assertEqual(budget.read_snapshot(payload)["status"], "unknown")

    def test_invalid_limit_id_is_rejected(self):
        for limit_id in (True, 1, "", " "):
            with self.assertRaises(ValueError):
                budget.read_snapshot(reading(), limit_id)


class PlanningTests(unittest.TestCase):
    def test_fraction_applies_to_remainder(self):
        plan = budget.make_plan(reading(60), 0.10)
        self.assertEqual(plan["windows"]["primary"], {"baseline_used": 60, "allocation": 4, "target_used": 64, "finalize_used": 62.8})

    def test_no_fraction_is_an_explicitly_labeled_default(self):
        plan = budget.make_plan(reading(60))
        self.assertFalse(plan["fraction_specified"])
        self.assertEqual(plan["windows"]["primary"]["finalize_used"], 88)

    def test_each_window_gets_its_own_budget(self):
        plan = budget.make_plan(reading(20, 70), 0.1)
        self.assertEqual(plan["windows"]["primary"]["target_used"], 28)
        self.assertEqual(plan["windows"]["secondary"]["target_used"], 73)

    def test_invalid_fractions_are_rejected(self):
        for value in (-0.1, 1.1, 10, True, "0.1", float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                budget.make_plan(reading(), value)

    def test_zero_fraction_stops_even_with_unknown_usage(self):
        self.assertEqual(budget.make_plan(None, 0)["action"], "stop")

    def test_exhaustion_stops_even_with_another_unknown_window(self):
        payload = reading(100)
        payload["rateLimitsByLimitId"]["codex"]["secondary"] = None
        self.assertEqual(budget.make_plan(payload)["action"], "stop")

    def test_clamping_happens_before_budget_calculation(self):
        self.assertEqual(budget.make_plan(reading(-10), 0.1)["windows"]["primary"]["allocation"], 10)

    def test_threshold_ordering_for_valid_inputs(self):
        for used in (0, 0.1, 25, 60, 99.9, 100):
            for fraction in (0, 0.01, 0.1, 0.5, 1):
                with self.subTest(used=used, fraction=fraction):
                    window = budget.make_plan(reading(used), fraction)["windows"]["primary"]
                    self.assertLessEqual(used, window["finalize_used"])
                    self.assertLessEqual(window["finalize_used"], window["target_used"])
                    self.assertLessEqual(window["target_used"], 100)


class CheckpointTests(unittest.TestCase):
    def test_before_trigger_continues(self):
        self.assertEqual(budget.assess_checkpoint(reading(60), reading(62), 0.1)["action"], "continue")

    def test_exact_trigger_finalizes(self):
        result = budget.assess_checkpoint(reading(60), reading(62.8), 0.1)
        self.assertEqual((result["action"], result["reason"]), ("finalize", "early_finalization_trigger"))

    def test_before_target_finalizes(self):
        self.assertEqual(budget.assess_checkpoint(reading(60), reading(63), 0.1)["action"], "finalize")

    def test_target_stops(self):
        self.assertEqual(budget.assess_checkpoint(reading(60), reading(64), 0.1)["action"], "stop")

    def test_any_relevant_window_can_trigger_finalization(self):
        self.assertEqual(budget.assess_checkpoint(reading(20, 70), reading(25, 92))["action"], "finalize")

    def test_missing_or_invalid_current_window_favors_finalization(self):
        for current in (reading(None), {"rateLimitsByLimitId": {"codex": {}}}):
            self.assertEqual(budget.assess_checkpoint(reading(60), current, 0.1)["action"], "finalize")

    def test_reset_does_not_grant_a_new_budget(self):
        self.assertEqual(budget.assess_checkpoint(reading(60), reading(5), 0.1)["action"], "reconcile")

    def test_changed_or_missing_window_identity_requires_reconciliation(self):
        baseline = reading(60, resetsAt=1000, windowDurationMins=300)
        for current in (reading(61, resetsAt=2000, windowDurationMins=300), reading(61)):
            self.assertEqual(budget.assess_checkpoint(baseline, current, 0.1)["action"], "reconcile")

    def test_new_window_requires_reconciliation(self):
        self.assertEqual(budget.assess_checkpoint(reading(60), reading(61, 25), 0.1)["action"], "reconcile")

    def test_reader_source_change_does_not_reset_baseline(self):
        legacy = {"rateLimits": {"primary": {"usedPercent": 61}}}
        self.assertEqual(budget.assess_checkpoint(reading(60), legacy, 0.1)["action"], "reconcile")

    def test_current_exhaustion_stops_even_without_known_baseline(self):
        self.assertEqual(budget.assess_checkpoint(None, reading(100), limit_id="codex")["action"], "stop")

    def test_known_reached_target_stops_when_other_window_disappears(self):
        self.assertEqual(budget.assess_checkpoint(reading(60, 50), reading(64), 0.1)["action"], "stop")

    def test_known_reached_target_stops_with_partial_baseline(self):
        baseline = reading(60)
        baseline["rateLimitsByLimitId"]["codex"]["secondary"] = None
        self.assertEqual(budget.assess_checkpoint(baseline, reading(64, 50), 0.1)["action"], "stop")


class CommandLineTests(unittest.TestCase):
    def invoke(self, text):
        return subprocess.run([sys.executable, "-B", str(SCRIPT)], input=text, text=True, capture_output=True, timeout=10)

    def test_json_input_produces_a_decision(self):
        result = self.invoke(json.dumps({"baseline": reading(60), "current": reading(63), "fraction": 0.1}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "finalize")

    def test_invalid_input_returns_a_bounded_error_without_traceback(self):
        for data in ("", "{", "[]", '{"baseline": null, "fraction": -1}', '{"baseline": null, "fraction": NaN}', '{"baseline": null, "fraction": null}', '{"baseline": null, "fraction": 0.1, "fraction": 1}'):
            with self.subTest(data=data):
                result = self.invoke(data)
                self.assertEqual(result.returncode, 2)
                self.assertIn("error", json.loads(result.stdout))
                self.assertEqual(result.stderr, "")

    def test_help_does_not_require_stdin(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("stdin", result.stdout)


if __name__ == "__main__":
    unittest.main()
