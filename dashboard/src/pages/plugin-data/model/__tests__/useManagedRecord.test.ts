import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { fetchManagedRecord } from "../../../../entities/plugin-data/api/managedRecordsApi";
import { useManagedRecord } from "../useManagedRecord";

vi.mock("../../../../entities/plugin-data/api/managedRecordsApi", () => ({
  fetchManagedRecord: vi.fn(),
  mutateManagedRecord: vi.fn(),
  recordLocatorSchema: {},
}));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("头像下载为图片并清理缓存键中的路径字符，不导出 JSON 包装", async () => {
  const locator = { kind: "avatar", key: "onebot:123456" };
  const uri = "data:image/png;base64,iVBORw0KGgo=";
  vi.mocked(fetchManagedRecord).mockResolvedValue({
    locator,
    revision: "v1",
    data: { data_uri: uri },
  });
  let downloaded = { href: "", name: "" };
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    downloaded = { href: this.href, name: this.download };
  });
  const { result } = renderHook(() => useManagedRecord(locator, vi.fn(), vi.fn()));
  await waitFor(() => expect(result.current.record).not.toBeNull());
  act(() => result.current.download());
  expect(downloaded).toEqual({ href: uri, name: "avatar-onebot_123456.png" });
});
