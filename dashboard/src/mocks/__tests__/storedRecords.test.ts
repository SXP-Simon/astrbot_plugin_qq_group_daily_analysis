import { expect, it } from "vitest";
import { managedRecordMockHandlers as handlers } from "../data/managedRecords";
it("存档和头像示例足够跨页，按键倒序排列且列表不加载头像内容", () => {
  for (const kind of ["history", "avatar"]) {
    const first = handlers["GET plugin-data/records"]({ kind, page: 1 }).data;
    const second = handlers["GET plugin-data/records"]({ kind, page: 2 }).data;
    expect(first.total).toBeGreaterThan(20);
    expect(first.items).toHaveLength(20);
    expect(second.items.length).toBeGreaterThan(0);
    const names = [...first.items, ...second.items].map((item) => item.name);
    expect(new Set(names).size).toBe(names.length);
    expect(names).toEqual([...names].sort().reverse());
    expect(first.items.every((item) => !("data" in item))).toBe(true);
    for (const item of second.items)
      expect(handlers["GET plugin-data/records/detail"](item.locator).status).toBe("ok");
  }
});
it("搜索大小写行为与后端一致，删除、导入立即反映到分页", () => {
  const query = { kind: "avatar", search: "DEMO-USER-01" };
  const list = handlers["GET plugin-data/records"](query).data;
  expect(list.total).toBe(1);
  const record = handlers["GET plugin-data/records/detail"](list.items[0].locator).data!;
  try {
    expect(
      handlers["POST plugin-data/records/mutate"]({ ...record, operation: "delete" }).status,
    ).toBe("ok");
    expect(handlers["GET plugin-data/records"](query).data.total).toBe(0);
  } finally {
    expect(
      handlers["POST plugin-data/records/mutate"]({ ...record, operation: "create" }).status,
    ).toBe("ok");
  }
  expect(handlers["GET plugin-data/records"](query).data.total).toBe(1);
});
