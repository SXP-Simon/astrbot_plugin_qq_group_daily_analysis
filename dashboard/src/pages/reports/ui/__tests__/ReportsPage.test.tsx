import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ReportsPage } from "../ReportsPage";
import { useReportsViewModel } from "../../model/useReportsViewModel";
import {
  fetchReportHistory,
  fetchReportContent,
  fetchReportTemplates,
  rerenderReport,
} from "../../../../entities/report/api/reportApi";
import { fetchDistinctGroups } from "../../../../entities/group/api/groupApi";
import type { ReportItem } from "../../../../entities/report/model/types";

vi.mock("../../../../entities/report/api/reportApi", () => ({
  fetchReportHistory: vi.fn(),
  fetchReportContent: vi.fn(),
  fetchReportTemplates: vi.fn(),
  rerenderReport: vi.fn(),
}));
vi.mock("../../../../entities/group/api/groupApi", () => ({ fetchDistinctGroups: vi.fn() }));
const image: ReportItem = {
  filename: "example-a.png",
  modified_at: 200,
  size_bytes: 100,
  group_id: "123",
  group_name: "示例群聊",
  platform: "telegram",
  trace_id: "trace-example",
};
const html: ReportItem = { ...image, filename: "example-b.html", is_html: true, modified_at: 100 };
const comic: ReportItem = {
  ...image,
  filename: "comic_example.png",
  is_comic: true,
  trace_id: null,
};
const onViewTrace = vi.fn();
function Page() {
  return <ReportsPage viewModel={useReportsViewModel()} onViewTrace={onViewTrace} />;
}
beforeEach(() => {
  vi.mocked(fetchReportHistory).mockResolvedValue({ items: [image, html, comic], total: 25 });
  vi.mocked(fetchDistinctGroups).mockResolvedValue([]);
  vi.mocked(fetchReportContent).mockImplementation(async (filename) =>
    filename === html.filename
      ? { ...html, html_content: "<h1>示例报告</h1>" }
      : { ...image, data_url: "data:image/png;base64,example" },
  );
  vi.mocked(fetchReportTemplates).mockResolvedValue([
    { id: "HatsuneMiku", label: "初音", has_image: true, has_html: true },
  ]);
  vi.mocked(rerenderReport).mockResolvedValue({
    success: true,
    filename: "new.png",
    report_path: "reports/new.png",
    is_html: false,
  });
});
afterEach(() => vi.resetAllMocks());

it("显示报告身份与明确操作，漫画不提供换模板，图片与HTML预览和关联任务保留", async () => {
  render(<Page />);
  const list = await screen.findByRole("list", { name: "报告文件" });
  const rows = within(list).getAllByRole("listitem");
  expect(rows[0]).toHaveTextContent("example-a.png");
  expect(rows[0]).toHaveTextContent("telegram · 123");
  expect(
    within(rows.find((row) => row.textContent?.includes(comic.filename))!).queryByRole("button", {
      name: "换模板",
    }),
  ).not.toBeInTheDocument();
  fireEvent.click(within(rows[0]).getByRole("button", { name: /查看任务/ }));
  expect(onViewTrace).toHaveBeenCalledWith("trace-example");
  const preview = within(rows[0]).getByRole("button", { name: "预览" });
  preview.focus();
  fireEvent.click(preview);
  const dialog = screen.getByRole("dialog", { name: "报告预览" });
  expect(await within(dialog).findByRole("img", { name: image.filename })).toBeVisible();
  fireEvent.click(within(dialog).getByRole("button", { name: "关闭预览" }));
  await waitFor(() => expect(preview).toHaveFocus());
  const htmlRow = rows.find((row) => row.textContent?.includes(html.filename))!;
  fireEvent.click(within(htmlRow).getByRole("button", { name: "预览" }));
  expect(await screen.findByTitle(html.filename)).toHaveAttribute("srcdoc", "<h1>示例报告</h1>");
});

it("本页日期筛空后仍能翻页，日期错误不应用，排序和重置可操作", async () => {
  render(<Page />);
  await screen.findByRole("list", { name: "报告文件" });
  fireEvent.change(screen.getByLabelText("本页时间排序"), { target: { value: "asc" } });
  expect(
    within(screen.getByRole("list", { name: "报告文件" })).getAllByRole("listitem")[0],
  ).toHaveTextContent(html.filename);
  fireEvent.change(screen.getByLabelText("本页开始日期"), { target: { value: "2026-11-07" } });
  fireEvent.change(screen.getByLabelText("本页结束日期"), { target: { value: "2026-11-01" } });
  expect(screen.getByRole("alert")).toHaveTextContent("结束日期不能早于开始日期");
  fireEvent.change(screen.getByLabelText("本页结束日期"), { target: { value: "2026-11-08" } });
  expect(screen.getByText("本页没有这个日期范围内的报告，可清空日期或继续翻页。")).toBeVisible();
  expect(screen.getByRole("navigation", { name: "分页" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  await waitFor(() =>
    expect(fetchReportHistory).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 20 })),
  );
  fireEvent.click(screen.getByRole("button", { name: "清空筛选" }));
  expect(screen.getByLabelText("本页开始日期")).toHaveValue("");
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "第 1 页" })).toHaveAttribute("aria-current", "page"),
  );
  expect(screen.getByRole("list", { name: "报告文件" })).toBeVisible();
});

it("换模板仍使用保存的报告身份，成功后刷新第一页；列表失败可重试", async () => {
  vi.mocked(fetchReportHistory).mockRejectedValueOnce(new Error("宿主暂不可用"));
  render(<Page />);
  expect(await screen.findByRole("alert")).toHaveTextContent("宿主暂不可用");
  expect(screen.queryByText(/暂无符合条件/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "刷新" }));
  const list = await screen.findByRole("list", { name: "报告文件" });
  fireEvent.click(within(list).getAllByRole("button", { name: "换模板" })[0]);
  const dialog = screen.getByRole("dialog");
  await waitFor(() =>
    expect(within(dialog).getByRole("button", { name: "生成新报告" })).toBeEnabled(),
  );
  fireEvent.click(within(dialog).getByRole("button", { name: "生成新报告" }));
  await waitFor(() =>
    expect(rerenderReport).toHaveBeenCalledWith(
      expect.objectContaining({
        group_id: "123",
        platform_id: "telegram",
        trace_id: "trace-example",
      }),
    ),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(fetchReportHistory).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 0 }));
});
