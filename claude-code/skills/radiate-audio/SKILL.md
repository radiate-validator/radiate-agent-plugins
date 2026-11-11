---
name: radiate-audio
description: Create music, voice-over and sound effects with Radiate Studio. Use when the user asks for a soundtrack, song, score, jingle, narration, character voice or sound effect. Quotes the price and gets a yes before generating.
version: 0.1.0
---

# Audio with Radiate

Follow `radiate-studio` for sign-in, quoting, approvals and caps.

## Music

- `generate_music` takes a `prompt` (genre, mood, tempo, instruments), a
  `duration` in seconds and an optional `model` (for example `diffrhythm`,
  the default, `elevenlabs` or `ace-step`).
- Describe the music, not a copyrighted song or a living artist's voice.
  Don't ask for lyrics you don't have the rights to.

## Voice and sound effects

- Use `recommend_model` with the task ("narration in a warm female voice",
  "door creak sound effect") to find a voice or sound model, then
  `estimate_model_cost` and `generate_with_model`. Where the server offers
  `create_media`, it can route the request for you.
- Voice-over must be the user's own script. Never clone or imitate a real
  person's voice unless the user confirms they have that person's permission.

## Price, then run

1. Quote with the same model and duration (or text length for voice).
2. Show the quote and wait for a yes.
3. Run with an `idempotency_key`, then follow the job with
   `get_generation_status` or `get_job` and give the user the audio link.

## In a project

Pass `project_id` (and `scene_num` / `shot_num`) to add the track to the
user's project. See `radiate-projects`.
