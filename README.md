# Ark Flex · ComfyUI nodes for Volcengine Ark

Two nodes for **Seedream images** and **Seedance videos** on Volcengine Ark, built
around the one thing that trips people up: Ark has **two API surfaces** —

| Surface | Base URL | Notes |
| --- | --- | --- |
| Standard API | `https://ark.cn-beijing.volces.com/api/v3` | `/images/generations`, `/contents/generations/tasks` |
| Agent Plan | `https://ark.cn-beijing.volces.com/api/plan/v3` | same request bodies, **its own key** |

The keys are **not** interchangeable: a standard key against the plan URL answers
403, and so does the reverse. Most node packs hard-code the standard URL, which
makes an Agent Plan key unusable.

This pack makes the surface a **profile**: a named pair of base URL + key.
Every node carries a `profile` widget, so images can run on the standard surface
while videos run on Agent Plan — or any other combination.

## Features

- **Per-node profiles.** `standard`, `agent-plan`, or any profile you add to
  `config.json`; `base_url_override` / `api_key_override` for one-off calls.
- **Per-node keys.** Image and video resolve their profile independently.
- **`custom_model`** on both nodes — a model or endpoint id that is not in the
  dropdown still works (that is how newer `doubao-seedance-*` ids are used).
- **`extra_json`** — shallow-merge arbitrary fields into the request body, so a
  new Ark parameter needs no code change.
- **Actionable errors.** A 403 says *which* surface the profile points at and
  that the key probably belongs to the other one.
- **No third-party dependencies.** Standard library only; ComfyUI provides
  torch / numpy / Pillow, which the image decoding uses.

## Install

```bash
cd ComfyUI/custom_nodes
git clone <this-repo> ComfyUI-ArkFlex
```

Restart ComfyUI, then look for the **Ark / 火山方舟** category.

## Which endpoints it talks to

| `kind` | What it is | Reference images |
| --- | --- | --- |
| `ark` (default) | Volcengine Ark — `/api/v3` (standard) and `/api/plan/v3` (Agent Plan) | `refs_mode: json` (data URLs) |
| `openai` | **any OpenAI-compatible image API** (official `/v1`, a third-party relay, …) | `json` (data URLs, most relays) / `multipart` (a real `/images/edits` upload) / `none` |

```jsonc
"profiles": {
  "standard":   { "kind": "ark",    "base_url": "https://ark.cn-beijing.volces.com/api/v3",      "api_key": "…" },
  "agent-plan": { "kind": "ark",    "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3", "api_key": "…" },
  "relay":      { "kind": "openai", "base_url": "https://your-relay/v1", "api_key": "…", "refs_mode": "json" }
}
```

Video is Ark-only: pointing a video node at an `openai` profile fails with an
explanation. Size comes from the `size` preset, or from `width` + `height` when
both are above zero (Ark wants multiples of 16; an OpenAI endpoint does not).

That is what lets this pack replace `comfyui-byokey`'s two families — Ark relay
and third-party relay — with one node and two profiles.

## Configure

**The key lives inside this pack's folder** (`custom_nodes/ComfyUI-ArkFlex/config.json`),
so uninstalling — deleting the folder — takes the key with it. Nothing is left
in ComfyUI's global settings file.

Three ways to enter it; the first needs no file at all:

1. **ComfyUI Settings** — `Settings → Ark Flex` has four entries: *Standard API Key (/api/v3)*, *Agent Plan Key (/api/plan/v3)*, **default image surface** and **default video surface**.
   Pasting a key writes it into the pack's `config.json` immediately and the field
   turns into a **`✅ saved to config.json`** marker — not blank, so a save never
   looks like a no-op. Paste again to replace it. No plaintext copy stays in
   `user/default/comfy.settings.json`.
   The two pickers write `defaults.image` / `defaults.video`, so images and video
   can run on different surfaces (images on the standard API, video on Agent Plan).
2. **`config.json`** → `profiles.<name>.api_key` (one machine, several profiles).
3. **The node's `api_key_override`** (one call, one node).

`ARK_API_KEY` still works as a fallback.

Resolution order, first hit wins:

```
node override  ->  config.json profile  ->  legacy comfy.settings.json (read only)  ->  ARK_API_KEY  ->  built-in default
```

`config.json` is git-ignored on purpose: keys stay out of the repository.

## Uninstall

Delete `custom_nodes/ComfyUI-ArkFlex` and restart ComfyUI. Nodes, settings
entries and the key all go with it — no residue.

(One historical case: a key entered in an early version would sit in
`user/default/comfy.settings.json`; the first load of this version migrates it
into the pack folder and clears that record.)

## Nodes

### Ark 图片 · Seedream

`prompt`, `model`, `size` (pixel presets, not labels — Ark bills by pixel steps),
`max_images` (1–4, sequential calls with `seed + i`), `seed`, `watermark`,
optional `image1..4` references, `custom_model`, `extra_json`.
Returns an `IMAGE` batch and an info string.

### Ark 视频 · Seedance

`prompt`, `model`, `mode` (text / first frame / first + last / reference),
`resolution`, `ratio`, `duration` (4–30 s), `generate_audio`, `output_format`,
`seed`, `watermark`, `timeout`, `poll_seconds`, optional `first_frame`,
`last_frame`, `ref_image1..3`, `custom_model`, `extra_json`.
Returns a `VIDEO` plus an info string (on hosts without the `VIDEO` type, the
saved file path only). Local reference images are sent as base64 data URLs, so
no upload step is needed.

The finished file is written under `output/ark/video/`.

## Notes on models

Model ids change often. The dropdowns carry the ones that existed when this was
written; when yours is missing, put it in **`custom_model`** (or the endpoint id
`ep-...` from the Ark console). That is deliberate: a stale hard-coded list is
worse than a text box.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests are offline: they cover profile resolution, payload assembly per
video mode, size parsing, error text, and the data-URL path (with the tensor
encoder stubbed, since torch is a ComfyUI runtime dependency).

## Prior art

Written after reading `HinaAyanami/comfyui-ark-nodes` and
`fkxianzhou/ComfyUI-Jimeng-API` (both MIT) — the protocol details and the
Agent-Plan URL caveat come from them and from Volcengine's docs. This package
differs in making the surface a first-class, per-node choice.

## License

MIT — see [LICENSE](LICENSE).
