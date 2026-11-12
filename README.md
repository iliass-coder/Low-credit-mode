<p align="center"><img src="assets/icon.svg" width="72" height="72" alt="Low Credit Mode battery icon"></p>

# Low Credit Mode

**Keep AI work focused when your allowance is running low.**

A free, MIT-licensed skill for Codex. It prioritizes the essential result, reduces optional exploration, and begins wrapping up early when a working usage budget is nearly consumed.

**Public beta · v0.2.0** — budget targets are best effort. Live readings depend on your host; a hard spending cap and measured savings are not provided.

[Get started](#install) · [Examples](#use) · [Compatibility](docs/compatibility.md) · [Testing](docs/evaluation.md) · [Report an issue](https://github.com/iliass-coder/Low-credit-mode/issues)

## Install

In Codex, send:

```text
Use $skill-installer to install https://github.com/iliass-coder/Low-credit-mode/tree/main/skills/low-credit-mode
```

If your host does not include the skill installer, download or clone this repository and copy the entire `skills/low-credit-mode` folder into either:

| Scope | Destination |
| --- | --- |
| One project | `<project>/.agents/skills/low-credit-mode` |
| Your user | `~/.agents/skills/low-credit-mode` |

Keep `SKILL.md`, `agents/`, `scripts/`, `references/`, and `LICENSE` together. Restart Codex if the skill does not appear. Type `$` to find it in the skill selector. [Official Codex skill documentation](https://learn.chatgpt.com/docs/build-skills) describes discovery and installation locations.

The skill requires a host with Codex skill support. Its optional calculation helper needs Python 3.11+; the instructions also work without Python. The package adds no account, API key, or subscription requirement of its own. Your AI host's normal access and billing still apply.

## Use

Supply a concrete task:

```text
$low-credit-mode Fix the failing login test and run the relevant checks.
```

Give a working allocation when needed:

```text
$low-credit-mode Use at most 10% of my remaining allowance to review this project and fix the most important issue.
```

Supply a reading when your host cannot expose usage:

```text
$low-credit-mode My usage screen shows 60% used. Treat that as a user-provided snapshot, use 10% of the remainder, and finish the release notes.
```

A percentage budget applies to what remains. At **60% used**, allocating **10% of the remainder** gives **4 percentage points**, a **64% target**, and a **62.8% early-finalization trigger**.

## What to expect

- Essential work and necessary verification come first. Optional alternatives, repeated checks, and extra polish are reduced.
- When a supported usage reader is available, the agent checks relevant quota windows at meaningful milestones.
- When readings are unavailable, it says so and works conservatively. It does not invent a balance.
- A zero allocation or exhausted relevant window prevents new substantive work. Changes, resets, or missing readings do not silently create a new budget.
- The agent preserves the requested scope and reports incomplete or unverified work honestly.

The skill applies to the current task. It can activate from an explicit request for low-credit mode or a request to finish within limited remaining usage. Discussing pricing or building a budget tool should not activate it.

## Limits and privacy

This is a skill package used inside your AI host. Its behavior depends on the model following its instructions. It cannot interrupt an in-flight call, reserve credits, or guarantee completion. Percentages are allowance readings, not exact dollars or task costs. For very small tasks, extra instructions and monitoring may outweigh any savings.

The optional helper validates quota data and calculations locally. It makes no network requests, writes no files, and collects no telemetry. The project operates no backend; your host processes prompts and files under its own terms and permissions. See [Privacy](PRIVACY.md) and [Compatibility](docs/compatibility.md).

## Development and support

The Python helper has no third-party runtime dependencies. From a source checkout, run the full development checks:

```text
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

[Testing and behavioral trials](docs/evaluation.md) explain what has and has not been verified. [Contributing](CONTRIBUTING.md) covers changes and release packaging. For bugs or feature requests, use [GitHub Issues](https://github.com/iliass-coder/Low-credit-mode/issues). Keep secrets and real account readings out of reports; see [Security](SECURITY.md).

Released under the [MIT License](LICENSE). Built and maintained by [iliass-coder](https://github.com/iliass-coder). This is an independent project and is not affiliated with or endorsed by OpenAI.
