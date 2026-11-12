"""Validate quota snapshots and calculate conservative working budgets.

Python 3.11+, standard library only. Reads one JSON object from stdin and
writes a sanitized result to stdout. Makes no network requests or file writes.
Quota percentages describe allowance windows, not money or exact task costs.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from typing import Any


WINDOW_NAMES = ("primary", "secondary")
MAX_INPUT_BYTES = 1_048_576


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _fraction(value: Any) -> Decimal:
    number = _number(value)
    if number is None or not 0 <= number <= 1:
        raise ValueError("fraction must be a finite number between 0 and 1, for example 0.10 for 10%")
    return number


def _json_number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _credits(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    balance = value.get("balance")
    if isinstance(balance, str):
        if len(balance) > 80:
            return None
        try:
            balance = Decimal(balance)
        except InvalidOperation:
            return None
    number = _number(balance)
    if number is None or number < 0 or number.adjusted() > 80:
        return None
    return str(number)


def read_snapshot(payload: Any, limit_id: str | None = None) -> dict[str, Any]:
    """Select one relevant bucket without falling back from an unusable map.

    A missing or null preferred map permits the legacy reader. An empty,
    malformed, ambiguous, or nonmatching map does not. Unknown windows are
    retained so that a partial reading cannot silently become a full budget.
    """
    if limit_id is not None and (not isinstance(limit_id, str) or not limit_id.strip()):
        raise ValueError("limit_id must be a nonempty string when supplied")
    result: dict[str, Any] = {
        "status": "unknown", "source": "unknown", "limit_id": limit_id,
        "windows": {}, "additional_credits_balance": None, "reason": None,
    }
    if not isinstance(payload, dict):
        result["reason"] = "invalid_snapshot"
        return result
    preferred = payload.get("rateLimitsByLimitId")
    if preferred is not None:
        result["source"] = "preferred"
        if not isinstance(preferred, dict) or not preferred:
            result["reason"] = "unusable_preferred_map"
            return result
        if limit_id is None:
            if len(preferred) != 1:
                result["reason"] = "ambiguous_limit_id"
                return result
            limit_id = next(iter(preferred))
            result["limit_id"] = limit_id
        bucket = preferred.get(limit_id)
        if not isinstance(bucket, dict):
            result["reason"] = "missing_limit_bucket"
            return result
    else:
        result["source"] = "legacy"
        bucket = payload.get("rateLimits")
        if not isinstance(bucket, dict):
            result["reason"] = "missing_legacy_reading"
            return result
    result["additional_credits_balance"] = _credits(bucket.get("credits"))
    for name in WINDOW_NAMES:
        if name not in bucket:
            continue
        raw = bucket[name]
        window: dict[str, Any] = {"status": "unknown"}
        if isinstance(raw, dict):
            used = _number(raw.get("usedPercent"))
            if used is not None:
                used = min(Decimal(100), max(Decimal(0), used))
                window.update(status="known", used_percent=_json_number(used), remaining_percent=_json_number(100 - used))
            for field in ("windowDurationMins", "resetsAt"):
                number = _number(raw.get(field))
                if number is not None and number >= 0:
                    window[field] = _json_number(number)
        result["windows"][name] = window
    known = sum(window["status"] == "known" for window in result["windows"].values())
    if known:
        result["status"] = "known" if known == len(result["windows"]) else "partial"
    result["reason"] = None if result["status"] == "known" else "unknown_or_missing_windows"
    return result


def make_plan(payload: Any, fraction: int | float | Decimal | None = None, limit_id: str | None = None) -> dict[str, Any]:
    """Use p=1 as a working baseline when no user fraction was provided."""
    p = _fraction(1 if fraction is None else fraction)
    snapshot = read_snapshot(payload, limit_id)
    plan: dict[str, Any] = {
        "status": snapshot["status"], "snapshot": snapshot,
        "fraction": _json_number(p), "fraction_specified": fraction is not None,
        "windows": {}, "action": "conserve", "reason": snapshot["reason"],
    }
    for name, window in snapshot["windows"].items():
        if window["status"] != "known":
            continue
        used = Decimal(str(window["used_percent"]))
        allocation = (100 - used) * p
        plan["windows"][name] = {
            "baseline_used": _json_number(used), "allocation": _json_number(allocation),
            "target_used": _json_number(used + allocation),
            "finalize_used": _json_number(used + Decimal("0.70") * allocation),
        }
    if p == 0 or any(window["allocation"] == 0 for window in plan["windows"].values()):
        plan.update(action="stop", reason="zero_allocation_or_exhausted")
    elif snapshot["status"] == "known":
        plan.update(action="continue", reason="below_finalization_trigger")
    return plan


def assess_checkpoint(baseline: Any, current: Any, fraction: int | float | Decimal | None = None, limit_id: str | None = None) -> dict[str, Any]:
    """Compare each current window to the original baseline, never a new cap.

    Reconcile when a reset, changed window, or newly appearing window is
    detected. Unknown readings favor finalization. A known exhausted window
    or reached target always stops new substantive work.
    """
    plan = make_plan(baseline, fraction, limit_id)
    outcome: dict[str, Any] = {"action": "finalize", "reason": "unknown_headroom", "plan": plan}
    if plan["action"] == "stop":
        outcome.update(action="stop", reason=plan["reason"])
        return outcome
    selected_id = plan["snapshot"]["limit_id"]
    latest = read_snapshot(current, selected_id)
    outcome["current"] = latest
    before_windows = plan["snapshot"]["windows"]
    after_windows = latest["windows"]
    for name, window in after_windows.items():
        if window["status"] == "known" and window["remaining_percent"] == 0:
            outcome.update(action="stop", reason="exhausted_window")
            return outcome
    if latest["source"] == plan["snapshot"]["source"]:
        for name, window in plan["windows"].items():
            before = before_windows[name]
            after = after_windows.get(name, {})
            comparable = (
                after.get("status") == "known"
                and after["used_percent"] >= before["used_percent"]
                and all(field not in before or after.get(field) == before[field]
                        for field in ("resetsAt", "windowDurationMins"))
            )
            if comparable and after["used_percent"] >= window["target_used"]:
                outcome.update(action="stop", reason="target_reached")
                return outcome
    if plan["status"] != "known":
        outcome.update(action="reconcile", reason="baseline_unknown")
        return outcome
    if latest["source"] != plan["snapshot"]["source"]:
        outcome.update(action="reconcile", reason="reader_source_changed")
        return outcome
    if any(name not in after_windows or after_windows[name]["status"] != "known" for name in before_windows):
        return outcome
    if any(name not in before_windows for name in after_windows):
        outcome.update(action="reconcile", reason="new_window")
        return outcome
    for name, before in before_windows.items():
        after = after_windows[name]
        if after["used_percent"] < before["used_percent"]:
            outcome.update(action="reconcile", reason="possible_reset")
            return outcome
        for field in ("resetsAt", "windowDurationMins"):
            if field in before and (field not in after or after[field] != before[field]):
                outcome.update(action="reconcile", reason="window_changed")
                return outcome
    if any(after_windows[name]["used_percent"] >= window["target_used"] for name, window in plan["windows"].items()):
        outcome.update(action="stop", reason="target_reached")
    elif any(after_windows[name]["used_percent"] >= window["finalize_used"] for name, window in plan["windows"].items()):
        outcome.update(action="finalize", reason="early_finalization_trigger")
    else:
        outcome.update(action="continue", reason="below_finalization_trigger")
    return outcome


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite JSON number")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        data = sys.stdin.read(MAX_INPUT_BYTES + 1)
        if len(data.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ValueError("input exceeds 1 MiB")
        request = json.loads(data, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
        if not isinstance(request, dict) or "baseline" not in request:
            raise ValueError("supply an object with baseline, optional current, fraction, and limit_id")
        if "fraction" in request:
            _fraction(request["fraction"])
        options = {"fraction": request.get("fraction"), "limit_id": request.get("limit_id")}
        if "current" in request:
            result = assess_checkpoint(request["baseline"], request["current"], **options)
        else:
            result = make_plan(request["baseline"], **options)
        json.dump(result, sys.stdout, ensure_ascii=True, allow_nan=False, indent=2)
        sys.stdout.write("\n")
        return 0
    except (ValueError, TypeError, RecursionError) as error:
        json.dump({"error": str(error)}, sys.stdout)
        sys.stdout.write("\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
