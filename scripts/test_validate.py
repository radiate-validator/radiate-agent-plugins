"""Tests for scripts/validate.py: the real package passes, and each kind of mistake is caught.

    python3 -m unittest discover -s scripts -p "test_*.py"
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
# Literal paths, not validate.* names, so these tests fail (not error) on a validator without them.
OPENCLAW_SERVER = "openclaw/radiate.json"
OPENCLAW_TOKEN_REQUEST = "openclaw/connection-token-request.json"


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
        version = json.loads((REPO / "plugin.json").read_text(encoding="utf-8"))["version"]
        path.write_text(text.replace(f"version: {version}", "metadata: {openclaw: {}}"), encoding="utf-8")
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

    # OpenClaw connects with a Radiate connection token, never OAuth (Eric 2026-11-11).

    def test_openclaw_sends_the_token_from_an_env_var(self) -> None:
        server = json.loads((REPO / OPENCLAW_SERVER).read_text(encoding="utf-8"))
        mcp = json.loads((REPO / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(server["url"], mcp["mcpServers"]["radiate"]["url"])
        self.assertEqual(server["transport"], "streamable-http")
        self.assertEqual(server["headers"], {"Authorization": "Bearer ${RADIATE_MCP_TOKEN}"})
        # OpenClaw's own decoder (src/agents/bundle-mcp-adapter.ts decodeHeaderEnvPlaceholder)
        # must read it as a bearer token taken from RADIATE_MCP_TOKEN.
        match = re.fullmatch(r"(Bearer )?\$\{([A-Z0-9_]+)\}", server["headers"]["Authorization"])
        self.assertIsNotNone(match)
        self.assertEqual((bool(match.group(1)), match.group(2)), (True, "RADIATE_MCP_TOKEN"))
        self.assertFalse({"auth", "oauth"} & set(server), "OpenClaw must not use OAuth")

    def test_openclaw_literal_token_is_refused(self) -> None:
        literal = "Bearer " + "Ab3" * 14
        self.edit_json(OPENCLAW_SERVER, lambda d: d["headers"].update(Authorization=literal))
        self.assertCaught("env reference")
        self.assertCaught("looks like it contains a bearer token")

    def test_openclaw_header_must_be_exactly_the_bearer_env_reference(self) -> None:
        for headers in (
            {"Authorization": "${RADIATE_MCP_TOKEN}"},
            {"Authorization": "Bearer ${OTHER_TOKEN}"},
            {"Authorization": "Bearer ${RADIATE_MCP_TOKEN:-fallback}"},
            {"Authorization": "Bearer ${RADIATE_MCP_TOKEN}", "X-API-Key": "${RADIATE_MCP_TOKEN}"},
            {},
        ):
            self.edit_json(OPENCLAW_SERVER, lambda d, h=headers: d.update(headers=h))
            self.assertCaught("headers must be exactly")

    def test_openclaw_oauth_is_refused(self) -> None:
        for extra in (
            {"auth": "oauth"},
            {"oauth": {"clientMetadataUrl": "https://radiatestudio.ai/oauth/openclaw.json"}},
        ):
            self.edit_json(OPENCLAW_SERVER, lambda d, e=extra: d.update(e))
            self.assertCaught("no OAuth for OpenClaw")

    def test_openclaw_url_must_match_mcp_json(self) -> None:
        self.edit_json(OPENCLAW_SERVER, lambda d: d.update(url="https://mcp.radiatestudio.ai/mcp"))
        self.assertCaught("url must match mcp.json")

    def test_readme_openclaw_steps_never_sign_in_with_oauth(self) -> None:
        for line in ("openclaw mcp login radiate", 'openclaw mcp set radiate \'{"auth":"oauth"}\''):
            path = self.root / "README.md"
            text = (REPO / "README.md").read_text(encoding="utf-8")
            path.write_text(text.replace("### OpenClaw\n", f"### OpenClaw\n\n{line}\n", 1), encoding="utf-8")
            self.assertCaught("README.md OpenClaw: no OAuth")

    def test_a_pasted_connection_token_is_caught(self) -> None:
        fake = "Q7" * 20  # the shape of a Radiate connection token: 40 letters and digits
        (self.root / "notes.md").write_text(f"export RADIATE_MCP_TOKEN={fake}\n", encoding="utf-8")
        self.assertCaught("Radiate connection token")

    def test_connection_token_request_asks_only_for_read_and_write_tools(self) -> None:
        self.edit_json(OPENCLAW_TOKEN_REQUEST, lambda d: d["tools"].append("generate_image"))
        self.assertCaught("'generate_image' is compute")
        self.edit_json(OPENCLAW_TOKEN_REQUEST, lambda d: d.update(tools=["get_mcp_identity", "no_such_tool"]))
        self.assertCaught("'no_such_tool' is not in tools/inventory.json")


if __name__ == "__main__":
    unittest.main()
