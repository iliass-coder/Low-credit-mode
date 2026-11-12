---
name: low-credit-mode
description: Conserve remaining AI allowance while completing a task. Use when the user requests low-credit mode, says usage is nearly exhausted, or asks to finish within remaining allowance. Do not activate for discussions about pricing or building budget tools.
license: MIT
---

# Low Credit Mode

Prioritize the user's essential result and required verification. Reduce optional exploration, repeated checks, and polish. Preserve the requested scope; obtain agreement before reducing the deliverable. Budget targets guide execution and cannot reserve credits, enforce a cap, interrupt an in-flight call, or guarantee completion.

## Establish the task and allowance

1. Apply to the current task. If no task is identifiable, ask what to do before reading usage; do not start a monitoring loop.
2. Discover an available read-only usage reader. Prefer the host's `get_usage_limits` when exposed. Use existing permissions; do not install helpers, sign into accounts, buy credits, consume reset entitlements, or change settings to activate this mode.
3. If no reader is available or it fails, briefly disclose that live allowance is unknown. Use a user-provided snapshot if supplied and label it accordingly; otherwise proceed conservatively without claiming a measured budget.
4. Prefer a non-null `rateLimitsByLimitId` map. Select the bucket known to apply to the current model/task; ignore unrelated exhausted buckets. If several buckets exist and relevance is unclear, treat the allowance as unknown. Use legacy `rateLimits` only when the preferred map is absent or null. An empty, malformed, or nonmatching preferred map stays unknown; it must not be replaced by a favorable legacy reading.
5. Keep each primary/secondary window separate. A valid `usedPercent` is a finite number, excluding booleans and numeric strings. Clamp valid numbers to 0–100 before calculating. Missing, null, or invalid readings remain unknown; never treat them as zero usage. A known exhausted relevant window prevents new substantive work even when another window is unknown.
6. Keep additional `credits.balance` separate from included allowance. A zero additional balance does not mean included allowance is exhausted. Do not translate percentages into dollars, exact credits, or predicted task capacity.

Briefly state the known or unknown allowance, essential outcome, and economical approach. Avoid a long activation plan or repeating the same disclosure at every checkpoint.

## Set a working budget

When the user allocates a fraction `p` of the remainder, require a finite number between 0 and 1. For example, 10% means `p = 0.10`. Ask to correct negative, nonfinite, or greater-than-100% allocations; do not silently clamp an invalid allocation or start the requested substantive work first. A zero allocation means no new substantive work, even if usage itself is unknown.

For each applicable window with validated baseline usage `u0`:

```text
allocation = (100 - u0) * p
target_used = u0 + allocation
finalize_used = u0 + 0.70 * allocation
```

At 60% used, allocating 10% of the remainder gives 4 percentage points, a target of 64% used, and an early-finalization trigger of 62.8% used.

Without an explicit fraction, use `p = 1` only as a planning baseline. It is not a requirement to consume all remaining allowance. Finalize earlier when capacity is very low or uncertain. The 30% headroom is a heuristic, not a protected reserve.

For complex readings or checkpoint comparisons, the optional [budget helper](scripts/budget.py) provides validated calculations using Python 3.11+ and no third-party packages. It reads JSON on stdin and writes JSON to stdout; it does not fetch usage or persist it. See [the input format](references/budget-input.md) only when using the helper. If Python is unavailable, apply the rules directly without installing dependencies.

## Work and recheck

- Deliver essential work first, with checks that establish correctness. Batch independent reads, bound output, and avoid repeating completed checks without new evidence. Do not write progress documents for simple tasks.
- Save useful artifacts incrementally in their normal outputs. Keep real account identifiers, balances, and usage snapshots out of repository files, issue reports, and shared notes.
- Recheck after meaningful milestones and before expensive optional work or retries. Do not poll while idle or check after trivial steps; reading tools and instructions also consumes resources.
- Compare each current window against its original baseline and trigger. Do not add windows' percentages or attribute all account consumption to this task.
- At an early-finalization trigger, stop optional work and complete the most valuable viable output and essential checks. At the target or known exhaustion, launch no further substantive work; return saved results and identify what remains.
- If a reader fails, a previously present window disappears, the reader source changes, or values become invalid, treat headroom as unknown and favor finalization. If usage drops, reset time changes, or a new window appears, reconcile once when useful. Do not grant a new allocation or reset the baseline silently.
- Respect the host's permissions and hard limits. Do not silently change models, spawn agents without separate authorization, or retry indefinitely. This mode gives no extra execution permissions.

## Report the result

Lead with the result and material verification. Distinguish completed, unverified, and unfinished work. Include a latest allowance snapshot only when useful and label its source. Never claim that credits were reserved, a spending cap was enforced, savings were measured without a comparison, or these instructions have a proven reliability rate.
