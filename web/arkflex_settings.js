import { app } from "../../scripts/app.js";

// Two text fields in ComfyUI's own Settings dialog, one per Ark surface.
//
// They are an *input* only. On change the value is POSTed to /arkflex/settings,
// which writes it into this pack's config.json (inside the node folder), and the
// field is then cleared so ComfyUI's global comfy.settings.json keeps no copy.
// That is what makes "delete the folder" a complete uninstall.
const ENDPOINT = "/arkflex/settings";
const FIELDS = [
  {
    id: "ArkFlex.StandardApiKey",
    key: "standard",
    name: "Ark Flex · 标准 API Key（/api/v3）",
  },
  {
    id: "ArkFlex.PlanApiKey",
    key: "agentPlan",
    name: "Ark Flex · Agent Plan Key（/api/plan/v3）",
  },
];

async function save(key, value) {
  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ [key]: value }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || !body || body.ok !== true) {
    throw new Error(body?.error || `HTTP ${response.status}`);
  }
  return body;
}

// The value goes to the pack's own file; the UI copy is blanked. A blank value
// (the second onChange fired by that clearing) is ignored.
async function adopt(settingId, key, value) {
  const text = typeof value === "string" ? value.trim() : "";
  if (text === "") return;
  try {
    await save(key, text);
    app.ui.settings.setSettingValue(settingId, "");
    console.info("[ArkFlex] key saved to custom_nodes/ComfyUI-ArkFlex/config.json (Ui copy cleared)");
  } catch (error) {
    console.error("[ArkFlex] could not save the key:", error);
    app.ui.dialog?.show?.(`Ark Flex：Key 保存失败 —— ${error?.message || error}`);
  }
}

app.registerExtension({
  name: "ArkFlex.Settings",
  settings: FIELDS.map(field => ({
    id: field.id,
    name: field.name,
    type: "text",
    defaultValue: "",
    tooltip:
      "粘贴 Key 后会保存到 custom_nodes/ComfyUI-ArkFlex/config.json，此处随即清空（不在 ComfyUI 全局设置里留副本）。卸载插件 = 删目录 = Key 一并消失。",
    attrs: { autocomplete: "off" },
    onChange(value) {
      void adopt(field.id, field.key, value);
    },
  })),

  async setup() {
    // Migration path: a value typed before this write-through existed still sits
    // in comfy.settings.json. Move it into the pack and clear the copy.
    for (const field of FIELDS) {
      const value = app.ui.settings.getSettingValue(field.id, "");
      if (typeof value === "string" && value.trim() !== "") {
        await adopt(field.id, field.key, value);
      }
    }
  },
});
