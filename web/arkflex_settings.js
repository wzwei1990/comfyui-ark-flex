import { app } from "../../scripts/app.js";

// Two text fields in ComfyUI's own Settings dialog. ComfyUI persists them to
// user/default/comfy.settings.json, which the Python side reads — so the key is
// typed once, in the UI, and every Ark node picks it up.
//
// The ids must match ark/settings.py: ArkFlex.StandardApiKey / ArkFlex.PlanApiKey.
app.registerExtension({
  name: "ArkFlex.Settings",
  settings: [
    {
      id: "ArkFlex.StandardApiKey",
      name: "Ark Flex · 标准 API Key（/api/v3）",
      type: "text",
      defaultValue: "",
      tooltip:
        "火山方舟标准入口的 Key。与 Agent Plan 的 Key 不通用；留空时回退到 config.json 的 profile，再回退到环境变量 ARK_API_KEY。",
      attrs: { autocomplete: "off" },
    },
    {
      id: "ArkFlex.PlanApiKey",
      name: "Ark Flex · Agent Plan Key（/api/plan/v3）",
      type: "text",
      defaultValue: "",
      tooltip:
        "Agent Plan 控制台的 Key。profile 选 agent-plan（或 base_url 指向 /api/plan/v3）时使用。",
      attrs: { autocomplete: "off" },
    },
  ],
});
