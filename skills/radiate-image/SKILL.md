---
name: radiate-image
description: Create images with Radiate Studio (FLUX, Nano Banana and other catalog models). Use when the user asks for an image, still, poster, concept art, storyboard frame or variations. Quotes the price and gets a yes before generating.
version: 0.2.0
---

# Images with Radiate

Follow `radiate-studio` for sign-in, quoting, approvals and caps. This skill
adds what is specific to images.

## Pick the model

- `generate_image` covers the common models: `flux-schnell` (fast, cheapest,
  the default), `flux-dev`, `nano-banana` and `nano-banana-pro` (best for text
  in images, reference images and 2K/4K output).
- For anything else, call `recommend_model` with the task (for example
  "photoreal product shot") or `search_models`, then use the returned
  `model_id` with `estimate_model_cost` and `generate_with_model`.
- If the user names a model you can't find, say so. Don't substitute a more
  expensive one silently.

## Write the prompt

- Subject first, then setting, light, lens or style, then mood. Keep it to two
  or three sentences.
- Put what to avoid in `negative_prompt`, not in the prompt.
- Choose `aspect_ratio` from the use: `16:9` for widescreen, `9:16` for phone
  stories, `1:1` for avatars and grids.
- Reference images (`reference_image_urls`, Nano Banana only) must be the
  user's own or ones they are allowed to use. Ask if you're not sure.

## Price, then run

1. Quote with the same model, `num_images` and `resolution` you will send.
   Price grows with the image count and with 2K/4K output.
2. Show the quote and wait for a yes.
3. Call `generate_image` (or `generate_with_model`) with an `idempotency_key`.
4. Follow the returned `task_id` with `get_generation_status` until it is done,
   then give the user the image links.

Ask before making more than 4 images in one go, and before redoing a batch.

## In a project

Pass `project_id` (and `scene_num` / `shot_num` for a storyboard frame) to file
the image in the user's Radiate project. See `radiate-projects`.
