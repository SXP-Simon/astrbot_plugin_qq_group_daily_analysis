import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { fetchConfigFileContent, uploadConfigFile } from "../../../entities/config/api/configApi";
import { useConfigFiles, useConfigImage } from "./useConfigFiles";
import { toast } from "sonner";

vi.mock("../../../entities/config/api/configApi", () => ({
  fetchConfigFileContent: vi.fn(),
  uploadConfigFile: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), warning: vi.fn() } }));
beforeEach(() => vi.resetAllMocks());

it("上传失败保留原引用，可重试；单文件成功后替换引用并使用真实配置路径", async () => {
  const change = vi.fn();
  vi.mocked(uploadConfigFile)
    .mockResolvedValueOnce(null)
    .mockResolvedValueOnce({ path: "files/new.png" });
  const { result } = renderHook(() =>
    useConfigFiles("files/old.png", false, "comic.image", change),
  );
  const file = new File(["image"], "new.png");
  await act(() => result.current.upload([file]));
  expect(change).not.toHaveBeenCalled();
  expect(result.current.files).toEqual(["files/old.png"]);
  expect(result.current.error).toContain("上传失败");
  await act(() => result.current.upload([file]));
  expect(uploadConfigFile).toHaveBeenLastCalledWith(file, "comic.image");
  expect(change).toHaveBeenCalledWith("files/new.png");
  expect(result.current.error).toBe("");
  expect(result.current.busy).toBe(false);
});

it("多图部分成功保留已有路径，清除旧内嵌内容并报告失败数量", async () => {
  const change = vi.fn();
  const value = ["files/old.png", "data:image/png;base64,old"];
  vi.mocked(uploadConfigFile)
    .mockResolvedValueOnce({ path: "files/one.png" })
    .mockRejectedValueOnce(new Error("offline"));
  const { result } = renderHook(() => useConfigFiles(value, true, "comic.images", change));
  await act(() =>
    result.current.upload([new File(["one"], "one.png"), new File(["two"], "two.png")]),
  );
  expect(change).toHaveBeenCalledWith(["files/old.png", "files/one.png"]);
  expect(toast.warning).toHaveBeenCalledWith(expect.stringContaining("另有 1 个"));
});

it("条目切换使旧上传失效，旧回执不能覆盖新条目或释放新请求状态", async () => {
  let finishOld!: (value: { path: string }) => void;
  let finishNew!: (value: { path: string }) => void;
  vi.mocked(uploadConfigFile)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishOld = resolve;
        }),
    )
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishNew = resolve;
        }),
    );
  const oldChange = vi.fn();
  const newChange = vi.fn();
  const empty: string[] = [];
  const { result, rerender } = renderHook(
    ({ scope, change }) => useConfigFiles(empty, true, "comic.images", change, scope),
    { initialProps: { scope: { name: "first" }, change: oldChange } },
  );
  let first!: Promise<void>;
  act(() => {
    first = result.current.upload([new File(["first"], "first.png")]);
  });
  rerender({ scope: { name: "second" }, change: newChange });
  let second!: Promise<void>;
  act(() => {
    second = result.current.upload([new File(["second"], "second.png")]);
  });
  await act(async () => {
    finishOld({ path: "files/first.png" });
    await first;
  });
  expect(oldChange).not.toHaveBeenCalled();
  expect(newChange).not.toHaveBeenCalled();
  expect(result.current.busy).toBe(true);
  await act(async () => {
    finishNew({ path: "files/second.png" });
    await second;
  });
  expect(newChange).toHaveBeenCalledWith(["files/second.png"]);
  expect(result.current.busy).toBe(false);
});

it("重复点击只上传一次，卸载后不再写入配置", async () => {
  let finish!: (value: { path: string }) => void;
  vi.mocked(uploadConfigFile).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const change = vi.fn();
  const { result, unmount } = renderHook(() => useConfigFiles("", false, "image", change));
  const files = [new File(["image"], "file.png")];
  let pending!: Promise<void>;
  act(() => {
    pending = result.current.upload(files);
    void result.current.upload(files);
  });
  expect(uploadConfigFile).toHaveBeenCalledOnce();
  unmount();
  await act(async () => {
    finish({ path: "files/result.png" });
    await pending;
  });
  expect(change).not.toHaveBeenCalled();
});

it("参考图片按路径隔离读取，外链不请求插件内容 API", async () => {
  let finish!: (value: { data_url: string }) => void;
  vi.mocked(fetchConfigFileContent)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    )
    .mockResolvedValueOnce({ data_url: "second-image" });
  const { result, rerender } = renderHook(({ path }) => useConfigImage(path), {
    initialProps: { path: "files/first.png" },
  });
  rerender({ path: "files/second.png" });
  expect(result.current.src).toBeNull();
  await waitFor(() => expect(result.current.src).toBe("second-image"));
  await act(async () => finish({ data_url: "first-image" }));
  expect(result.current.src).toBe("second-image");
  rerender({ path: "https://image.example/test.webp" });
  expect(result.current.src).toBe("https://image.example/test.webp");
  expect(fetchConfigFileContent).toHaveBeenCalledTimes(2);
});
