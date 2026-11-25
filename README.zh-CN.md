# Ark Flex · ComfyUI 节点（方舟 Seedream / Seedance + OpenAI 兼容图片）

三个节点，各管一件事：

| 节点 | 负责 | 连接来自 |
| --- | --- | --- |
| `ArkImage` | 火山方舟 **Seedream** 图片（文生图 / 图生图） | 设置 → **方舟 Ark** |
| `OpenAIImage` | **任何 OpenAI 兼容图片接口**（apiyi 等中转、官方 `/v1`） | 设置 → **OpenAI 兼容** |
| `ArkVideo` | 火山方舟 **Seedance** 视频（文生 / 首帧 / 首尾帧 / 参考图） | 设置 → **方舟 Ark** |

两家的设置、下拉、节点都是分开的 —— 不会出现"一个 profile 下拉里混着方舟和第三方中转"。

## 为什么需要它

火山方舟有**两套 API 入口**，请求体一样，但 **Key 不通用**：

| 入口 | Base URL | 说明 |
| --- | --- | --- |
| 标准 API | `https://ark.cn-beijing.volces.com/api/v3` | `/images/generations`、`/contents/generations/tasks` |
| Agent Plan | `https://ark.cn-beijing.volces.com/api/plan/v3` | 请求体一致，**必须用 Agent Plan 控制台的 Key** |

用标准 Key 打 Agent Plan 地址会 **403**，反过来也一样。多数现成节点把标准地址写死，于是 Agent Plan 的 Key 直接不可用。

本包把"入口"做成 **profile（接入面）**：一个有名字的 `(base_url, api_key)` 组合，按节点选择；图片和视频可以各走一套。第三方 OpenAI 兼容接口则单独归到 `openai` 那一节，和方舟互不影响。

## 特性

- **方舟 / OpenAI 兼容彻底分开**：两个图片节点、两页设置、两段配置，不共用下拉。
- **按节点选接入面**：`standard`、`agent-plan`，或自己加的方舟 profile；单次调用可用 `base_url_override` / `api_key_override` 覆盖。
- **Key 存在插件目录**：`custom_nodes/ComfyUI-ArkFlex/config.json`（已 gitignore），**卸载 = 删目录 = Key 一起消失**，ComfyUI 全局设置里不留明文。
- **参考图两种送法**：`json`（data URL，方舟与多数中转）或 `multipart`（真正的 `/images/edits` 上传）；节点上可单独覆盖。
- **`custom_model` / 自定义模型**：下拉没有的模型、端点 id 直接填（新的 `doubao-*` 就靠它）。
- **`extra_json`**：浅合并进请求体，接口新增参数不用改代码。
- **报错能看懂**：403 会说明当前指向哪个入口、Key 很可能属于另一个；尺寸不合法会直接说要求。
- **零三方依赖**：只用标准库；图片解码用 ComfyUI 自带的 torch / numpy / Pillow。

## 安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/wzwei1990/comfyui-ark-flex.git ComfyUI-ArkFlex
```

重启 ComfyUI，节点分类里出现 **Ark / 火山方舟**。

## 配置（两页设置，八个项）

**ComfyUI 设置 → 方舟 Ark**

| 二级 | 设置项 | 写到 `config.json` |
| --- | --- | --- |
| 密钥 | 标准 API Key（/api/v3） | `ark.standard.api_key` |
| 密钥 | Agent Plan Key（/api/plan/v3） | `ark.agent-plan.api_key` |
| 图片 | 图片默认接入面（standard / agent-plan） | `defaults.image` |
| 视频 | 视频默认接入面 | `defaults.video` |

**ComfyUI 设置 → OpenAI 兼容**

| 二级 | 设置项 | 写到 `config.json` |
| --- | --- | --- |
| 连接 | 接口地址（base_url，到版本号为止） | `openai.apiyi.base_url` |
| 连接 | API Key | `openai.apiyi.api_key` |
| 连接 | 参考图传输方式（json / multipart / none） | `openai.apiyi.refs_mode` |
| 图片 | 默认模型 | `openai.apiyi.model` |

- 粘贴 Key 后会**立即写入插件目录的 `config.json`**，字段变成 `✅ 已保存到 config.json（卸载插件即清除）` 的标记（不是空白，避免"以为没填上"）；再粘一次即覆盖。
- 也可以手写 `config.json`（照 `config.example.json`），或用环境变量 `ARK_API_KEY`（仅方舟）。
- 优先级：`节点覆盖 → config.json 对应区间 → ARK_API_KEY（仅方舟）→ 内置默认`。

```jsonc
// config.json
{
  "ark": {
    "standard":   { "base_url": "https://ark.cn-beijing.volces.com/api/v3",      "api_key": "…" },
    "agent-plan": { "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3", "api_key": "…" }
  },
  "openai": {
    "apiyi": { "base_url": "https://你的中转/v1", "api_key": "…", "refs_mode": "json", "model": "gpt-image-2.5-sunburst-vip" }
  },
  "defaults": { "image": "standard", "video": "standard" }
}
```

旧版本（`profiles` + `kind`）的配置在读取时会**自动迁移**到上面两段，不用重填 Key。

## 参考图传输方式（refs_mode）

图生图 / 带参考图时，参考图怎么送到接口：

| 值 | 行为 | 适用 |
| --- | --- | --- |
| `json` | 参考图转成 data URL，放进 JSON body 的 `image` 字段 | 方舟、多数第三方中转（apiyi 等） |
| `multipart` | `POST /images/edits`，真正的多文件上传 | OpenAI 官方接口或要求标准 edits 形态的服务 |
| `none` | 不允许参考图 | 只做文生图，或该接口不支持 |

不知道就保持 `json`；如果图生图报 400 / 415 / "unsupported"，改成 `multipart`。节点上的 `refs_mode` 可对单个节点覆盖。

## 尺寸

- `ArkImage`：`size` 预设，或同时填 `width`/`height`（两者都 >0 才生效；**方舟要求 16 的倍数**）。
- `OpenAIImage`：`size` 字符串（如 `1024x1024`），或 `width`/`height` 覆盖（不限 16 的倍数）。
- `ArkVideo`：`width`/`height` 会映射到方舟的 `ratio` + 分辨率档，`length`（帧）按 `fps` 换算成 4–30 秒。

## 卸载

删掉 `custom_nodes/ComfyUI-ArkFlex` 并重启 —— 节点、设置项、Key 一起消失，没有残留。

## 测试

```bash
python3 -m unittest discover -s tests
```

离线运行（网络与 torch 都被隔离）：端点解析、迁移、请求体、multipart 帧格式、尺寸校验、视频换算。

## 许可

MIT。协议细节参考了 `HinaAyanami/comfyui-ark-nodes` 与 `fkxianzhou/ComfyUI-Jimeng-API`（均为 MIT）。
