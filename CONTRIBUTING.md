# Contributing

Focused bug reports, documentation improvements, and reproducible regression tests are welcome. For substantial changes, open an issue first to agree on scope.

## Run checks

From a source checkout, use Python 3.11+:

```text
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Runtime code uses only the standard library. Development dependencies validate YAML metadata. Tests make no model or account API calls and use synthetic quota readings.

When changing the skill's decisions, add a regression case and follow the [behavioral testing guidance](docs/evaluation.md). Do not publish raw model transcripts or account telemetry. Keep prompt changes concise; added instructions also consume context.

## Build a distributable

```text
python tools/build_release.py
```

This creates a versioned ZIP in `dist/` using an explicit list of public files. Internal trial workspaces, test outputs, caches, editor settings, and credentials are excluded. The archive is reproducible for identical source files and the same Python/compression runtime. Generated archives are not committed.

Before publishing a new version, update `plugin.json` and `CHANGELOG.md`, run the checks, inspect the archive contents, and complete any behavioral trials warranted by the changes. Do not claim live quota integration or savings without evidence.

## Pull requests

Explain the user-visible problem, resulting behavior, and relevant verification. Keep unrelated formatting and refactoring separate. Contributions are provided under the project's [MIT License](LICENSE).
