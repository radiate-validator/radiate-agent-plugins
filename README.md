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
| [OpenClaw](https://docs.openclaw.ai) | The same root package as an Agent Plugins bundle | Preview: skills work; sign-in pending (below) |
| Codex | The root `plugin.json` | Preview: uses Radiate's existing Codex sign-in client |
| Claude Code | `claude-code/` (its own `.claude-plugin/` manifest, `.mcp.json` and a copy of the skills) | Preview: sign-in not yet verified |

It is **not** listed in any plugin catalog or marketplace yet.

## What's inside

```text
plugin.json            Agent Plugins v1 manifest, with Hermes trust/costs/spend_limit
mcp.json               the Radiate MCP server (remote, streamable HTTP; no credentials)
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

Sign-in is always OAuth in your browser. **This package never asks for an API
key, and you should never paste one into chat.**

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

```bash
git clone https://github.com/radiate-validator/radiate-agent-plugins
openclaw plugins install ./radiate-agent-plugins
openclaw mcp set radiate '{"url":"https://mcp-dev.radiatestudio.ai/mcp","transport":"streamable-http","auth":"oauth"}'
openclaw mcp login radiate
```

**Sign-in is pending.** OpenClaw registers its sign-in client automatically
(dynamic client registration), and Radiate's sign-in server only accepts
clients that Radiate has registered. Until Radiate adds an OpenClaw client,
`openclaw mcp login radiate` will fail; the skills still load. OpenClaw has no
per-tool cost controls, so keep its approval mode at **prompt** for the
`radiate` server and rely on Radiate's approvals and caps (below).

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

**Network and spend disclosure.** When enabled, this package makes your agent
call `mcp-dev.radiatestudio.ai` (later `mcp.radiatestudio.ai`) and Radiate's
sign-in server, `auth.radiatestudio.ai`. Paid tools spend Radiate credits from
your account. The package itself sends nothing anywhere and has no
auto-updater.

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
- OpenClaw MCP sign-in: https://docs.openclaw.ai/cli/mcp
- Claude Code plugins: https://docs.claude.com/en/docs/claude-code/plugins
