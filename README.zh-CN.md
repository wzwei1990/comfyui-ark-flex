# Ark Flex · ComfyUI 火山方舟节点（Seedream / Seedance）

两个节点，覆盖**火山方舟的 Seedream 图片**和 **Seedance 视频**。它只解决一个最容易被卡住的问题：

火山方舟有**两套 API 入口**，请求体一样，但 **Key 不通用**。

| 入口 | Base URL | 说明 |
| --- | --- | --- |
| 标准 API | `https://ark.cn-beijing.volces.com/api/v3` | `/images/generations`、`/contents/generations/tasks` |
| Agent Plan | `https://ark.cn-beijing.volces.com/api/plan/v3` | 请求体一致，**必须用 Agent Plan 控制台的 Key** |

用标准 Key 打 Agent Plan 地址会 **403**，反过来也一样。多数现成节点把标准地址写死，于是 Agent Plan 的 Key 直接不可用。

本包把"入口"做成 **profile（接入面）**：一个有名字的 `(base_url, api_key)` 组合。每个节点上都有一个 `profile` 下拉，因此**图片可以走标准入口、视频走 Agent Plan**，或者任意组合。

## 特性

- **按节点选接入面**：`standard`、`agent-plan`，或在 `config.json` 里自己加 profile；单次调用还能用 `base_url_override` / `api_key_override` 覆盖。
- **图片与视频各自独立**：两个节点分别解析自己的 profile，互不影响。
- **`custom_model`**：下拉里没有的模型 / 端点 id 直接填（新的 `doubao-seedance-*` 就靠它）。
- **`extra_json`**：浅合并进请求体，方舟新增参数不用改代码。
- **报错能看懂**：403 会直接告诉你当前 profile 指向哪个入口、Key 很可能属于另一个入口。
- **零三方依赖**：只用标准库；图片解码用 ComfyUI 自带的 torch / numpy / Pillow。

## 安装

```bash
cd ComfyUI/custom_nodes
git clone <本仓库地址> ComfyUI-ArkFlex
```

重启 ComfyUI，节点分类里会出现 **Ark / 火山方舟**。

## 配置

**Key 有三种填法，最省事的是第一种：**

1. **ComfyUI 设置面板**（不用碰文件）：`设置 → Ark Flex` 里有两个输入框 —— **标准 API Key（/api/v3）** 与 **Agent Plan Key（/api/plan/v3）**。ComfyUI 会把它们存进 `user/default/comfy.settings.json`，插件直接读这个文件，所有节点共享。
2. **`config.json` 的 `profiles.<名字>.api_key`**（适合一台机器多套配置）
3. **节点上的 `api_key_override`**（临时、只对该节点这一次生效）

也可以完全不填，交给环境变量 `ARK_API_KEY`。

先复制一份配置模板（只在用第 2 种方式时需要）：

```bash
cp config.example.json config.json
```

每个字段的取值顺序（先命中者优先）：

```
节点覆盖  ->  profile 条目  ->  ComfyUI 设置面板  ->  ARK_API_KEY  ->  内置默认
```

`config.json` 已加入 `.gitignore`：Key 只留在你本机。

## 节点

### Ark 图片 · Seedream
`prompt`、`model`、`size`（像素预设，按像素台阶计费，别用 2048×2048 正方形）、`max_images`（1–4，内部按 `seed + i` 连发）、`seed`、`watermark`、可选 `image1..4` 参考图、`custom_model`、`extra_json`。
输出 `IMAGE` 批次 + 信息字符串。

### Ark 视频 · Seedance
`prompt`、`model`、`mode`（文生 / 首帧 / 首尾帧 / 参考图）、`resolution`、`ratio`、`duration`（4–30 秒）、`generate_audio`、`output_format`、`seed`、`watermark`、`timeout`、`poll_seconds`，可选 `first_frame`、`last_frame`、`ref_image1..3`、`custom_model`、`extra_json`。
输出 `VIDEO` + 信息字符串（宿主没有 `VIDEO` 类型时只给文件路径）。本地参考图会转成 base64 data URL，**不需要上传**。

成片保存到 `output/ark/video/`。

## 关于模型 id

模型 id 变化很快。下拉里是写这个包时已知的值；你的模型不在里面时，填 **`custom_model`**（或方舟控制台里的端点 id `ep-...`）。这是刻意的取舍：与其维护一张会过期的清单，不如留一个输入框。

## 测试

```bash
python -m unittest discover -s tests -v
```

测试完全离线：覆盖 profile 解析优先级、各视频模式的 payload 组装、尺寸解析、错误文案、data URL 路径（张量编码器被 stub 掉，因为 torch 属于 ComfyUI 运行时依赖）。

## 参考

实现前读过 `HinaAyanami/comfyui-ark-nodes` 与 `fkxianzhou/ComfyUI-Jimeng-API`（均为 MIT）：协议细节与 Agent Plan 地址的坑来自它们和火山官方文档。本包的不同点是把"接入面"做成一等公民、按节点可选。

## 许可

MIT，见 [LICENSE](LICENSE)。
