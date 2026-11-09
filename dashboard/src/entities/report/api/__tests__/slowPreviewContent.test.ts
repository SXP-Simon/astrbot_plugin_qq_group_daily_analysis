import { afterEach, expect, it, vi } from "vitest";
import { fetchReportContent, fetchTemplatePreview } from "@/entities/report/api/reportApi";
import { fetchManagedContent } from "@/entities/plugin-data/api/managedFilesApi";

const image = {
  filename: "large.png",
  size_bytes: 3000000,
  modified_at: 1,
  data_url: "data:image/png;base64,YWJj",
};
const html = {
  filename: "large.html",
  size_bytes: 3000000,
  modified_at: 1,
  html_content: "<h1>示例</h1>",
};
const managed = {
  name: "large.png",
  revision: "v1",
  media_type: "image/png",
  text: null,
  content_base64: "YWJj",
};

afterEach(() => {
  delete window.AstrBotPluginPage;
  vi.useRealTimers();
});

it.each([
  {
    name: "报告图片",
    read: () => fetchReportContent(image.filename),
    data: image,
    expected: image,
  },
  { name: "HTML 报告", read: () => fetchReportContent(html.filename), data: html, expected: html },
  {
    name: "文件管理",
    read: () => fetchManagedContent("reports", managed.name),
    data: managed,
    expected: managed,
  },
  {
    name: "自定义模板预览",
    read: () => fetchTemplatePreview("custom"),
    data: { data_url: image.data_url },
    expected: image.data_url,
  },
])(
  "$name 使用真实 Bridge 等待迟到响应，三十秒后不主动结束请求",
  async ({ read, data, expected }) => {
    vi.useFakeTimers();
    let complete!: (value: { data: unknown }) => void;
    const get = vi.fn(
      () =>
        new Promise<{ data: unknown }>((resolve) => {
          complete = resolve;
        }),
    );
    window.AstrBotPluginPage = { apiGet: get } as unknown as NonNullable<
      Window["AstrBotPluginPage"]
    >;
    let settled = false;
    const request = read().finally(() => {
      settled = true;
    });
    await vi.advanceTimersByTimeAsync(45000);
    expect(settled).toBe(false);
    expect(get).toHaveBeenCalledTimes(1);
    complete({ data });
    await expect(request).resolves.toEqual(expected);
    expect(vi.getTimerCount()).toBe(0);
  },
);
