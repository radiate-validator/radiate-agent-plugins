---
name: radiate-video
description: Create video clips with Radiate Studio (Luma, Seedance, MiniMax and other catalog models), from text or from a start image. Use when the user asks for a video, clip, animation, shot or motion from a still. Video is the most expensive media, so always quote first.
version: 0.2.0
---

# Video with Radiate

Follow `radiate-studio` for sign-in, quoting, approvals and caps. Video costs
far more than images: a few seconds can cost hundreds or thousands of
credits, and one call may not exceed the connection's per-call cap (2,500
credits by default).

## Plan the clip

- Confirm the length (`duration`, in seconds), aspect ratio and resolution
  before quoting. These drive the price.
- Start short: offer a 4 to 5 second draft at 720p before a long or 1080p+ run.
- For a clip from a still, generate or pick the still first (see
  `radiate-image`) and pass it as `start_image_url`; `end_image_url` sets the
  last frame where the model supports it.
- `generate_video` models: `luma` (default), `seedance-2.5`, `seedance-2.0`,
  `minimax-h3`, `minimax-h3-max`. For other models use `recommend_model`, then
  `estimate_model_cost` and `generate_with_model`.

## Write the prompt

- Describe one shot: the subject, what moves, and how the camera moves
  ("slow dolly in", "handheld follow", "static wide").
- Keep one action per clip. Cut longer ideas into several shots and quote
  each one.

## Price, then run

1. Quote with the exact model, duration and resolution. If the quote is above
   the per-call cap, say so and offer a shorter or lower-resolution version.
2. Show the quote and wait for a yes.
3. Call the tool with an `idempotency_key`. Expect a Radiate approval step
   (see `radiate-studio` §3).
4. Video takes minutes. Tell the user it's running, then check the `task_id`
   with `get_generation_status` every 15 to 30 seconds. On hosts that support
   it, end your turn and check again when the user comes back rather than
   holding the conversation.

## In a project

Pass `project_id`, `scene_num` and `shot_num` to attach the clip to a shot in
the user's project. See `radiate-projects`.
