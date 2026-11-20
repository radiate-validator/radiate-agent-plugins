---
name: radiate-studio
description: Rules for every Radiate Studio task (image, video, audio, projects, canvas). Use first whenever the user asks to create media with Radiate or work in a Radiate project. Covers sign-in, quoting before spending, approvals, credit caps and following long jobs.
version: 0.2.0
---

# Radiate Studio: the rules for every task

Radiate Studio is a hosted creative studio. You reach it through the `radiate`
MCP server. Every action is a tool call on that server; nothing in this skill
runs code on the user's machine.

Load the matching skill for the work, after this one:

| The user wants | Skill |
| --- | --- |
| Images, stills, edits of a still | `radiate-image` |
| Video clips | `radiate-video` |
| Music, voice, sound effects | `radiate-audio` |
| To use or update a Radiate project | `radiate-projects` |
| A repeatable multi-step pipeline (a canvas graph) | `radiate-canvas` |
| To run a job on their own GPU through Radiate | `radiate-local-compute` |

## 1. Sign-in

- Most hosts sign the user in to Radiate in their browser through the host's
  MCP OAuth login. OpenClaw instead sends a Radiate connection token that the
  user keeps in the `RADIATE_MCP_TOKEN` environment variable on their machine.
  You never handle their password or their token.
- **Never ask for, accept or store an API key, token or password.** If the user
  pastes one, tell them not to share it in chat and to revoke it in Radiate.
- If a tool answers that sign-in is required (HTTP 401, `authorization-required`),
  tell the user to run their host's login command (see the README) and stop.
  In OpenClaw it means the connection token is missing, expired or revoked:
  tell the user to create a new one and update `RADIATE_MCP_TOKEN` themselves
  (see the README), and stop.
- Call `get_mcp_identity` once at the start to confirm who is signed in.

## 2. Quote, confirm, run, follow

Every tool that spends credits follows the same four steps. Do not skip one.

1. **Quote.** Call the matching estimate tool first:
   `estimate_generation_cost`, `estimate_model_cost` or
   `estimate_canvas_graph_cost`. Use exactly the arguments you plan to run.
   If no estimate covers the exact request, say so and show the published
   price from `get_service_pricing`. Never make a price up.
2. **Confirm.** Show the user the price in credits (and "up to" when the
   estimate is a ceiling) and their balance from `get_credit_balance` when it
   matters. Wait for a clear yes. A yes covers one run with those arguments,
   not later runs or changed arguments.
3. **Run.** Call the spending tool with the same arguments, plus a new
   `idempotency_key` (8 to 128 characters: letters, digits, `.`, `_`, `:` or
   `-`). Every Radiate tool accepts it. If the call times out or the connection
   drops and you don't know whether it ran, retry with the **same** key, so it
   can't run twice.
4. **Follow.** Spending tools usually return a job or task id. Check it with
   `get_generation_status` or `get_job` (read-only, free). Use
   `poll_generation` only when the server tells you to. Don't check more often
   than every 10 to 15 seconds; video can take minutes. Give the user the
   result links when the job finishes.

## 3. Approvals in Radiate

Radiate asks a person to approve every call that spends credits, on top of
any prompt your host shows. You will see one of these:

- **An approval prompt from the host** (MCP elicitation). The user answers it
  in their agent. If they decline, stop and don't retry.
- **`human_release_required` without a `confirmation_id`**: Radiate isn't
  taking approvals from agents on this account or server yet, so paid and
  high-risk tools can't run from here. Say so, suggest doing it in Radiate
  Studio directly, and don't retry. Free tools (estimates, reads) still work.
- **`human_release_required`** with a `confirmation_id`, `expires_at` and
  `max_credits`. Tell the user: "Approve this in Radiate: Settings →
  Integrations → Pending approvals." When they say they've approved it, retry
  **the same call with identical arguments** and set
  `_meta["io.radiatestudio/confirmationId"]` to the `confirmation_id`.
- **`confirmation_not_released`**: not approved yet. Wait for the user. Don't
  loop on retries.
- **`confirmation_declined`, `confirmation_expired`,
  `confirmation_rounds_exceeded` or `confirmation_not_pending`**: stop. Start
  over from the quote only if the user asks.

Never try to approve on the user's behalf, and never describe the approval as
optional.

## 4. Credit caps

Radiate limits what one agent connection can spend: by default 5,000 credits
a day and 2,500 per call. The approval ceiling can't be set above the per-call
cap. The user can only change the caps in Radiate.

- If a quote is above the per-call cap, say so before running. Offer a cheaper
  model, a shorter clip or fewer outputs.
- If a call is refused for a credit cap (`credit_cap_exceeded`,
  `cost_cap_exceeded` or HTTP 409 naming a maximum), stop and tell the user
  which cap was hit.
- **Never get around a cap** by splitting one job into many calls, switching
  connections, or asking the user to raise a limit so you can carry on.

## 5. Errors

- `connection_token_tool_refused`: this connection is a connection token
  (OpenClaw), which may use only free read and write tools. Paid generation
  and high-risk tools aren't available from it yet. Say so, offer the quote
  you can still give, suggest running the job in Radiate Studio, and don't
  retry.
- Out of credits: tell the user, and don't retry.
- A job that failed is refunded by Radiate. Report the error. Trying again
  is a new run: quote and confirm again, with a new `idempotency_key`.
- Anything you don't understand: show the error text and stop.

## 6. What to tell the user

- Credits are Radiate credits. Show the number the estimate returned, not a
  dollar figure you worked out.
- Results are private to the user's Radiate account unless they share them.
