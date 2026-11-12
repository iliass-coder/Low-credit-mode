# Budget helper

Use this optional helper when quota selection, input validation, or multiple checkpoints make manual calculations error-prone. It requires Python 3.11+ and only its standard library. It does not connect to an account, install anything, write files, or collect telemetry.

Pass one JSON object on stdin to `python scripts/budget.py`, using the script path relative to the installed skill directory. The fields are:

| Field | Meaning |
| --- | --- |
| `baseline` | The original host or user-provided usage snapshot. Required; may be null if unknown. |
| `current` | The latest snapshot. Include it for a checkpoint comparison. |
| `fraction` | Optional number from 0 to 1. `0.10` allocates 10% of the remainder; omission uses the planning default. |
| `limit_id` | The known relevant preferred-map key. Required when a map contains multiple buckets. |

Example input, with synthetic readings:

```json
{
  "baseline": {"rateLimitsByLimitId": {"codex": {"primary": {"usedPercent": 60}}}},
  "current": {"rateLimitsByLimitId": {"codex": {"primary": {"usedPercent": 63}}}},
  "fraction": 0.10,
  "limit_id": "codex"
}
```

This returns `action: "finalize"`, with a 62.8% early-finalization trigger and 64% target. It does not stop the running model or enforce the target.

| Action | Agent behavior |
| --- | --- |
| `continue` | Continue the essential task; complete it as soon as ready. |
| `conserve` | Baseline allowance is unknown or partial. Continue conservatively without claiming a measured budget. |
| `finalize` | Stop optional exploration and deliver the most useful viable result, retaining essential checks. |
| `stop` | Start no new substantive work; return saved results and explain incomplete work. |
| `reconcile` | Headroom or window identity changed. Read once more if useful; do not silently reset the budget. Favor finalization if uncertainty remains. |

Invalid input or a fraction outside 0–1 returns an error with exit code 2. Success returns exit code 0, including when the calculated action is `stop`. Unknown allowance is represented explicitly, not as zero.

Keep real readings transient. Do not commit helper inputs or outputs containing account usage. Local permissions, host approvals, and the user's requested scope still apply.
