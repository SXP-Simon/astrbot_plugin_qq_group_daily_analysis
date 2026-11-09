import { expect, it } from "vitest";
import { mockHandlers } from "@/mocks/handlers";
import { mockReportHistory } from "@/mocks/data/reports";

it("历史群聊选项保留跨平台同号群，查询先按平台筛选再分页", () => {
  const groups = mockHandlers["GET groups"]({ by_session: true }).data;
  const same = groups.filter((group) => group.group_id === "123456789");
  expect(new Set(same.map((group) => group.platform))).toEqual(new Set(["aiocqhttp", "telegram"]));
  const list = mockHandlers["GET traces"]({
    platform: "telegram",
    group_id: "123456789",
    limit: 1,
  }).data;
  expect(list.total).toBe(1);
  expect(list.items[0].group_name).toBe("摄影交流示例群");
  expect(mockHandlers["GET traces"]({ platform: "" }).data.total).toBe(0);
});

it("报告按平台过滤后的总数和分页与真实接口一致", () => {
  for (const platform of ["telegram", "", "不存在的平台"]) {
    const expected = mockReportHistory.filter((report) => (report.platform || "") === platform);
    const result = mockHandlers["GET reports/history"]({ platform, limit: 1 }).data;
    expect(result.total).toBe(expected.length);
    expect(result.items.length).toBe(Math.min(expected.length, 1));
    expect(result.items.every((report) => (report.platform || "") === platform)).toBe(true);
  }
});
