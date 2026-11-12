"""Check installed-skill metadata and the actual distributable archive."""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/low-credit-mode"
SPEC = importlib.util.spec_from_file_location("build_release", ROOT / "tools/build_release.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class MetadataTests(unittest.TestCase):
    def test_frontmatter_and_interface_are_valid_yaml(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(frontmatter["name"], "low-credit-mode")
        self.assertEqual(frontmatter["license"], "MIT")
        self.assertIsInstance(frontmatter["description"], str)
        self.assertLessEqual(len(frontmatter["description"]), 1024)
        interface = yaml.safe_load((SKILL / "agents/openai.yaml").read_text(encoding="utf-8"))["interface"]
        self.assertEqual(interface["display_name"], "Low Credit Mode")
        self.assertTrue(25 <= len(interface["short_description"]) <= 64)
        self.assertIn("$low-credit-mode", interface["default_prompt"])

    def test_manifest_uses_public_identity_and_license(self):
        manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "low-credit-mode")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["license"], "MIT")
        self.assertEqual(manifest["author"]["name"], "iliass-coder")
        self.assertNotIn("email", manifest["author"])
        allowed_keys = {"$schema", "name", "version", "description", "author", "homepage", "repository", "license", "keywords", "extensions"}
        self.assertFalse(set(manifest) - allowed_keys)
        for field in ("homepage", "repository"):
            self.assertEqual(manifest[field], "https://github.com/iliass-coder/Low-credit-mode")

    def test_icon_references_exist_within_package(self):
        manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        interface = manifest["extensions"]["com.openai"]["interface"]
        for key in ("composerIcon", "logo"):
            path = (ROOT / interface[key]).resolve()
            self.assertTrue(path.is_relative_to(ROOT))
            self.assertEqual(ET.parse(path).getroot().tag, "{http://www.w3.org/2000/svg}svg")

    def test_standalone_skill_retains_mit_notice(self):
        self.assertEqual((ROOT / "LICENSE").read_bytes(), (SKILL / "LICENSE").read_bytes())
        self.assertIn("Permission is hereby granted", (SKILL / "LICENSE").read_text(encoding="utf-8"))

    def test_local_markdown_links_resolve(self):
        documents = [ROOT / name for name in builder.PUBLIC_PATHS if name.endswith(".md")]
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if target.startswith(("https://", "http://", "#")):
                    continue
                with self.subTest(document=document.name, target=target):
                    self.assertTrue((document.parent / target.split("#", 1)[0]).exists())

    def test_release_text_has_no_known_private_literal_patterns(self):
        patterns = (
            re.compile(r"[A-Z]:[\\/](?:Users|Program Files)[\\/]", re.I),
            re.compile(r"/(?:Users|home)/[^/\s]+/"),
            re.compile(r"\b(?:gh[pousr]_|github_pat_|sk-)[A-Za-z0-9_-]{20,}\b"),
            re.compile(r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY"),
        )
        for relative in builder.PUBLIC_PATHS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for pattern in patterns:
                self.assertIsNone(pattern.search(text), f"Potential private literal in {relative}; inspect locally")

    def test_ci_has_read_only_permissions_and_pinned_actions(self):
        # BaseLoader preserves GitHub's YAML 1.2 'on' key as a string.
        workflow = yaml.load((ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertIn("push", workflow["on"])
        self.assertIn("pull_request", workflow["on"])
        steps = workflow["jobs"]["test"]["steps"]
        for step in steps:
            if "uses" in step:
                self.assertRegex(step["uses"], r"@[0-9a-f]{40}$")
        self.assertEqual(steps[0]["with"]["persist-credentials"], "false")


class ArchiveTests(unittest.TestCase):
    def test_archive_is_reproducible_and_contains_only_public_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = builder.build_archive(ROOT, Path(temporary) / "first")
            second = builder.build_archive(ROOT, Path(temporary) / "second")
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as archive:
                expected = {f"low-credit-mode/{path}" for path in builder.PUBLIC_PATHS}
                self.assertEqual(set(archive.namelist()), expected)
                self.assertIsNone(archive.testzip())
                for name in archive.namelist():
                    self.assertNotIn("..", Path(name).parts)
                    self.assertFalse(Path(name).is_absolute())

    def test_unlisted_local_files_are_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "source"
            for relative in builder.PUBLIC_PATHS:
                target = fixture / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            (fixture / ".env").write_text("SYNTHETIC_LOCAL_ONLY=value", encoding="utf-8")
            (fixture / "private-run.json").write_text("{}", encoding="utf-8")
            result = builder.build_archive(fixture, Path(temporary) / "output")
            with zipfile.ZipFile(result) as archive:
                self.assertFalse(any(name.endswith((".env", "private-run.json")) for name in archive.namelist()))

    def test_missing_required_source_fails_before_building(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            shutil.copyfile(ROOT / "plugin.json", root / "plugin.json")
            with self.assertRaises(ValueError):
                builder.build_archive(root, Path(temporary) / "output")
            self.assertFalse((Path(temporary) / "output").exists())


if __name__ == "__main__":
    unittest.main()
