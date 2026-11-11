# Radiate agent plugins

Use [Radiate Studio](https://radiatestudio.ai) from your AI agent. Create images,
video, music, voice and sound effects. Work in your Radiate projects and run
canvas pipelines, all from chat. Your agent shows you the price before anything
spends credits, and Radiate asks you to approve every paid call.

> **Preview.** This package currently connects to Radiate's **development**
> server, `https://mcp-dev.radiatestudio.ai/mcp`. Development accounts and
> credits are separate from production, and the service may change or reset.
> It will switch to `https://mcp.radiatestudio.ai/mcp` when Radiate's MCP
> server is released.
>
> Until Radiate turns on approvals for agents, **paid and high-risk tools are
> refused** (`human_release_required`) and only free tools (estimates, account
> and project reads) work. The skills handle that answer.

This repository holds one package, in the
[Agent Plugins v1](https://agent-plugins.org/specification) format, that works
with several agents:

| Agent | What it loads | Status |
| --- | --- | --- |
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | Root `plugin.json` + `mcp.json` + `skills/` as a portable plugin, with Hermes cost and spend-limit metadata | Preview: needs the Radiate `hermes` sign-in client (below) |
| [OpenClaw](https://docs.openclaw.ai) | The same root package as an Agent Plugins bundle, plus the server entry in `openclaw/radiate.json` | Preview: connects with a Radiate connection token; read and write tools and quotes only, no paid generation (below) |
| Codex | The root `plugin.json` | Preview: uses Radiate's existing Codex sign-in client |
| Claude Code | `claude-code/` (its own `.claude-plugin/` manifest, `.mcp.json` and a copy of the skills) | Preview: sign-in not yet verified |

It is **not** listed in any plugin catalog or marketplace yet.

## What's inside

```text
plugin.json            Agent Plugins v1 manifest, with Hermes trust/costs/spend_limit
mcp.json               the Radiate MCP server (remote, streamable HTTP; no credentials)
openclaw/              OpenClaw's server entry (token header read from an environment
                       variable) and the request that creates its connection token
skills/                seven workflow skills shared by every agent
  radiate-studio/        the rules: sign-in, quote → confirm → run → follow, approvals, caps
  radiate-image/         images
  radiate-video/         video clips
  radiate-audio/         music, voice and sound effects
  radiate-projects/      Radiate projects as working memory
  radiate-canvas/        canvas graphs (repeatable pipelines)
  radiate-local-compute/ Blender renders on your own paired machine (opt-in)
tools/default-tools.json  the ~20 tools to enable by default, plus per-skill extras
tools/inventory.json      the server's tool names and risk classes (used by CI)
claude-code/           the Claude Code plugin (generated copy of skills/)
scripts/validate.py    the checks CI runs; no network, no dependencies
```

There is no code that runs on your machine. The skills are instructions for
your agent, and every action is a call to Radiate's hosted MCP server.

## Before you start

- A Radiate account on a paid plan (MCP access is not on the free plan). For
  this preview, use an account on Radiate's development environment.
- Credits in that account. You only spend credits on calls you approve.

## Install and sign in

Hermes, Codex and Claude Code sign in with OAuth in your browser. OpenClaw
connects with a Radiate **connection token** that you keep in an environment
variable on your own machine. **This package contains no token, never asks you
for one in chat, and you should never paste one into chat.**

### Hermes Agent

```bash
hermes plugins install radiate-validator/radiate-agent-plugins --no-enable
hermes plugins enable radiate
```

Then add a same-named server to `~/.hermes/config.yaml` so Hermes signs you in
with Radiate's Hermes client. Keep `trust: untrusted`: a `config.yaml` entry
replaces the package's trust setting, while the package's per-tool costs and
spend limit stay in force.

```yaml
mcp_servers:
  radiate:
    url: https://mcp-dev.radiatestudio.ai/mcp
    auth: oauth
    trust: untrusted
    oauth:
      client_id: "RADIATE_HERMES_CLIENT_ID"  # TODO: published here once Radiate registers it
      redirect_port: 27890                   # 27891-27894 also work if 27890 is busy
```

```bash
hermes mcp login radiate                 # opens your browser
hermes mcp login radiate --flow device   # on a server or over SSH: enter a code on any device
```

To keep the tool list small, enable only the tools in
[`tools/default-tools.json`](tools/default-tools.json).

### OpenClaw

OpenClaw connects with a Radiate **connection token**, sent as an
`Authorization: Bearer` header. It does not sign in with OAuth and has no
browser sign-in step: Radiate's sign-in server doesn't accept the client
registration OpenClaw would need, so Radiate gives OpenClaw a scoped token
instead.

**What a connection token can do.** Free read and write tools only: account,
balance, model search, **quotes** (the estimate tools), job status, projects
and canvas reads. Radiate refuses every tool that spends credits, and every
high-risk tool, on a connection token (`connection_token_tool_refused`), so
**OpenClaw can't run paid generation yet**. That arrives with approvals inside
Radiate; until then, run paid jobs in Radiate Studio.

#### 1. Create a connection token

Radiate Studio has no screen for connection tokens yet (it is planned for
Settings → Integrations), and the feature is off on the development server
until Radiate turns it on. Until then, create one through Radiate's API while
signed in to Radiate, with [`openclaw/connection-token-request.json`](openclaw/connection-token-request.json)
as the request. That file names the tools the token may use (all free) and
asks for 30 days; the longest allowed is 90.

```bash
curl -sS -X POST https://backend-dev.radiatestudio.ai/api/v2/mcp/connection-tokens \
  -H "Authorization: Bearer $RADIATE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  --data @radiate-agent-plugins/openclaw/connection-token-request.json
```

`$RADIATE_ACCESS_TOKEN` is an access token from your own Radiate sign-in (the
one Radiate Studio uses), not the connection token. Until the Settings screen
ships, this step is meant for developers and preview testers.

The answer holds the token's `id` (keep it: you need it to revoke the token)
and, **once only**, its `secret`: the connection token. Radiate stores only a
hash of it and can't show it again.

#### 2. Store it in `RADIATE_MCP_TOKEN`

Put it where OpenClaw's Gateway reads its environment, for example
`~/.openclaw/.env`. `read -s` keeps it out of your shell history:

```bash
mkdir -p ~/.openclaw && umask 077
read -rsp 'Radiate connection token: ' RADIATE_MCP_TOKEN && echo
printf 'RADIATE_MCP_TOKEN=%s\n' "$RADIATE_MCP_TOKEN" >> ~/.openclaw/.env
unset RADIATE_MCP_TOKEN
```

#### 3. Install and connect

```bash
git clone https://github.com/radiate-validator/radiate-agent-plugins
openclaw plugins install ./radiate-agent-plugins
openclaw mcp set radiate "$(cat radiate-agent-plugins/openclaw/radiate.json)"
openclaw mcp probe radiate
```

[`openclaw/radiate.json`](openclaw/radiate.json) is the package's `mcp.json`
server plus one header, `"Authorization": "Bearer ${RADIATE_MCP_TOKEN}"`.
OpenClaw saves that reference as written and fills in the token from the
environment when it connects, so the token never lands in OpenClaw's config
file. The entry replaces the package's own `radiate` server in OpenClaw. It
also sets `codex.defaultToolsApprovalMode` to `prompt`, so OpenClaw's Codex
runtime asks you before each Radiate tool call.

#### Revoke or replace it

Revoke a token as soon as you stop using it or think it has leaked. Revoking
works even while connection tokens are switched off; the list works only
while they are on:

```bash
curl -sS https://backend-dev.radiatestudio.ai/api/v2/mcp/connection-tokens \
  -H "Authorization: Bearer $RADIATE_ACCESS_TOKEN"            # list: ids, labels, expiry
curl -sS -X DELETE https://backend-dev.radiatestudio.ai/api/v2/mcp/connection-tokens/TOKEN_ID \
  -H "Authorization: Bearer $RADIATE_ACCESS_TOKEN"            # revoke one
```

Then delete the `RADIATE_MCP_TOKEN` line from `~/.openclaw/.env`. A token also
stops working when it expires; to keep going, create a new one and replace the
line.

### Claude Code

```bash
git clone https://github.com/radiate-validator/radiate-agent-plugins
```

In Claude Code:

```text
/plugin marketplace add ./radiate-agent-plugins/claude-code
/plugin install radiate@radiate
/mcp      # choose radiate, then Authenticate
```

Sign-in from Claude Code hasn't been verified against Radiate yet. If it fails
with a client registration error, Radiate hasn't enabled a Claude Code client;
the skills still load.

### Codex

Codex reads the root `plugin.json`. For the MCP sign-in, follow the Codex
instructions in Radiate (Settings → Integrations), which pin the callback port
Radiate's Codex client expects.

## Spend safety

Several layers protect your credits. None of them relies on the agent
behaving well.

1. **Quote first.** The skills tell the agent to price every paid call with
   Radiate's estimate tools and wait for your yes.
2. **Your agent's own prompt.** In Hermes, the package marks the server
   `trust: untrusted` (every call that isn't read-only asks you first), names
   the cost range of each paid tool, and sets a per-chat `spend_limit` of
   5,000 credits.
3. **Approval in Radiate.** Radiate requires a person to approve every call
   that spends credits, and every high-risk call. Approve it in your agent if
   it shows Radiate's prompt, or in Radiate under Settings → Integrations →
   Pending approvals. A host-side "yes" does not replace this, and an agent
   can't approve for you. Unattended runs (cron, bots) stop at this step.
4. **Caps per connection.** With approvals on, one agent connection can
   spend at most **5,000 credits a day** and **2,500 credits per call** by
   default. A call above the per-call cap is refused even if approved.
5. **Narrow tool access.** The default tool list has no high-risk tools.
   `run_compute_job` (renders on your own machine) is opt-in, and
   `blender_live_command` and `launch_original` are never on by default.
6. **No spending from connection tokens.** An OpenClaw connection token can
   only use the free read and write tools it was created with. Radiate
   refuses every spending or high-risk call on it, whatever the agent asks.

**Network and spend disclosure.** When enabled, this package makes your agent
call `mcp-dev.radiatestudio.ai` (later `mcp.radiatestudio.ai`) and Radiate's
sign-in server, `auth.radiatestudio.ai`. In OpenClaw it sends your connection
token to `mcp-dev.radiatestudio.ai` and nowhere else. Paid tools spend Radiate
credits from your account. The package itself sends nothing anywhere and has
no auto-updater.

## Licence

Apache-2.0. See [LICENSE](LICENSE). Copyright Radiate Validator LLC.

If the skills are published to ClawHub, ClawHub redistributes every skill's
text under MIT-0, as its terms require. The copy in this repository stays
under Apache-2.0.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md). **Pull requests from forks don't run
CI**; a maintainer reviews them first. Report security issues as described in
[SECURITY.md](SECURITY.md), not in public issues.

## Links

- Radiate Studio: https://radiatestudio.ai
- Agent Plugins specification: https://agent-plugins.org/specification
- Hermes portable plugins: https://github.com/NousResearch/hermes-agent (developer guide → plugins)
- OpenClaw MCP servers and headers: https://docs.openclaw.ai/cli/mcp/transports
- Claude Code plugins: https://docs.claude.com/en/docs/claude-code/plugins
