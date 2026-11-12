# Testing and evidence

## Automated checks

From a source checkout, run:

```text
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Checks exercise the actual helper and command-line interface: preferred and legacy readings, ambiguous buckets, invalid values, additional credits, independent windows, remainder-based budgets, zero allocations, early finalization, target stops, resets, missing readings, bounded errors, package metadata, and release contents. Synthetic fixtures are used; no model or account APIs are called by the test suite.

## Behavioral trials

Behavioral testing requires a real assistant run; passing arithmetic tests alone does not establish that an agent follows the skill. Use a fresh context, the skill, a realistic request, and an isolated workspace. Define expected observable outcomes before running it. Keep the expected answers and grader out of the acting assistant's context.

The reusable trial preparer provides small coding tasks and explicitly labeled synthetic quota snapshots:

```text
python tools/behavioral_suite.py prepare
```

Give each generated `.local/behavioral-runs/<case>/request.md` to a fresh assistant context. Limit file writes to that workspace. Preserve the tests and fixture runners. Afterward run:

```text
python tools/behavioral_suite.py verify
```

Review the assistant's response and actual tool record separately. The file verifier cannot establish that allowance was disclosed correctly or that activation happened for the right reason. Generated workspaces, raw traces, and usage snapshots remain ignored and should not be committed.

## Evidence and limits

Version 0.1.0 was exercised in seven one-shot independent contexts. Selected outcomes matched expectations: a real defect was repaired under available work budgets; exhausted/zero budgets left code untouched; no task produced a clarification; and optional work was skipped after early finalization. Those quota-driven trials used synthetic user-provided readings and were not live host integration tests.

Version 0.2.0 adds validated deterministic calculations and more explicit edge-case rules. Three fresh independent contexts also matched their selected checks: completing a real repair without a usage reader, stopping optional work at 63% after a 62.8% trigger, and asking to correct a 200% allocation before editing code. The two repair trials each passed four unchanged functional tests. Inputs were synthetic where quota readings were supplied; source and output files were verified separately. Raw assistant records are kept outside the public package.

Each behavioral scenario was run once. These smoke tests are not a reliability rate or evidence of monetary savings.

Live usage integration, automatic activation quality, long-running behavior, exact budget enforcement, and actual credit savings remain unverified. A paired comparison with and without the skill, repeated over representative tasks, is needed before publishing savings claims. For very short tasks, the skill's overhead could exceed its savings.
