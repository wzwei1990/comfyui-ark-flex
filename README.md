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

## Configure

**Three places a key can live; the first needs no file at all:**

1. **ComfyUI Settings** — `Settings → Ark Flex` holds *Standard API Key (/api/v3)*
   and *Agent Plan Key (/api/plan/v3)*. ComfyUI persists them to
   `user/default/comfy.settings.json`; the nodes read that file, so the key is
   typed once and shared by every node.
2. **`config.json`** → `profiles.<name>.api_key` (one machine, several profiles).
3. **The node's `api_key_override`** (one call, one node).

Leaving all three empty falls back to `ARK_API_KEY`.

Copying the template is only needed for option 2:

```bash
cp config.example.json config.json
```

Resolution order for each field, first hit wins:

```
node override  ->  profile entry  ->  ComfyUI Settings  ->  ARK_API_KEY  ->  built-in default
```

`config.json` is git-ignored on purpose: keys stay on your machine.

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
