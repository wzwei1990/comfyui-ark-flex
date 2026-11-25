import { app } from "../../scripts/app.js";

// Two provider pages in ComfyUI's Settings dialog:
//
//   方舟 Ark      → 密钥（标准 / Agent Plan）  · 图片（默认接入面） · 视频（默认接入面）
//   OpenAI 兼容   → 连接（地址 / Key / 参考图方式） · 图片（默认模型）
//
// ComfyUI groups settings by `category[0]` / `category[1]`, which is why both
// levels are given explicitly — an id like `Ark.StandardApiKey` alone would put
// each entry in its own sub-group.
//
// Secrets are write-only from this dialog: on change they are POSTed to
// /arkflex/settings (which writes the pack's config.json) and the field is
// replaced by a marker. Nothing secret stays in comfy.settings.json, so
// deleting the node folder is a complete uninstall.
const ENDPOINT = "/arkflex/settings";

// Must match the marker string the dialog writes; it is never sent as a key.
const MARKER = "✅ 已保存到 config.json（卸载插件即清除）";

const ARK_SURFACES = [
  { value: "standard", text: "标准 API（/api/v3）" },
  { value: "agent-plan", text: "Agent Plan（/api/plan/v3）" },
];

const REFS_MODES = [
  { value: "json", text: "json — data URL（方舟 / 多数中转）" },
  { value: "multipart", text: "multipart — /images/edits 上传（OpenAI 官方）" },
  { value: "none", text: "none — 不接受参考图" },
];

async function post(payload) {
  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || !body || body.ok !== true) {
    throw new Error(body?.error || `HTTP ${response.status}`);
  }
  return body;
}

function complain(error) {
  console.error("[ArkFlex] save failed:", error);
  app.ui.dialog?.show?.(`Ark Flex：保存失败 —— ${error?.message || error}`);
}

// A secret: save it, then show the marker. Blank or marker values (a second
// onChange fired by that write) are ignored.
async function adoptSecret(settingId, field, value) {
  const text = typeof value === "string" ? value.trim() : "";
  if (text === "" || text === MARKER) return;
  try {
    await post({ [field]: text });
    app.ui.settings.setSettingValue(settingId, MARKER);
  } catch (error) {
    complain(error);
  }
}

async function adopt(settingId, field, value) {
  if (typeof value !== "string") return;
  try {
    await post({ [field]: value });
  } catch (error) {
    complain(error);
    return;
  }
  if (settingId === "OpenAI.RefsMode") return;
}

// Plain values (addresses, model names) are mirrored back into the field so the
// dialog shows what config.json actually says.
async function adoptVisible(field, value) {
  if (typeof value !== "string" || value.trim() === "") return;
  try {
    await post({ [field]: value.trim() });
  } catch (error) {
    complain(error);
  }
}

const SECRETS = [
  ["Ark.StandardApiKey", "arkStandard"],
  ["Ark.PlanApiKey", "arkPlan"],
  ["OpenAI.ApiKey", "openaiApiKey"],
];

app.registerExtension({
  name: "ArkFlex.Settings",
  settings: [
    {
      id: "Ark.StandardApiKey",
      name: "标准 API Key（/api/v3）",
      category: ["方舟 Ark","密钥","标准 API Key（/api/v3）"],
      type: "text",
      defaultValue: "",
      tooltip: "粘贴即保存到 custom_nodes/ComfyUI-ArkFlex/config.json，字段变成「已保存」标记；再粘一次即覆盖。",
      attrs: { autocomplete: "off" },
      onChange(value) {
        void adoptSecret("Ark.StandardApiKey", "arkStandard", value);
      },
    },
    {
      id: "Ark.PlanApiKey",
      name: "Agent Plan Key（/api/plan/v3）",
      category: ["方舟 Ark","密钥","Agent Plan Key（/api/plan/v3）"],
      type: "text",
      defaultValue: "",
      tooltip: "Agent Plan 控制台的 Key；与标准入口不通用，粘错入口会得到 403（节点会说明）。",
      attrs: { autocomplete: "off" },
      onChange(value) {
        void adoptSecret("Ark.PlanApiKey", "arkPlan", value);
      },
    },
    {
      id: "Ark.ImageSurface",
      name: "图片默认接入面",
      category: ["方舟 Ark","图片","图片默认接入面"],
      type: "combo",
      options: ARK_SURFACES,
      defaultValue: "standard",
      tooltip: "Ark 图片节点上 profile 选「自定义」时的回退；一般节点上选 profile 就够了。",
      onChange(value) {
        void adopt("Ark.ImageSurface", "imageDefault", value);
      },
    },
    {
      id: "Ark.VideoSurface",
      name: "视频默认接入面",
      category: ["方舟 Ark","视频","视频默认接入面"],
      type: "combo",
      options: ARK_SURFACES,
      defaultValue: "standard",
      tooltip: "视频只支持方舟；这里决定默认走标准入口还是 Agent Plan。",
      onChange(value) {
        void adopt("Ark.VideoSurface", "videoDefault", value);
      },
    },
    {
      id: "OpenAI.BaseUrl",
      name: "接口地址（base_url）",
      category: ["OpenAI 兼容","连接","接口地址（base_url）"],
      type: "text",
      defaultValue: "",
      tooltip: "到版本号为止，例如 https://你的中转/v1 。保存到 config.json 的 openai.apiyi.base_url。",
      onChange(value) {
        void adoptVisible("openaiBaseUrl", value);
      },
    },
    {
      id: "OpenAI.ApiKey",
      name: "API Key",
      category: ["OpenAI 兼容","连接","API Key"],
      type: "text",
      defaultValue: "",
      tooltip: "粘贴即保存进插件目录；字段变成「已保存」标记，不在 ComfyUI 全局设置里留明文。",
      attrs: { autocomplete: "off" },
      onChange(value) {
        void adoptSecret("OpenAI.ApiKey", "openaiApiKey", value);
      },
    },
    {
      id: "OpenAI.RefsMode",
      name: "参考图传输方式",
      category: ["OpenAI 兼容","连接","参考图传输方式"],
      type: "combo",
      options: REFS_MODES,
      defaultValue: "json",
      tooltip:
        "图生图时怎么送参考图：json=塞进 JSON body 的 image 字段（方舟 / 多数中转）；multipart=真正的 /images/edits 上传（OpenAI 官方）；none=不允许参考图。不确定就用 json。",
      onChange(value) {
        void adopt("OpenAI.RefsMode", "openaiRefsMode", value);
      },
    },
    {
      id: "OpenAI.DefaultModel",
      name: "默认模型",
      category: ["OpenAI 兼容","图片","默认模型"],
      type: "text",
      defaultValue: "",
      tooltip: "节点上 model 留空时使用；也可以直接写进节点。",
      onChange(value) {
        void adoptVisible("openaiModel", value);
      },
    },
  ],

  async setup() {
    // Secrets arrive as markers so the dialog reflects "already saved".
    for (const [id, field] of SECRETS) {
      const current = app.ui.settings.getSettingValue(id, "");
      if (typeof current === "string" && current.trim() !== "" && current.trim() !== MARKER) {
        // A value typed before this version: move it into config.json.
        await adoptSecret(id, field, current);
      }
    }
    // Visible values come from config.json, so they are never stale.
    try {
      const response = await fetch(ENDPOINT);
      const body = await response.json();
      const ark = body?.ark || {};
      const openai = body?.openai || {};
      const defaults = body?.defaults || {};
      const setIfDifferent = (id, value) => {
        if (typeof value !== "string" || value === "") return;
        if (app.ui.settings.getSettingValue(id, "") === value) return;
        app.ui.settings.setSettingValue(id, value);
      };
      setIfDifferent("OpenAI.BaseUrl", openai.baseUrl);
      setIfDifferent("OpenAI.DefaultModel", openai.model);
      if (typeof openai.refsMode === "string" && openai.refsMode) {
        app.ui.settings.setSettingValue("OpenAI.RefsMode", openai.refsMode);
      }
      for (const [id, saved] of [
        ["Ark.StandardApiKey", ark.standard],
        ["Ark.PlanApiKey", ark.agentPlan],
        ["OpenAI.ApiKey", openai.apiKey],
      ]) {
        if (saved && app.ui.settings.getSettingValue(id, "") !== MARKER) {
          app.ui.settings.setSettingValue(id, MARKER);
        }
      }
      if (defaults.image === "standard" || defaults.image === "agent-plan") {
        app.ui.settings.setSettingValue("Ark.ImageSurface", defaults.image);
      }
      if (defaults.video === "standard" || defaults.video === "agent-plan") {
        app.ui.settings.setSettingValue("Ark.VideoSurface", defaults.video);
      }
    } catch (error) {
      console.warn("[ArkFlex] could not read the saved settings:", error);
    }
  },
});
