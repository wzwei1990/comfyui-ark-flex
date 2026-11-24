import { app } from "../../scripts/app.js";

// Two key fields and two "which surface is default" pickers, all in ComfyUI's
// own Settings dialog.
//
// The key fields are an *input* only: on change the value is POSTed to
// /arkflex/settings, which writes it into this pack's config.json (inside the
// node folder), and the field is then replaced by a short "saved" marker. The
// marker is not a secret — it makes the save visible, where a blank field reads
// as "nothing happened". ComfyUI therefore keeps no copy of the key, so deleting
// the folder is a complete uninstall.
const ENDPOINT = "/arkflex/settings";

// Must match SAVED_MARKER in ark/settings.py: a value equal to this is ignored
// when the Python side reads the legacy settings file.
const MARKER = "✅ 已保存到 config.json（卸载插件即清除）";

const SURFACES = [
  { value: "standard", text: "标准 API（/api/v3）" },
  { value: "agent-plan", text: "Agent Plan（/api/plan/v3）" },
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

// The value goes to the pack's file; the field is left showing a marker. A blank
// value or the marker itself (the second onChange fired by that write) is ignored.
async function adoptKey(settingId, key, value) {
  const text = typeof value === "string" ? value.trim() : "";
  if (text === "" || text === MARKER) return;
  try {
    await post({ [key]: text });
    app.ui.settings.setSettingValue(settingId, MARKER);
  } catch (error) {
    complain(error);
  }
}

async function adoptSurface(key, value) {
  if (value !== "standard" && value !== "agent-plan") return;
  try {
    await post({ [key]: value });
  } catch (error) {
    complain(error);
  }
}

app.registerExtension({
  name: "ArkFlex.Settings",
  settings: [
    {
      id: "ArkFlex.StandardApiKey",
      name: "Ark Flex · 标准 API Key（/api/v3）",
      category: ["Ark Flex"],
      type: "text",
      defaultValue: "",
      tooltip:
        "粘贴即保存到 custom_nodes/ComfyUI-ArkFlex/config.json，字段会变成「已保存」标记，不在 ComfyUI 全局设置里留明文。再粘一次即覆盖。",
      attrs: { autocomplete: "off" },
      onChange(value) {
        void adoptKey("ArkFlex.StandardApiKey", "standard", value);
      },
    },
    {
      id: "ArkFlex.PlanApiKey",
      name: "Ark Flex · Agent Plan Key（/api/plan/v3）",
      category: ["Ark Flex"],
      type: "text",
      defaultValue: "",
      tooltip:
        "同上，写入本插件目录。Agent Plan 的 Key 与标准入口不通用；粘错入口会得到 403（节点会直接说明）。",
      attrs: { autocomplete: "off" },
      onChange(value) {
        void adoptKey("ArkFlex.PlanApiKey", "agentPlan", value);
      },
    },
    {
      id: "ArkFlex.ImageSurface",
      name: "Ark Flex · 图片默认接入面",
      category: ["Ark Flex"],
      type: "combo",
      options: SURFACES,
      defaultValue: "standard",
      tooltip: "写入 config.json 的 defaults.image。图片和视频可以各走一套入口。",
      onChange(value) {
        void adoptSurface("imageDefault", value);
      },
    },
    {
      id: "ArkFlex.VideoSurface",
      name: "Ark Flex · 视频默认接入面",
      category: ["Ark Flex"],
      type: "combo",
      options: SURFACES,
      defaultValue: "standard",
      tooltip: "写入 config.json 的 defaults.video。",
      onChange(value) {
        void adoptSurface("videoDefault", value);
      },
    },
  ],

  async setup() {
    // Migration: a key typed before the write-through existed still sits in
    // comfy.settings.json. Move it into the pack and leave the marker behind.
    for (const [id, key] of [
      ["ArkFlex.StandardApiKey", "standard"],
      ["ArkFlex.PlanApiKey", "agentPlan"],
    ]) {
      const value = app.ui.settings.getSettingValue(id, "");
      if (typeof value === "string" && value.trim() !== "" && value.trim() !== MARKER) {
        await adoptKey(id, key, value);
      }
    }
    // Show the stored defaults, so the pickers are not lying about config.json.
    try {
      const response = await fetch(ENDPOINT);
      const body = await response.json();
      const defaults = body?.defaults || {};
      for (const [id, key] of [
        ["ArkFlex.ImageSurface", "image"],
        ["ArkFlex.VideoSurface", "video"],
      ]) {
        const value = defaults[key];
        if ((value === "standard" || value === "agent-plan") && app.ui.settings.getSettingValue(id) !== value) {
          app.ui.settings.setSettingValue(id, value);
        }
      }
    } catch (error) {
      console.warn("[ArkFlex] could not read the saved defaults:", error);
    }
  },
});
