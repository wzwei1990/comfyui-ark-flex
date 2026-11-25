# Ark Flex · ComfyUI nodes (Ark Seedream / Seedance + OpenAI-compatible images)

Three nodes, one responsibility each:

| Node | Does | Connection from |
| --- | --- | --- |
| `ArkImage` | Volcengine Ark **Seedream** images (text-to-image / image-to-image) | Settings → **方舟 Ark** |
| `OpenAIImage` | **any OpenAI-compatible image API** (third-party relays, `/v1`) | Settings → **OpenAI 兼容** |
| `ArkVideo` | Volcengine Ark **Seedance** video (text / first frame / first+last / reference) | Settings → **方舟 Ark** |

The two providers are kept apart end to end: separate nodes, separate settings pages, separate config sections. No dropdown mixes an Ark surface with a relay.

## Why

Volcengine Ark has two API surfaces with identical request bodies, but keys that are **not interchangeable**:

| Surface | Base URL | Notes |
| --- | --- | --- |
| Standard | `https://ark.cn-beijing.volces.com/api/v3` | `/images/generations`, `/contents/generations/tasks` |
| Agent Plan | `https://ark.cn-beijing.volces.com/api/plan/v3` | Same bodies, **Agent Plan console key** |

A standard key against the plan URL returns **403**, and vice versa. Most packs hard-code the standard URL, which makes an Agent Plan key unusable.

**Surface and model are not freely interchangeable** (measured):

| Model | Works on | The other surface answers |
| --- | --- | --- |
| `doubao-seedream-5-0-pro` (images) | **Agent Plan** | 404 `InvalidEndpointOrModel.NotFound` on standard |
| `doubao-seedance-2-5-flash-261115` (video) | **Standard** | 404 `UnsupportedModel: does not support the agent plan feature` on plan |

So the usual setup is *images on the plan surface, video on standard* (`defaults.image = agent-plan`, `defaults.video = standard`); the node's `profile` starts from those fields.

Also: **first-frame / first+last modes must not send `ratio`** — Ark returns `400 InvalidParameter.TaskTypeConstraint` because the ratio follows the conditioning image. The node now omits it in those modes.

Here a *surface* is a **profile** — a named `(base_url, api_key)` pair — chosen per node, so images and video can use different surfaces. OpenAI-compatible relays live in their own `openai` section and never appear in the Ark dropdown.

## Features

- **Ark and OpenAI-compatible are separate**: two image nodes, two settings pages, two config sections.
- **Per-node surface**: `standard`, `agent-plan`, or your own Ark profile; `base_url_override` / `api_key_override` for a single call.
- **Keys live in the pack folder** (`custom_nodes/ComfyUI-ArkFlex/config.json`, git-ignored): uninstalling — deleting the folder — removes them, and no plaintext copy stays in `comfy.settings.json`.
- **Two ways to send references**: `json` (data URLs — Ark and most relays) or `multipart` (a real `/images/edits` upload), overridable per node.
- **`custom_model` / free-text model**: anything missing from a dropdown, including new endpoint ids.
- **`extra_json`**: shallow-merged into the request body, so new parameters need no code change.
- **Errors that explain themselves**: a 403 names the surface you hit and where the key probably belongs; bad sizes say what is required.
- **Standard library only**: image decoding uses ComfyUI's own torch / numpy / Pillow.

## Install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/wzwei1990/comfyui-ark-flex.git ComfyUI-ArkFlex
```

Restart ComfyUI; the nodes appear under **Ark / 火山方舟**.

## Configure (two settings pages, eight entries)

**Settings → 方舟 Ark**

| Group | Setting | Written to `config.json` |
| --- | --- | --- |
| 密钥 | Standard API key (/api/v3) | `ark.standard.api_key` |
| 密钥 | Agent Plan key (/api/plan/v3) | `ark.agent-plan.api_key` |
| 图片 | Default image surface | `defaults.image` |
| 视频 | Default video surface | `defaults.video` |

**Settings → OpenAI 兼容**

| Group | Setting | Written to `config.json` |
| --- | --- | --- |
| 连接 | base_url (up to the version segment) | `openai.apiyi.base_url` |
| 连接 | API key | `openai.apiyi.api_key` |
| 连接 | Reference mode (json / multipart / none) | `openai.apiyi.refs_mode` |
| 图片 | Default model | `openai.apiyi.model` |

- Pasting a key writes it into the pack's `config.json` immediately; the field becomes a `✅ saved` marker (not blank, so a save never looks like a no-op).
- You can also edit `config.json` by hand (see `config.example.json`) or set `ARK_API_KEY` (Ark only).
- Resolution order: `node override → config section → ARK_API_KEY (Ark only) → built-in default`.

```jsonc
{
  "ark": {
    "standard":   { "base_url": "https://ark.cn-beijing.volces.com/api/v3",      "api_key": "…" },
    "agent-plan": { "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3", "api_key": "…" }
  },
  "openai": {
    "apiyi": { "base_url": "https://your-relay/v1", "api_key": "…", "refs_mode": "json", "model": "your model name" }
  },
  "defaults": { "image": "standard", "video": "standard" }
}
```

An older `profiles` (+ `kind`) file is migrated on read — no key needs re-entering.

## Reference mode (refs_mode)

| Value | Behaviour | Fits |
| --- | --- | --- |
| `json` | Reference images as data URLs in the body's `image` field | Ark and most relays |
| `multipart` | A real `POST /images/edits` upload | OpenAI proper, or services that require it |
| `none` | No references allowed | Text-to-image only |

Start with `json`; if an image-to-image call returns 400 / 415 / "unsupported", switch to `multipart`. The node's own `refs_mode` overrides the setting for one call.

## Sizes

- `ArkImage`: the `size` preset, or `width` + `height` (both above zero; **Ark requires multiples of 16**).
- `OpenAIImage`: a `size` string such as `1024x1024`, or `width` + `height` (no 16-multiple rule).
- `ArkVideo`: `width`/`height` map onto Ark's `ratio` + resolution tier; `length` (frames) becomes 4–30 seconds via `fps`.

## Uninstall

Delete `custom_nodes/ComfyUI-ArkFlex` and restart. Nodes, settings entries and keys go with it.

## Tests

```bash
python3 -m unittest discover -s tests
```

Offline: endpoint resolution, migration, payloads, multipart framing, size validation, video mapping.

## License

MIT. Protocol details were cross-checked against `HinaAyanami/comfyui-ark-nodes` and `fkxianzhou/ComfyUI-Jimeng-API` (both MIT).
