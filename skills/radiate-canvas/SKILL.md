---
name: radiate-canvas
description: Run repeatable multi-step pipelines as Radiate Canvas graphs (for example prompt to image to video to upscale). Use when the user wants the same chain of generation steps run again, batched, or on a schedule. Validates and prices the whole graph before running it.
version: 0.2.0
---

# Radiate Canvas graphs

Follow `radiate-studio` for sign-in, quoting, approvals and caps. A graph run
can start several paid steps, so the quote covers the **whole graph**.

## Build or reuse the graph

- Prefer a graph the user already has: `list_canvas_boards` /
  `get_canvas_board`, or a template from `list_canvas_templates`.
- To build one, look up node types with `list_node_catalog` and
  `get_node_schema`. Keep graphs small; each paid node adds to the price.
- Check it with `validate_canvas_graph` before quoting.

## Price, then run

1. `estimate_canvas_graph_cost` with the exact graph. Show the total, and the
   most expensive nodes if the total is large.
2. Wait for a yes.
3. `run_canvas_graph` with the same `board_id` and `graph`, an
   `idempotency_key`, and `max_credits` set to the quoted total, so the run
   stops instead of costing more than the user agreed to.
4. Follow it with `get_canvas_graph_run`. If one node fails, report which one;
   `retry_canvas_graph_node` is a new paid step, so quote it first.

## Unattended runs

When the host runs this on a schedule (cron, a gateway, a bot):

- Radiate still requires a person to approve each paid run. An unattended run
  will stop at the approval step; that is expected. Tell the user how to
  approve in Radiate rather than retrying.
- Never raise `max_credits` above the last quote the user agreed to.
