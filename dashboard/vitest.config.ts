import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { moduleAliases } from "./moduleAliases";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: moduleAliases,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
