import { expect, it } from "vitest";
import { mockConfigBackups } from "../../../../mocks/data/configBackups";
import {
  configBackupDetailSchema,
  configBackupListSchema,
} from "../configBackup";

it("备份契约保留当前 Schema 不认识的嵌套键值，允许旧文件缺少版本和时间", () => {
  expect(
    configBackupListSchema.parse({
      items: mockConfigBackups.map((item) => item.backup),
    }).items,
  ).toHaveLength(3);
  for (const backup of mockConfigBackups)
    expect(configBackupDetailSchema.parse(backup)).toEqual(backup);
});

it.each([null, [1, false, null], "旧文本", { unknown: { old: true } }])(
  "任意 JSON 根结构均可读取：%j",
  (content) => {
    expect(
      configBackupDetailSchema.parse({ ...mockConfigBackups[0], content })
        .content,
    ).toEqual(content);
  },
);

it("API 边界拒绝无效元数据和非 JSON 内容", () => {
  expect(
    configBackupDetailSchema.safeParse({
      ...mockConfigBackups[0],
      content: undefined,
    }).success,
  ).toBe(false);
  expect(
    configBackupListSchema.safeParse({ items: [{ filename: "x.json" }] })
      .success,
  ).toBe(false);
});
