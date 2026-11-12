# Compatibility and troubleshooting

## Supported installation

The package follows Codex's filesystem skill layout. Install the complete `skills/low-credit-mode` directory in a supported skills location. Codex CLI and the IDE extension expose explicit skill invocation with `$`. Your host's version, settings, and workspace policy determine availability. See the [official skill documentation](https://learn.chatgpt.com/docs/build-skills).

The repository's root `plugin.json` also packages the skill and icon for compatible local plugin hosts. Publishing the repository does not list it in an official plugin marketplace. Filesystem skill installation is the documented distribution route for this beta.

## Usage readings

| Environment | Behavior |
| --- | --- |
| Supported read-only usage tool exposed | The agent can read applicable quota windows at checkpoints. |
| No usage reader, or reader fails | The agent discloses unknown live allowance and works conservatively. |
| User supplies a reading | The agent labels it user-provided and treats it as a snapshot. |
| Multiple quota buckets with unclear relevance | Allowance stays unknown until relevance can be established. |
| Known exhaustion or zero requested allocation | No new substantive work is started. |

A skill cannot expose a usage tool that the host does not provide. This project includes no account API integration. Live integration has not been verified for any host in this beta.

## Optional helper

`skills/low-credit-mode/scripts/budget.py` requires Python 3.11+ and uses only its standard library. It validates supplied JSON and calculates decisions; it does not read account usage itself. If Python is unavailable, the skill applies the same rules directly without installing dependencies.

## Troubleshooting

**The skill does not appear.** Check that the destination contains `low-credit-mode/SKILL.md`, not an extra nested repository folder. Restart Codex and confirm skills are enabled by your workspace policy.

**Usage is unknown.** This is expected when no supported reader is exposed. You can supply a reading from your usage screen, explicitly labeled as your snapshot. Do not share account identifiers or credentials.

**The agent stopped early.** Check whether the requested allocation was zero, a relevant quota window was exhausted, or a finalization trigger was crossed. The agent should explain what was completed and what remains.

**A budget fraction was rejected.** The helper accepts numbers from 0 to 1. For a 10% allocation use `0.10`; in a chat prompt, write “10% of my remaining allowance.”

**The task needs more work than the budget allows.** The agent should preserve useful progress and report incomplete work. Agree on a smaller task or provide a new explicit allocation; a reset must not silently grant more budget.
