"""Tests for scripts/validate.py: the real package passes, and each kind of mistake is caught.

    python3 -m unittest discover -s scripts -p "test_*.py"
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


class ValidateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "pkg"
        shutil.copytree(REPO, self.root, ignore=shutil.ignore_patterns(".git"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def edit_json(self, rel: str, change) -> None:
        path = self.root / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def errors(self) -> list[str]:
        return validate.validate(self.root).errors

    def assertCaught(self, fragment: str) -> None:
        errors = self.errors()
        self.assertTrue(any(fragment in e for e in errors), f"{fragment!r} not in {errors}")

    def test_the_package_is_valid(self) -> None:
        self.assertEqual(self.errors(), [])

    def test_unknown_manifest_field(self) -> None:
        self.edit_json("plugin.json", lambda d: d.update(skills="skills/"))
        self.assertCaught("unknown top-level field 'skills'")

    def test_headers_are_refused(self) -> None:
        self.edit_json(
            "mcp.json",
            lambda d: d["mcpServers"]["radiate"].update(headers={"X-API-Key": "x"}),
        )
        self.assertCaught("no headers, no credentials")

    def test_other_hosts_and_plain_http_are_refused(self) -> None:
        for url in ("http://mcp.radiatestudio.ai/mcp", "https://mcp.example.com/mcp"):
            self.edit_json("mcp.json", lambda d, u=url: d["mcpServers"]["radiate"].update(url=u))
            self.assertCaught("url must be https")

    def test_the_hermes_server_must_stay_untrusted(self) -> None:
        def change(d):
            d["extensions"][validate.HERMES]["servers"]["radiate"]["trust"] = "full"

        self.edit_json("plugin.json", change)
        self.assertCaught("trust must be 'untrusted'")

    def test_costs_cover_only_compute_tools_within_the_per_call_cap(self) -> None:
        def change(d):
            costs = d["extensions"][validate.HERMES]["servers"]["radiate"]["costs"]
            costs["list_projects"] = 1
            costs["generate_video"] = [20, 9000]

        self.edit_json("plugin.json", change)
        self.assertCaught("list_projects: is not a compute tool")
        self.assertCaught("above the per-call cap")

    def test_skill_frontmatter_rules(self) -> None:
        path = self.root / "skills" / "radiate-image" / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("name: radiate-image", "name: radiate-images"), encoding="utf-8")
        self.assertCaught("name must equal the folder name")
        path.write_text(text.replace("version: 0.1.0", "metadata: {openclaw: {}}"), encoding="utf-8")
        self.assertCaught("frontmatter must be flat")

    def test_unknown_tool_in_a_skill(self) -> None:
        path = self.root / "skills" / "radiate-video" / "SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nCall `generate_movie`.\n", encoding="utf-8")
        validate.sync(self.root)
        self.assertCaught("'generate_movie', which tools/inventory.json does not list")

    def test_claude_code_copy_must_match(self) -> None:
        path = self.root / "claude-code" / "skills" / "radiate-audio" / "SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
        self.assertCaught("differs from skills/")

    def test_no_claude_marker_at_the_root(self) -> None:
        (self.root / ".claude-plugin").mkdir()
        self.assertCaught("must not exist at the root")

    def test_high_risk_tools_never_default(self) -> None:
        self.edit_json("tools/default-tools.json", lambda d: d["groups"]["jobs"].append("blender_live_command"))
        self.assertCaught("is high_risk and may never be on by default")

    def test_credentials_are_caught(self) -> None:
        fake = "sk-ant-" + "a" * 30
        (self.root / "notes.md").write_text(f"key: {fake}\n", encoding="utf-8")
        self.assertCaught("OpenAI/Anthropic-style key")


if __name__ == "__main__":
    unittest.main()
