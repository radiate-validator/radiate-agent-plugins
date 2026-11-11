---
name: radiate-local-compute
description: Run Blender renders or scene checks on the user's own machine through the Radiate compute connector. Use only when the user asks to render on their own GPU or workstation that they have paired with Radiate. Plans first, shows the plan, and needs approval in Radiate for every run.
version: 0.2.0
---

# Local compute through Radiate

Follow `radiate-studio` for sign-in and approvals. This skill uses
`run_compute_job`, which is **off by default** in this plugin: the user has
to enable that tool in their agent first. If it isn't available, say so and
stop.

## What it can do

- Render a `.blend` file from the user's Radiate Media Library on their paired
  machine, or run one of a few fixed inspection commands (`ping`,
  `get_scene_info`, `get_camera_data`, `export_glb`).
- It never runs arbitrary Python or downloads arbitrary URLs. If the user asks
  for that, say it isn't supported.

## Plan, show, approve, run

1. `plan_compute_job` with the `project_id`, the `mode` (`render` or
   `inspect`), the asset or command, and the frame range, resolution and
   samples. Start with a short preview (`preview: true`, a few frames).
2. Show the user the plan: machine, file, frames, resolution, samples.
3. `run_compute_job` with the plan's `plan_id`, `plan_hash` and
   `expected_base_revisions`, unchanged. Radiate asks the user to approve
   every run in Radiate (see `radiate-studio` §3).
4. Follow the job with `get_job` and report where the output landed.

## Look after the machine

- Long renders keep the user's GPU busy. Say how many frames and roughly how
  long before running a full range.
- If the connector reports the machine is busy or offline, stop and tell the
  user. Don't queue repeated retries.
