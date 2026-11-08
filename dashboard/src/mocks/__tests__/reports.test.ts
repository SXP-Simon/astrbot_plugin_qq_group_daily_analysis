import { afterEach, expect, it } from "vitest";
import { mockHandlers } from "../handlers";
import { mockReportHistory } from "../data/reports";
import { mockTraces } from "../data/traces";
import { mockReportImage, mockReportImageBytes, mockReportHtml } from "../data/reportContent";
import { extractData } from "../../shared/api/bridge";
import type { ReportItem } from "../../entities/report/model/types";

const savedReports = structuredClone(mockReportHistory);
const savedArtifacts = mockTraces.map((trace) => structuredClone(trace.report_files));
afterEach(() => {
  mockReportHistory.splice(0, mockReportHistory.length, ...structuredClone(savedReports));
  mockTraces.forEach((trace, index) => {
    trace.report_files = structuredClone(savedArtifacts[index]);
  });
});

it("报告清单与任务中的图片和网页产物保持相同文件名、群聊、平台和任务关联", () => {
  for (const trace of mockTraces) {
    for (const file of trace.report_files ?? []) {
      if (!file.filename || !/\.(png|jpe?g|webp|html?)$/i.test(file.filename)) continue;
      const item = mockReportHistory.find((report) => report.filename === file.filename);
      expect(item).toMatchObject({
        trace_id: trace.trace_id,
        group_id: trace.group_id,
        platform: trace.platform,
      });
      expect(
        extractData<ReportItem>(mockHandlers["GET reports/content"]({ filename: file.filename })),
      ).toMatchObject({
        filename: file.filename,
        trace_id: trace.trace_id,
        group_id: trace.group_id,
      });
    }
  }
  expect(mockHandlers["GET reports/content"]({ filename: "不存在.png" }).status).toBe("error");
});

it("报告接口按实际服务的群号精确筛选、文件关键字、降序与分页返回总数", () => {
  const list = mockHandlers["GET reports/history"]({ limit: 2 }).data;
  const next = mockHandlers["GET reports/history"]({ limit: 2, offset: 2 }).data;
  expect(list.items).toHaveLength(2);
  expect(next.items).toHaveLength(2);
  expect(list.total).toBe(mockReportHistory.length);
  expect(list.items[1].modified_at).toBeGreaterThanOrEqual(next.items[0].modified_at);
  expect(new Set([...list.items, ...next.items].map((item) => item.filename)).size).toBe(4);
  const filtered = mockHandlers["GET reports/history"]({
    group_id: "123456789",
    search: "DAILY",
    limit: 100,
  }).data;
  expect(filtered.total).toBeGreaterThan(0);
  expect(
    filtered.items.every(
      (item) => item.group_id === "123456789" && item.filename.includes("daily"),
    ),
  ).toBe(true);
  expect(mockHandlers["GET reports/history"]({ group_id: "123" }).data.total).toBe(0);
  expect(mockHandlers["GET reports/history"]({ offset: 1000 }).data).toEqual({
    items: [],
    total: mockReportHistory.length,
  });
});

it.each(["html", "image"])(
  "重绘 %s 后可从列表和任务产物找到新文件，并读取同一份示例内容",
  (format) => {
    const source = mockReportHistory.find((item) => item.trace_id)!;
    const template = mockHandlers["GET reports/templates"]({ render_format: format }).data[0];
    const response = extractData<{ filename: string; is_html: boolean }>(
      mockHandlers["POST reports/rerender"]({
        group_id: source.group_id,
        trace_id: source.trace_id,
        platform_id: source.platform,
        render_format: format,
        template_name: template.id,
      }),
    )!;
    expect(response.is_html).toBe(format === "html");
    const listing = mockHandlers["GET reports/history"]({ search: response.filename }).data;
    expect(listing.total).toBe(1);
    expect(listing.items[0]).toMatchObject({
      trace_id: source.trace_id,
      group_id: source.group_id,
      platform: source.platform,
      is_comic: false,
    });
    const content = extractData<ReportItem>(
      mockHandlers["GET reports/content"]({ filename: response.filename }),
    )!;
    if (format === "html") {
      expect(content.html_content).toBe(mockReportHtml);
      expect(content.html_content).toContain("示例数据");
      expect(content.data_url).toBeUndefined();
      expect(content.size_bytes).toBe(new TextEncoder().encode(mockReportHtml).byteLength);
    } else {
      expect(content.data_url).toBe(mockReportImage);
      expect(content.data_url).toMatch(/^data:image\/png;base64,iVBOR/);
      expect(content.size_bytes).toBe(mockReportImageBytes);
      expect(content.html_content).toBeUndefined();
    }
    expect(
      mockTraces.find((trace) => trace.trace_id === source.trace_id)?.report_files,
    ).toContainEqual(
      expect.objectContaining({ filename: response.filename, size_bytes: content.size_bytes }),
    );
  },
);

it("不存在的快照、错误平台及不支持的模板或格式不能伪造重绘成功", () => {
  const source = mockReportHistory.find((item) => item.trace_id)!;
  const template = mockHandlers["GET reports/templates"]({ render_format: "image" }).data[0];
  const payload = {
    group_id: source.group_id,
    trace_id: source.trace_id,
    platform_id: source.platform,
    render_format: "image",
    template_name: template.id,
  };
  for (const override of [
    { group_id: "missing" },
    { trace_id: "missing" },
    { platform_id: "missing" },
    { render_format: "pdf" },
    { template_name: "missing" },
  ]) {
    expect(mockHandlers["POST reports/rerender"]({ ...payload, ...override }).status).toBe("error");
  }
  expect(mockReportHistory).toEqual(savedReports);
});
it("日期与升序先应用于全局数据，再分页；同一时间以文件名定序", () => {
  mockReportHistory.splice(
    0,
    mockReportHistory.length,
    ...Array.from({ length: 6 }, (_, i) => ({
      ...savedReports[0],
      filename: `global-${i}.png`,
      modified_at: Math.floor(i / 2),
    })),
  );
  const first = mockHandlers["GET reports/history"]({
    limit: 2,
    sort_order: "asc",
    start_time: 1,
    end_time: 2,
  }).data;
  const second = mockHandlers["GET reports/history"]({
    limit: 2,
    offset: 2,
    sort_order: "asc",
    start_time: 1,
    end_time: 2,
  }).data;
  expect(first.total).toBe(4);
  expect(second.total).toBe(4);
  expect([...first.items, ...second.items].map((item) => item.filename)).toEqual([
    "global-2.png",
    "global-3.png",
    "global-4.png",
    "global-5.png",
  ]);
});

it("报告列表已带示例绝对路径，无需读取图片内容，路径与内容接口一致", () => {
  const list = mockHandlers["GET reports/history"]({ limit: 2 }).data;
  for (const item of list.items) {
    expect(item.absolute_path).toBe(`/demo/plugin_data/reports/${item.filename}`);
    expect(item.data_url).toBeUndefined();
    expect(item.html_content).toBeUndefined();
    const content = extractData<ReportItem>(
      mockHandlers["GET reports/content"]({ filename: item.filename }),
    );
    expect(content?.absolute_path).toBe(item.absolute_path);
  }
});
