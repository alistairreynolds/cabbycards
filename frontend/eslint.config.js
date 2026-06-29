import { defineConfigWithVueTs, vueTsConfigs } from "@vue/eslint-config-typescript"
import pluginVue from "eslint-plugin-vue"

export default defineConfigWithVueTs(
  { name: "app/files", files: ["**/*.{ts,vue}"] },
  { name: "app/ignores", ignores: ["dist/**", "coverage/**"] },
  pluginVue.configs["flat/essential"],
  vueTsConfigs.recommended,
  {
    rules: {
      // Mirror the project convention: no nested ternaries.
      "no-nested-ternary": "error",
    },
  },
)
