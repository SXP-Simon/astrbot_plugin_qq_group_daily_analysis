import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { build } from "vite";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("生产构建裁掉开发分支，同时保留经典脚本入口", async (t) => {
  const temporary = mkdtempSync(join(tmpdir(), "dashboard-production-"));
  t.after(() => {
    assert.equal(dirname(temporary), resolve(tmpdir()));
    rmSync(temporary, { recursive: true, force: true });
  });
  mkdirSync(join(temporary, "src/mocks"), { recursive: true });
  writeFileSync(join(temporary, "src/mocks/example.js"), 'globalThis.mockMarker = "MOCK_LEAK";');
  writeFileSync(
    join(temporary, "index.html"),
    '<html><body><script type="module" src="/src/main.js"></script></body></html>',
  );
  writeFileSync(
    join(temporary, "src/main.js"),
    'if (import.meta.env.DEV) import("./mocks/example.js"); globalThis.productionMarker = "PRODUCTION_OK";',
  );
  const result = await build({
    configFile: join(root, "vite.config.ts"),
    root: temporary,
    logLevel: "silent",
    build: { write: false, minify: false, emptyOutDir: false },
  });
  assert.ok(!Array.isArray(result) && "output" in result);
  const script = result.output.find((item) => item.type === "chunk");
  assert.ok(script && script.type === "chunk");
  assert.match(script.code, /PRODUCTION_OK/);
  assert.doesNotMatch(script.code, /MOCK_LEAK/);
  assert.equal(script.isEntry, true);
  assert.equal(script.imports.length, 0);
  assert.equal(script.dynamicImports.length, 0);
  const html = result.output.find((item) => item.fileName === "index.html");
  assert.ok(html && html.type === "asset" && typeof html.source === "string");
  assert.match(html.source, /<script defer/);
  assert.doesNotMatch(html.source, /type="module"/);
});

for (const modulePath of [
  "src/mocks/example.js",
  "src/shared/api/devBridge.ts",
  "src/widgets/dev-bar/DevToolbar.tsx",
]) {
  test(`生产构建拒绝意外带入 ${modulePath}`, async (t) => {
    const temporary = mkdtempSync(join(tmpdir(), "dashboard-production-leak-"));
    t.after(() => {
      assert.equal(dirname(temporary), resolve(tmpdir()));
      rmSync(temporary, { recursive: true, force: true });
    });
    const moduleFile = join(temporary, modulePath);
    mkdirSync(dirname(moduleFile), { recursive: true });
    writeFileSync(moduleFile, 'export const marker = "MOCK_LEAK";');
    writeFileSync(
      join(temporary, "index.html"),
      `<html><body><script type="module" src="/${modulePath}"></script><script type="module">import { marker } from "/${modulePath}"; globalThis.mockMarker = marker;</script></body></html>`,
    );
    await assert.rejects(
      build({
        configFile: join(root, "vite.config.ts"),
        root: temporary,
        logLevel: "silent",
        build: { write: false, emptyOutDir: false },
      }),
      /生产构建包含开发模式或 mock 模块/,
    );
  });
}

test("Oxlint preserves the existing quality gates", (t) => {
  const temporary = mkdtempSync(join(tmpdir(), "dashboard-lint-"));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const cases = [
    ["any", "export const value: any = 1;", "no-explicit-any"],
    ["unused", "const unused = 1; export {};", "no-unused-vars"],
    [
      "hooks",
      'import { useEffect } from "react"; export function View({ flag }: { flag: boolean }) { if (flag) useEffect(() => {}, []); return null; }',
      "rules-of-hooks",
    ],
    [
      "dependencies",
      'import { useEffect } from "react"; export function View({ value }: { value: string }) { useEffect(() => { console.log(value); }, []); return null; }',
      "exhaustive-deps",
    ],
    [
      "refresh",
      "export function View() { return <div />; } export function calculate() { return 1; }",
      "only-export-components",
    ],
    ["directive", "// oxlint-disable-next-line no-debugger\nexport const value = 1;", "Unused"],
    [
      "valid",
      'import { useEffect } from "react"; export const LABEL = "ok"; export function View({ value, _reserved }: { value: string; _reserved?: string }) { useEffect(() => { console.log(value); }, [value]); return <div>{value}</div>; }',
      null,
    ],
  ];
  for (const [name, source, rule] of cases) {
    const file = join(temporary, `${name}.tsx`);
    writeFileSync(file, source);
    const result = spawnSync(
      process.execPath,
      [
        join(root, "node_modules/oxlint/bin/oxlint"),
        "--config",
        join(root, ".oxlintrc.json"),
        "--deny-warnings",
        "--report-unused-disable-directives",
        file,
      ],
      { cwd: root, encoding: "utf8" },
    );
    assert.equal(result.error, undefined);
    const output = result.stdout + result.stderr;
    assert.equal(result.status, rule ? 1 : 0, `${name}: ${output}`);
    if (rule) assert.match(output.toLowerCase(), new RegExp(rule.toLowerCase()));
  }
});

test("Oxfmt checks without writing and produces stable formatting", (t) => {
  const temporary = mkdtempSync(join(tmpdir(), "dashboard-format-"));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const file = join(temporary, "example.ts");
  const original = "export const greeting={text:'hello'}";
  writeFileSync(file, original);
  for (const [mode, status] of [
    ["--check", 1],
    ["--write", 0],
    ["--check", 0],
  ]) {
    const result = spawnSync(
      process.execPath,
      [
        join(root, "node_modules/oxfmt/bin/oxfmt"),
        "--config",
        join(root, ".oxfmtrc.json"),
        mode,
        file,
      ],
      { cwd: root, encoding: "utf8" },
    );
    assert.equal(result.error, undefined);
    assert.equal(result.status, status, result.stdout + result.stderr);
    if (status === 1) assert.equal(readFileSync(file, "utf8"), original);
  }
});
