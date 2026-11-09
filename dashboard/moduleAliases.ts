import { fileURLToPath, URL } from "node:url";
import { compilerOptions } from "./tsconfig.json";

export const moduleAliases = Object.entries(compilerOptions.paths).map(([alias, [target]]) => ({
  find: alias.replace(/\/\*$/, ""),
  replacement: fileURLToPath(new URL(target.replace(/\/\*$/, ""), import.meta.url)),
}));
