import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

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
