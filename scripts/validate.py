#!/usr/bin/env python3
"""Validate the Radiate agent plugin package. Standard library only; makes no network calls.

Checks the Agent Plugins v1 manifests (plugin.json, mcp.json), the Hermes and
Claude Code metadata, every skill's frontmatter, the curated tool lists, and
that nothing that looks like a credential is committed.

    python3 scripts/validate.py          # check; exit 1 on any error
    python3 scripts/validate.py --sync   # copy skills/ into claude-code/skills/, then check
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
PLUGIN_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
AUTHOR_FIELDS = {"name", "email", "url"}
PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SKILL_NAME_RE = re.compile(r"^(?!.*--)[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
SKILL_FIELDS = {"name", "description", "version"}
HERMES = "com.nousresearch.hermes"
HERMES_SERVER_KEYS = {"trust", "costs", "spend_limit", "cost_unit"}
MCP_HOSTS = {"mcp.radiatestudio.ai", "mcp-dev.radiatestudio.ai"}
PRE_RELEASE_HOST = "mcp-dev.radiatestudio.ai"
# Radiate's default per-call agent cap. A declared cost above it can never run.
PER_CALL_CAP = 2500
TOOL_PREFIXES = (
    "add_",
    "compare_",
    "create_",
    "estimate_",
    "execute_",
    "generate_",
    "get_",
    "import_",
    "launch_",
    "list_",
    "plan_",
    "poll_",
    "preflight_",
    "propose_",
    "query_",
    "recommend_",
    "render_",
    "retry_",
    "run_",
    "save_",
    "search_",
    "train_",
    "update_",
    "upload_",
    "use_",
    "validate_",
)
# Backticked words that look like tool names but are arguments or command values.
NOT_TOOLS = {"get_camera_data", "get_scene_info", "plan_hash", "plan_id"}
SECRET_PATTERNS = {
    "OpenAI/Anthropic-style key": re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{20,}"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "Stripe key": re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{10,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
}
TEXT_SUFFIXES = {".json", ".md", ".yml", ".yaml", ".py", ".txt", ""}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")


def load_json(root: Path, rel: str, report: Report) -> dict | None:
    path = root / rel
    if not path.is_file():
        report.error(rel, "missing")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        report.error(rel, f"invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        report.error(rel, "must be a JSON object")
        return None
    return value


def _is_cost(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value >= 0
    if isinstance(value, list):
        return (
            len(value) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)
            and 0 <= value[0] <= value[1]
        )
    return False


def _cost_max(value: object) -> float:
    credits = value.get("credits") if isinstance(value, dict) else value
    return float(credits[1] if isinstance(credits, list) else credits)  # type: ignore[arg-type,index]


def check_hermes(where: str, extension: object, servers: set[str], inventory: dict, report: Report) -> None:
    if not isinstance(extension, dict) or not isinstance(extension.get("servers"), dict):
        report.error(where, "needs a 'servers' object")
        return
    for name, server in extension["servers"].items():
        at = f"{where}.servers.{name}"
        if name not in servers:
            report.error(at, "names no mcp.json server")
        if not isinstance(server, dict):
            report.error(at, "must be an object")
            continue
        for key in sorted(set(server) - HERMES_SERVER_KEYS):
            report.error(at, f"unexpected key {key!r}")
        if server.get("trust") != "untrusted":
            report.error(at, "trust must be 'untrusted': every spending call asks the user")
        spend_limit = server.get("spend_limit")
        if isinstance(spend_limit, bool) or not isinstance(spend_limit, (int, float)) or spend_limit <= 0:
            report.error(at, "spend_limit must be a positive number")
        if server.get("cost_unit", "credits") != "credits":
            report.error(at, "cost_unit must be 'credits'")
        costs = server.get("costs")
        if not isinstance(costs, dict) or not costs:
            report.error(at, "costs must be a non-empty object")
            continue
        for tool, cost in costs.items():
            if inventory.get(tool) != "compute":
                report.error(f"{at}.costs.{tool}", "is not a compute tool in tools/inventory.json")
            valid = _is_cost(cost) or (
                isinstance(cost, dict)
                and set(cost) <= {"credits", "note"}
                and _is_cost(cost.get("credits"))
                and isinstance(cost.get("note", ""), str)
            )
            if not valid:
                report.error(f"{at}.costs.{tool}", "must be a number, [min, max] or {credits, note}")
            elif _cost_max(cost) > PER_CALL_CAP:
                report.error(f"{at}.costs.{tool}", f"maximum is above the per-call cap {PER_CALL_CAP}")


def check_plugin(root: Path, inventory: dict, servers: set[str], report: Report) -> dict:
    manifest = load_json(root, "plugin.json", report) or {}
    if not manifest:
        return {}
    for field in sorted(set(manifest) - PLUGIN_FIELDS):
        report.error("plugin.json", f"unknown top-level field {field!r} (the v1 schema is closed)")
    if manifest.get("$schema") != PLUGIN_SCHEMA:
        report.error("plugin.json", f"$schema must be {PLUGIN_SCHEMA}")
    name = manifest.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or not PLUGIN_NAME_RE.fullmatch(name):
        report.error("plugin.json", "name does not meet the v1 name rules")
    for field in ("version", "description", "homepage", "repository", "license"):
        if field in manifest and not isinstance(manifest[field], str):
            report.error("plugin.json", f"{field} must be a string")
    if not SEMVER_RE.fullmatch(str(manifest.get("version", ""))):
        report.error("plugin.json", "version must be semver")
    if manifest.get("license") != "Apache-2.0":
        report.error("plugin.json", "license must be Apache-2.0")
    keywords = manifest.get("keywords", [])
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        report.error("plugin.json", "keywords must be an array of strings")
    author = manifest.get("author", {})
    if not isinstance(author, dict) or set(author) - AUTHOR_FIELDS:
        report.error("plugin.json", "author may hold only name, email and url")
    extensions = manifest.get("extensions", {})
    if not isinstance(extensions, dict) or not all(isinstance(v, dict) for v in extensions.values()):
        report.error("plugin.json", "extensions must map namespaces to objects")
    elif HERMES not in extensions:
        report.error("plugin.json", f"extensions.{HERMES} (trust, costs, spend_limit) is required")
    else:
        check_hermes(f"plugin.json extensions.{HERMES}", extensions[HERMES], servers, inventory, report)
    return manifest


def check_url(where: str, url: object, report: Report) -> None:
    parts = urlsplit(url) if isinstance(url, str) else None
    if parts is None or parts.scheme != "https" or parts.hostname not in MCP_HOSTS:
        report.error(where, f"url must be https on one of {sorted(MCP_HOSTS)}")
        return
    if parts.username or parts.password or parts.fragment or parts.query or parts.port:
        report.error(where, "url must have no user info, port, query or fragment")
    if parts.path != "/mcp":
        report.error(where, "url path must be /mcp")
    if parts.hostname == PRE_RELEASE_HOST:
        report.warn(where, "points at the development server; switch to mcp.radiatestudio.ai at release")


def check_mcp(root: Path, report: Report) -> tuple[set[str], str]:
    config = load_json(root, "mcp.json", report) or {}
    if not config:
        return set(), ""
    if set(config) != {"$schema", "mcpServers"}:
        report.error("mcp.json", "must hold exactly $schema and mcpServers")
    if config.get("$schema") != MCP_SCHEMA:
        report.error("mcp.json", f"$schema must be {MCP_SCHEMA}")
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or set(servers) != {"radiate"}:
        report.error("mcp.json", "mcpServers must hold exactly one server, 'radiate'")
        return set(), ""
    server = servers["radiate"]
    if not isinstance(server, dict) or set(server) != {"type", "url"}:
        # No headers: credentials come from the host's own OAuth sign-in, never the package.
        report.error("mcp.json radiate", "must hold only type and url (no headers, no credentials)")
        return {"radiate"}, ""
    if server.get("type") != "streamable-http":
        report.error("mcp.json radiate", "type must be streamable-http")
    check_url("mcp.json radiate", server.get("url"), report)
    return {"radiate"}, str(server.get("url"))


def check_claude_code(root: Path, plugin: dict, url: str, report: Report) -> None:
    base = "claude-code"
    if (root / ".claude-plugin").exists():
        report.error(".claude-plugin", "must not exist at the root: it would make OpenClaw load a Claude bundle")
    manifest = load_json(root, f"{base}/.claude-plugin/plugin.json", report) or {}
    for field in ("name", "version", "license", "homepage", "repository"):
        if manifest and manifest.get(field) != plugin.get(field):
            report.error(f"{base}/.claude-plugin/plugin.json", f"{field} must match plugin.json")
    market = load_json(root, f"{base}/.claude-plugin/marketplace.json", report) or {}
    plugins = market.get("plugins") if market else None
    if market and (
        not isinstance(plugins, list)
        or len(plugins) != 1
        or not isinstance(plugins[0], dict)
        or plugins[0].get("name") != plugin.get("name")
        or plugins[0].get("source") != "./"
    ):
        report.error(f"{base}/.claude-plugin/marketplace.json", "must list exactly this plugin with source './'")
    mcp = load_json(root, f"{base}/.mcp.json", report) or {}
    server = (mcp.get("mcpServers") or {}).get("radiate") if mcp else None
    if mcp and (not isinstance(server, dict) or set(server) != {"type", "url"} or server.get("type") != "http"):
        report.error(f"{base}/.mcp.json", "radiate must hold only type 'http' and url")
    elif mcp and server.get("url") != url:
        report.error(f"{base}/.mcp.json", "radiate url must match mcp.json")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """The flat ``key: value`` frontmatter these skills use; anything nested is refused."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([a-z][a-z-]*):[ ]+(\S.*)", line)
        if match is None:
            return None
        key, value = match.group(1), match.group(2).strip()
        if key in fields or value.startswith(("{", "[", "|", ">")):
            return None
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
    return fields


def check_skills(root: Path, plugin: dict, inventory: dict, report: Report) -> list[str]:
    skills_dir = root / "skills"
    names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []
    if not names:
        report.error("skills", "no skills found")
    for name in names:
        rel = f"skills/{name}/SKILL.md"
        path = root / rel
        if not path.is_file():
            report.error(rel, "missing (every skills/ child needs a SKILL.md)")
            continue
        text = path.read_text(encoding="utf-8")
        fields = parse_frontmatter(text)
        if fields is None:
            report.error(rel, "frontmatter must be flat 'key: value' lines between --- markers")
            continue
        for key in sorted(set(fields) - SKILL_FIELDS):
            report.error(rel, f"unexpected frontmatter key {key!r} (allowed: {sorted(SKILL_FIELDS)})")
        if fields.get("name") != name or not SKILL_NAME_RE.fullmatch(name) or len(name) > 64:
            report.error(rel, "name must equal the folder name (lowercase letters, digits, hyphens)")
        if not 1 <= len(fields.get("description", "")) <= 1024:
            report.error(rel, "description must be 1 to 1024 characters")
        if fields.get("version") != plugin.get("version"):
            report.error(rel, "version must match plugin.json")
        for token in sorted(set(re.findall(r"`([a-z][a-z0-9_]*)`", text))):
            if token.startswith(TOOL_PREFIXES) and token not in inventory and token not in NOT_TOOLS:
                report.error(rel, f"names tool {token!r}, which tools/inventory.json does not list")
    mirror = root / "claude-code" / "skills"
    mirrored = sorted(p.name for p in mirror.iterdir() if p.is_dir()) if mirror.is_dir() else []
    if mirrored != names:
        report.error("claude-code/skills", "must mirror skills/ (run scripts/validate.py --sync)")
    for name in set(names) & set(mirrored):
        a, b = root / "skills" / name, mirror / name
        files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
        files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
        if files_a != files_b or any((a / f).read_bytes() != (b / f).read_bytes() for f in files_a):
            report.error(f"claude-code/skills/{name}", "differs from skills/ (run scripts/validate.py --sync)")
    return names


def check_tools(root: Path, inventory: dict, skills: list[str], report: Report) -> None:
    rel = "tools/default-tools.json"
    data = load_json(root, rel, report) or {}
    if not data:
        return
    groups = data.get("groups")
    if not isinstance(groups, dict):
        report.error(rel, "groups must be an object")
        return
    default = [tool for tools in groups.values() for tool in tools]
    if len(default) != len(set(default)):
        report.error(rel, "a tool is listed twice")
    if not 15 <= len(default) <= 30:
        report.error(rel, f"keep the default list near 20 tools (has {len(default)})")
    for tool in default:
        if tool not in inventory:
            report.error(rel, f"{tool!r} is not in tools/inventory.json")
        elif inventory[tool] == "high_risk":
            report.error(rel, f"{tool!r} is high_risk and may never be on by default")
    for tool in [*data.get("opt_in", {}), *data.get("never_default", [])]:
        if tool not in inventory:
            report.error(rel, f"{tool!r} is not in tools/inventory.json")
        if tool in default:
            report.error(rel, f"{tool!r} is opt-in or never-default but is in groups")
    for tool, risk in inventory.items():
        if risk == "high_risk" and tool not in data.get("opt_in", {}) and tool not in data.get("never_default", []):
            report.error(rel, f"high_risk tool {tool!r} must be listed under opt_in or never_default")
    for skill, tools in (data.get("skill_tools") or {}).items():
        if skill.startswith("_"):
            continue
        if skill not in skills:
            report.error(rel, f"skill_tools names unknown skill {skill!r}")
        for tool in tools:
            if tool not in inventory:
                report.error(rel, f"skill_tools {skill}: {tool!r} is not in tools/inventory.json")


def check_secrets(root: Path, report: Report) -> None:
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or rel.parts[0] == ".git" or path.suffix not in TEXT_SUFFIXES:
            continue
        if rel.as_posix() == "scripts/validate.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report.error(rel.as_posix(), "is not UTF-8 text; binaries are not allowed")
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                report.error(rel.as_posix(), f"looks like it contains a {label}")


def sync(root: Path) -> None:
    mirror = root / "claude-code" / "skills"
    if mirror.exists():
        shutil.rmtree(mirror)
    shutil.copytree(root / "skills", mirror)


def validate(root: Path) -> Report:
    report = Report()
    inventory_doc = load_json(root, "tools/inventory.json", report) or {}
    inventory = inventory_doc.get("tools") if isinstance(inventory_doc.get("tools"), dict) else {}
    if inventory_doc and not inventory:
        report.error("tools/inventory.json", "tools must map tool names to risk classes")
    servers, url = check_mcp(root, report)
    plugin = check_plugin(root, inventory, servers, report)
    check_claude_code(root, plugin, url, report)
    skills = check_skills(root, plugin, inventory, report)
    check_tools(root, inventory, skills, report)
    check_secrets(root, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--sync", action="store_true", help="copy skills/ into claude-code/skills/ first")
    args = parser.parse_args(argv)
    if args.sync:
        sync(args.root)
    report = validate(args.root)
    for warning in report.warnings:
        print(f"warning: {warning}")
    for error in report.errors:
        print(f"error: {error}")
    print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
