import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { FontManager } from "../../../../../features/manage-typst-fonts/ui/FontManager";
import { downloadTypstFonts, fetchTypstFonts } from "../../../../../entities/config/api/configApi";
import {
  deleteManagedFiles,
  fetchManagedContent,
  fetchManagedFiles,
  mutateManagedFile,
  startManagedUpload,
  uploadManagedChunk,
  type ManagedFile,
} from "../../../../../entities/plugin-data/api/managedFilesApi";
import { mockFontPresets } from "../../../../../mocks/data/fontPresets";

vi.mock("../../../../../entities/config/api/configApi", () => ({
  downloadTypstFonts: vi.fn(),
  fetchTypstFonts: vi.fn(),
}));
vi.mock("../../../../../entities/plugin-data/api/managedFilesApi", () => ({
  deleteManagedFiles: vi.fn(),
  fetchManagedContent: vi.fn(),
  fetchManagedFiles: vi.fn(),
  mutateManagedFile: vi.fn(),
  uploadManagedChunk: vi.fn(),
  startManagedUpload: vi.fn(),
}));
let files: ManagedFile[];
const metadata = (name: string): ManagedFile => ({
  name,
  size_bytes: 1024,
  modified_at: 1,
  media_type: "font/ttf",
  downloadable: true,
  editable: false,
  revision: `stat:${name}`,
});
const required = ["NotoSansSC.ttf", "Inter.ttf"];

beforeEach(() => {
  vi.resetAllMocks();
  files = [metadata("NotoSansSC.ttf")];
  const computedStyle = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation((element) => computedStyle(element));
  vi.mocked(fetchManagedFiles).mockImplementation(async () => ({
    items: [...files],
    total: files.length,
  }));
  vi.mocked(fetchTypstFonts).mockImplementation(async () => ({
    directory: "/plugin/typst/fonts",
    files: files.map((file) => file.name),
    missing: required.filter((name) => !files.some((file) => file.name === name)),
    ready: files.length === 2,
    groups: ["HatsuneMiku", "maria"].map((theme) => ({
      theme,
      required,
      missing: required.filter((name) => !files.some((file) => file.name === name)),
      ready: files.length === 2,
    })),
  }));
  vi.mocked(downloadTypstFonts).mockImplementation(async () => {
    files = required.map(metadata);
    return await fetchTypstFonts();
  });
  vi.mocked(deleteManagedFiles).mockImplementation(async (_partition, selected) => {
    files = files.filter((file) => !selected.some((item) => item.name === file.name));
    return { deleted: selected.map((file) => file.name), failed: [] };
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("字体管理展示缺失和共享依赖，不提供无意义的二进制查看导出", async () => {
  render(<FontManager onChanged={vi.fn()} />);
  expect(await screen.findByText("已安装 1 / 2 个字体，缺少 1 个")).toBeVisible();
  expect(screen.getAllByText("所有内置模板共享").length).toBe(2);
  expect(screen.queryByText("查看 / 导出")).not.toBeInTheDocument();
  expect(fetchManagedContent).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("补齐所选模板字体"));
  expect(await screen.findByText("已安装 2 / 2 个字体，已就绪")).toBeVisible();
  expect(downloadTypstFonts).toHaveBeenCalledWith(
    expect.any(String),
    "HatsuneMiku",
    "Inter.ttf",
    expect.any(String),
    "cdn",
  );
  expect(mutateManagedFile).not.toHaveBeenCalled();
}, 15000);

it("移除共享字体会确认影响，使用列表版本并刷新为缺失状态", async () => {
  render(
    <>
      <FontManager onChanged={vi.fn()} />
    </>,
  );
  await screen.findByText("已安装 1 / 2 个字体，缺少 1 个");
  const row = screen.getByText("NotoSansSC.ttf").closest("tr")!;
  fireEvent.click(within(row).getByText("移除"));
  expect(await screen.findByText(/将影响 2 个模板/)).toBeInTheDocument();
  const confirm = screen.getByRole("dialog", { name: "移除 NotoSansSC.ttf？" });
  fireEvent.click(within(confirm).getByRole("button", { name: "移除字体" }));
  await waitFor(() =>
    expect(deleteManagedFiles).toHaveBeenCalledWith("typst_fonts", [
      { name: "NotoSansSC.ttf", revision: "stat:NotoSansSC.ttf" },
    ]),
  );
  expect(await screen.findByText("已安装 0 / 2 个字体，缺少 2 个")).toBeVisible();
}, 15000);

it("按方案选定模板并给出同版来源，上传上游原文件时自动使用插件目标名", async () => {
  const name = "LXGWWenKai.ttf";
  const preset = mockFontPresets.find((item) => item.name === name)!;
  vi.mocked(fetchTypstFonts).mockImplementation(async () => ({
    directory: "/plugin/typst/fonts",
    files: files.map((file) => file.name),
    missing: files.some((file) => file.name === name) ? [] : [name],
    ready: files.some((file) => file.name === name),
    presets: [preset],
    groups: [
      {
        theme: "ATRI",
        required: [name],
        missing: files.some((file) => file.name === name) ? [] : [name],
        ready: files.some((file) => file.name === name),
      },
    ],
  }));
  vi.mocked(uploadManagedChunk).mockImplementation(async (file) => {
    files.push(metadata(name));
    return { received: file.size, total: file.size, complete: true };
  });
  const onChanged = vi.fn();
  render(
    <>
      <FontManager
        onChanged={onChanged}
        initialSelection={{
          theme: "ATRI",
          cdnBaseUrl: "https://cdn.jsdelivr.net",
          source: "github",
        }}
      />
    </>,
  );
  await screen.findByText("已安装 0 / 1 个字体，缺少 1 个");
  const row = screen.getByText(name).closest("tr")!;
  expect(screen.queryByRole("textbox", { name: "外部地址" })).not.toBeInTheDocument();
  const upstream = within(row).getByRole("button", { name: "查看上游" });
  upstream.focus();
  fireEvent.click(upstream);
  const address = await screen.findByRole("dialog", { name: "查看上游" });
  expect(within(address).getByRole("textbox", { name: "外部地址" })).toHaveValue(
    preset.upstream_url,
  );
  fireEvent.click(within(address).getByRole("button", { name: "关闭" }));
  await waitFor(() => expect(upstream).toHaveFocus());
  expect(within(row).getByRole("button", { name: "直接下载" })).toBeVisible();
  expect(within(row).queryByRole("link")).not.toBeInTheDocument();
  fireEvent.change(row.querySelector<HTMLInputElement>("input[type=file]")!, {
    target: { files: [new File([new Uint8Array(20)], "invalid.png")] },
  });
  expect(
    await screen.findByText("请选择非空的 TTF、OTF 或 TTC 字体文件，最大 32 MiB"),
  ).toBeVisible();
  const file = new File(
    [new Uint8Array([0, 1, 0, 0, ...Array(1024).fill(0)])],
    "LXGWWenKai-Regular.ttf",
    { type: "font/ttf" },
  );
  fireEvent.change(row.querySelector<HTMLInputElement>("input[type=file]")!, {
    target: { files: [file] },
  });
  await waitFor(() =>
    expect(startManagedUpload).toHaveBeenCalledWith(
      expect.objectContaining({ partition: "typst_fonts", name, operation: "create" }),
    ),
  );
  expect(await screen.findByText("已安装 1 / 1 个字体，已就绪")).toBeVisible();
  expect(
    screen.queryByText("请选择非空的 TTF、OTF 或 TTC 字体文件，最大 32 MiB"),
  ).not.toBeInTheDocument();
  expect(onChanged).toHaveBeenCalled();
  expect(screen.getByRole("combobox", { name: "字体下载 CDN" })).toBeDisabled();
}, 15000);

it("多页字体保留选择，移除失败保留确认目标与错误并支持重试", async () => {
  files = Array.from({ length: 22 }, (_, index) => metadata(`Custom-${index}.ttf`));
  render(<FontManager onChanged={vi.fn()} />);
  await screen.findByText("已安装 0 / 2 个字体，缺少 2 个");
  fireEvent.change(screen.getByRole("combobox", { name: "管理字体的模板" }), {
    target: { value: "__all__" },
  });
  fireEvent.click(screen.getByRole("checkbox", { name: "选择字体 Custom-0.ttf" }));
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(screen.queryByText("Custom-0.ttf")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: "选择字体 Custom-20.ttf" }));
  const trigger = screen.getByRole("button", { name: "移除所选（2）" });
  trigger.focus();
  fireEvent.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "移除所选的 2 个字体？" });
  expect(within(dialog).getByText("Custom-0.ttf")).toBeVisible();
  expect(within(dialog).getByText("Custom-20.ttf")).toBeVisible();
  vi.mocked(deleteManagedFiles).mockRejectedValueOnce(new Error("字体正在使用，请稍后重试"));
  fireEvent.click(within(dialog).getByRole("button", { name: "移除字体" }));
  expect(await within(dialog).findByText("字体正在使用，请稍后重试")).toBeVisible();
  await waitFor(() =>
    expect(within(dialog).getByRole("button", { name: "移除字体" })).toBeEnabled(),
  );
  fireEvent.click(within(dialog).getByRole("button", { name: "移除字体" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(deleteManagedFiles).toHaveBeenLastCalledWith("typst_fonts", [
    { name: "Custom-0.ttf", revision: "stat:Custom-0.ttf" },
    { name: "Custom-20.ttf", revision: "stat:Custom-20.ttf" },
  ]);
});

it("移除确认可以用 Escape 取消并返回原按钮，不发删除请求", async () => {
  render(<FontManager onChanged={vi.fn()} />);
  await screen.findByText("已安装 1 / 2 个字体，缺少 1 个");
  const row = screen.getByText("NotoSansSC.ttf").closest("tr")!;
  const trigger = within(row).getByRole("button", { name: "移除" });
  trigger.focus();
  fireEvent.click(trigger);
  expect(screen.getByRole("button", { name: "取消" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(trigger).toHaveFocus();
  expect(deleteManagedFiles).not.toHaveBeenCalled();
});
