import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const devOnlyModule = /[/\\]src[/\\](?:mocks[/\\]|shared[/\\]api[/\\]devBridge\.ts$|widgets[/\\]dev-bar[/\\])/;

const classicScriptPlugin = (): Plugin => ({
  name: "classic-script-plugin",
  apply: "build",
  generateBundle(_options, bundle) {
    for (const chunk of Object.values(bundle)) {
      if (chunk.type === "chunk" && Object.keys(chunk.modules).some((id) => devOnlyModule.test(id))) {
        this.error("生产构建包含开发模式或 mock 模块");
      }
    }
  },
  transformIndexHtml(html: string) {
    return html
      .replace(/<script\s+type=["']module["']\s+crossorigin\b/gi, "<script defer")
      .replace(/<script\s+type=["']module["']\b/gi, "<script defer")
      .replace(/\s+crossorigin(?:=["'][^"']*["'])?/gi, "");
  },
});

export default defineConfig({
  base: "./",
  plugins: [react(), classicScriptPlugin()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    outDir: "../pages/daily-analysis",
    emptyOutDir: true,
    cssCodeSplit: false,
    assetsInlineLimit: 150000,
    chunkSizeWarningLimit: 5000,
    rollupOptions: {
      treeshake: {
        moduleSideEffects: (id) => !devOnlyModule.test(id),
      },
      output: {
        format: "iife",
        name: "DailyAnalysisApp",
        inlineDynamicImports: true,
        entryFileNames: "assets/index.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name].[ext]",
      },
    },
  },
  server: {
    port: 5175,
    proxy: {
      "/api/plugins/astrbot_plugin_qq_group_daily_analysis": {
        target: "http://localhost:6185",
        changeOrigin: true,
      },
    },
  },
});

