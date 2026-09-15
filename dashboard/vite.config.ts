import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const classicScriptPlugin = () => ({
  name: "classic-script-plugin",
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
  },
});

