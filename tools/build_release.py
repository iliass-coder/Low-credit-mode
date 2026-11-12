"""Build the public plugin archive from an explicit list of source files."""

import hashlib
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATHS = (
    "plugin.json", "README.md", "LICENSE", "PRIVACY.md", "SECURITY.md",
    "CONTRIBUTING.md", "CHANGELOG.md", "assets/icon.svg",
    "docs/compatibility.md", "docs/evaluation.md",
    "skills/low-credit-mode/SKILL.md", "skills/low-credit-mode/LICENSE",
    "skills/low-credit-mode/agents/openai.yaml",
    "skills/low-credit-mode/scripts/budget.py",
    "skills/low-credit-mode/references/budget-input.md",
)


def build_archive(root: Path, output_dir: Path) -> Path:
    root = root.resolve()
    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if manifest["name"] != "low-credit-mode" or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("invalid package name or version")
    contents = []
    for relative in sorted(PUBLIC_PATHS):
        path = root / relative
        if any((root / Path(*Path(relative).parts[:index])).is_symlink()
               for index in range(1, len(Path(relative).parts) + 1)):
            raise ValueError(f"symbolic link is not a release source: {relative}")
        if not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError(f"missing or unsafe release source: {relative}")
        contents.append((relative, path.read_bytes()))
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"low-credit-mode-{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for relative, data in contents:
            info = zipfile.ZipInfo(f"low-credit-mode/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, data, compresslevel=9)
    return archive


if __name__ == "__main__":
    result = build_archive(ROOT, ROOT / "dist")
    print(f"Built {result.name}")
    print(f"SHA256 {hashlib.sha256(result.read_bytes()).hexdigest()}")
