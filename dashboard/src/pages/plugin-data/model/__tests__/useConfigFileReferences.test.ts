import { afterEach, expect, it, vi } from "vitest";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { fetchPluginConfig } from "../../../../entities/config/api/configApi";
import { useConfigFileReferences } from "../../../../features/manage-stored-files/model/useConfigFileReferences";

vi.mock("../../../../entities/config/api/configApi", () => ({ fetchPluginConfig: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it("按需检查嵌套配置中的相对与绝对文件路径，忽略 CDN 同名图片", async () => {
  vi.mocked(fetchPluginConfig).mockResolvedValue({
    schema: {},
    config: {
      comic: {
        characters: [
          {
            images: [
              "files/characters/miku.png",
              "C:\\data\\plugin\\files\\characters\\miku.png",
              "https://example.com/files/characters/miku.png",
            ],
          },
        ],
      },
    },
  });
  const { result, rerender } = renderHook(({ enabled }) => useConfigFileReferences(enabled), {
    initialProps: { enabled: false },
  });
  expect(fetchPluginConfig).not.toHaveBeenCalled();
  rerender({ enabled: true });
  await waitFor(() => expect(result.current.references.get("characters/miku.png")).toHaveLength(2));
  expect(result.current.references.get("characters/miku.png")).toEqual(
    expect.arrayContaining(["comic.characters[0].images[0]", "comic.characters[0].images[1]"]),
  );
});
