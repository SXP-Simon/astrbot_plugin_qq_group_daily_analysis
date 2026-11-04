import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useFontUpload } from "../useFontUpload";
import { startManagedUpload, uploadManagedChunk } from "../../../../entities/plugin-data/api/managedFilesApi";
import { apiPost } from "../../../../shared/api/bridge";

vi.mock("../../../../entities/plugin-data/api/managedFilesApi", () => ({ startManagedUpload: vi.fn(), uploadManagedChunk: vi.fn() }));
vi.mock("../../../../shared/api/bridge", async original => ({ ...await original<typeof import("../../../../shared/api/bridge")>(), apiPost: vi.fn() }));
afterEach(() => vi.resetAllMocks());

it("网络失败仍在释放请求标识前清理服务器暂存", async () => {
  vi.mocked(uploadManagedChunk).mockRejectedValue(new Error("连接断开"));
  vi.mocked(apiPost).mockImplementation(async (_path, body) => ({ status: "ok", data: { ...(body as { download_id: string }), cancelled: true } }));
  const { result } = renderHook(() => useFontUpload(vi.fn()));
  await act(async () => { expect(await result.current.upload(new File([new Uint8Array(20)], "font.ttf"), "font.ttf")).toBe(false); });
  expect(apiPost).toHaveBeenCalledOnce();
  expect(result.current.progress).toMatchObject({ phase: "failed", error: "连接断开" });
});

it("按 1 MiB 二进制分块并使用服务器回执更新进度，不发送 Base64", async () => {
  const changed = vi.fn();
  vi.mocked(uploadManagedChunk).mockImplementation(async (file, _id, offset) => ({ received: offset + file.size, total: 2 * 1024 * 1024 + 20, complete: offset + file.size === 2 * 1024 * 1024 + 20 }));
  const { result } = renderHook(() => useFontUpload(changed));
  const file = new File([new Uint8Array(2 * 1024 * 1024 + 20)], "upstream.ttf");
  await act(async () => { expect(await result.current.upload(file, "preset.ttf")).toBe(true); });
  expect(uploadManagedChunk).toHaveBeenCalledTimes(3);
  expect(startManagedUpload).toHaveBeenCalledWith(expect.objectContaining({ name: "preset.ttf", total: file.size }));
  for (const [chunk, id] of vi.mocked(uploadManagedChunk).mock.calls) {
    expect(chunk.size).toBeLessThanOrEqual(1024 * 1024);
    expect(id).toMatch(/^[0-9a-f-]{36}$/);
  }
  expect(result.current.progress).toMatchObject({ phase: "saved", received: file.size });
  expect(result.current.running).toBe(false);
  expect(changed).toHaveBeenCalledOnce();
});

it("取消等待服务端确认，停止后续分块并保留真实已收进度", async () => {
  let rejectChunk!: (cause: Error) => void;
  vi.mocked(uploadManagedChunk).mockImplementation(async (file, _id, offset) => {
    if (offset === 0) return { received: file.size, total: 3 * 1024 * 1024, complete: false };
    return await new Promise((_, reject) => { rejectChunk = reject; });
  });
  vi.mocked(apiPost).mockImplementation(async (_path, body) => {
    const id = (body as { download_id: string }).download_id;
    rejectChunk(new Error("上传已取消"));
    return { status: "ok", data: { download_id: id, cancelled: true } };
  });
  const { result } = renderHook(() => useFontUpload(vi.fn()));
  let upload!: Promise<boolean>;
  act(() => { upload = result.current.upload(new File([new Uint8Array(3 * 1024 * 1024)], "font.ttf"), "font.ttf"); });
  await waitFor(() => expect(uploadManagedChunk).toHaveBeenCalledTimes(2));
  await act(async () => { await result.current.cancel(); await upload; });
  expect(apiPost).toHaveBeenCalledWith("plugin-data/files/upload/cancel", expect.objectContaining({ download_id: expect.any(String) }));
  expect(uploadManagedChunk).toHaveBeenCalledTimes(2);
  expect(result.current.progress).toMatchObject({ phase: "cancelled", received: 1024 * 1024 });
  expect(result.current.running).toBe(false);
});
