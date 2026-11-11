# Contributing

Thanks for helping. This repository is small on purpose: manifests, skills and
the checks that keep them safe. Catalogs pin exact commits of it, and each new
pin is reviewed, so keep changes focused and easy to read.

## Ground rules

- **No credentials, ever.** No API keys, tokens, client secrets or personal
  data in any file, example or test. `mcp.json` and `claude-code/.mcp.json`
  hold only the server `type` and `url`: Hermes, Codex and Claude Code sign
  in with their own OAuth flow. CI fails on anything that looks like a
  credential.
- **OpenClaw uses a connection token, never OAuth.** Radiate's sign-in server
  has no OpenClaw client (no dynamic client registration, no client ID
  metadata document), so `openclaw/radiate.json` is the `mcp.json` URL plus
  exactly one header, `"Authorization": "Bearer ${RADIATE_MCP_TOKEN}"`: an
  environment reference that OpenClaw fills in at runtime. Never a literal
  token, never an `auth` or `oauth` block, and no `openclaw mcp login` in the
  README. `openclaw/connection-token-request.json` may list only `read` and
  `write` tools; Radiate refuses spending and high-risk tools on connection
  tokens until in-app approvals exist.
- **No code that runs on the user's machine** and no binaries. Skills are
  instructions; every action is a call to Radiate's hosted MCP server. No
  self-updaters, install scripts or downloads.
- **Never weaken spend safety.** Skills must quote before every paid call, wait
  for the user's yes, handle Radiate's approval answers without looping, and
  never get around a credit cap. The Hermes server entry stays
  `trust: untrusted` with a `spend_limit`. High-risk tools never go in the
  default tool list.
- **Never ask users for an API key** in a skill, README or example.

## Making a change

1. Edit the skills in `skills/` (never in `claude-code/skills/`, which is a
   generated copy).
2. Run the checks. They need only Python 3.10+ and make no network calls:

   ```bash
   python3 scripts/validate.py --sync    # refresh claude-code/skills, then check
   python3 -m unittest discover -s scripts -p "test_*.py"
   ```

3. Keep `version` the same in `plugin.json`, `claude-code/.claude-plugin/plugin.json`
   and every `SKILL.md`, and bump it (semver) for any change users will see.
4. If the server adds or renames tools, refresh `tools/inventory.json` and
   check `tools/default-tools.json` (about 20 tools; nothing high-risk).
5. Open a pull request against `main`.

## CI and forks

CI runs on Radiate's **self-hosted** runners, and only for pushes to `main` and
pull requests from branches in this repository. **Pull requests from forks
don't run CI**: code from a fork must never run on our runners. A maintainer
reviews a fork's change, then re-opens it from a branch here so CI runs.
Please run the checks above yourself before opening a fork PR.

## Skill frontmatter

Each `skills/<name>/SKILL.md` starts with flat frontmatter that both Hermes's
Agent Skills validator and the ClawHub scanner accept:

```yaml
---
name: radiate-example          # equals the folder name
description: What it does and when to use it (1 to 1024 characters).
version: 0.2.0                 # equals plugin.json
---
```

Don't add nested `metadata`: Hermes requires `metadata` to be a flat string
map. These skills need no environment variables or binaries, so they declare
none. (OpenClaw's `RADIATE_MCP_TOKEN` belongs to its server entry, not to a
skill.)

## Licence of contributions

By contributing you agree that your contribution is licensed under
Apache-2.0, the licence of this repository. Skills published to ClawHub are
redistributed there under MIT-0.

## Release checklist (maintainers)

- [ ] **Switch the server URL to production.** Change
      `https://mcp-dev.radiatestudio.ai/mcp` to `https://mcp.radiatestudio.ai/mcp`
      in `mcp.json`, `claude-code/.mcp.json`, `openclaw/radiate.json` and the
      README (and `backend-dev` to `backend` in the README's connection-token
      steps). CI warns until this is done.
- [ ] Replace the README's connection-token API steps with Radiate's
      Settings → Integrations screen once it ships.
- [ ] Publish the Hermes client id in the README in place of
      `RADIATE_HERMES_CLIENT_ID` (a public client id, not a secret).
- [ ] Check the cost ranges in `plugin.json` against Radiate's current
      prices.
- [ ] Re-check the default tool list against the production server.
- [ ] Only then submit to any catalog or marketplace.
