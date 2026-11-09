import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { AstrBotContext } from "@/shared/api/bridge";
import { getHostThemeStyles } from "@/shared/lib/themeColors";

const fetchContext = vi.hoisted(() => vi.fn());
vi.mock("@/shared/api/bridge", () => ({
  fetchContext,
  subscribeContext: (callback: (context: AstrBotContext) => void) =>
    window.AstrBotPluginPage?.onContext?.(callback) ?? (() => {}),
}));

describe("宿主主题同步", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    document.documentElement.className = "";
    document.documentElement.style.cssText = "";
    delete document.documentElement.dataset.theme;
    delete window.AstrBotPluginPage;
  });

  it("初始化和后续通知都同步到根节点，弹层也能继承主题", async () => {
    let notify: ((context: AstrBotContext) => void) | undefined;
    fetchContext.mockResolvedValue({ isDark: true });
    window.AstrBotPluginPage = {
      ready: async () => ({ isDark: true }),
      onContext: (callback) => {
        notify = callback;
        return () => {};
      },
      apiGet: async () => null,
      apiPost: async () => null,
      subscribeSSE: async () => "test",
      unsubscribeSSE: () => {},
    };
    await import("@/shared/lib/useTheme");
    expect(document.documentElement).toHaveClass("dark");
    notify?.({ isDark: false });
    expect(document.documentElement).not.toHaveClass("dark");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("astrbot_plugin_theme_is_dark")).toBe("false");
  });

  it("较迟返回的初始化结果不能覆盖新的宿主通知", async () => {
    let resolve!: (context: AstrBotContext) => void;
    let notify: ((context: AstrBotContext) => void) | undefined;
    fetchContext.mockReturnValue(
      new Promise<AstrBotContext>((done) => {
        resolve = done;
      }),
    );
    window.AstrBotPluginPage = {
      ready: async () => ({}),
      onContext: (callback) => {
        notify = callback;
        return () => {};
      },
      apiGet: async () => null,
      apiPost: async () => null,
      subscribeSSE: async () => "test",
      unsubscribeSSE: () => {},
    };
    await import("@/shared/lib/useTheme");
    notify?.({ isDark: true });
    resolve({ isDark: false });
    await Promise.resolve();
    expect(document.documentElement).toHaveClass("dark");
  });

  it("宿主初始化失败时继续使用缓存主题", async () => {
    localStorage.setItem("astrbot_plugin_theme_is_dark", "true");
    fetchContext.mockRejectedValue(new Error("宿主暂未就绪"));
    await import("@/shared/lib/useTheme");
    await Promise.resolve();
    expect(document.documentElement).toHaveClass("dark");
  });
});

it("只更新颜色也会通知图表订阅，缺失颜色恢复默认且不修改状态语义色", async () => {
  vi.resetModules();
  document.documentElement.style.cssText = "--warning: #aa8800; --destructive: #bb1111;";
  let notify!: (context: AstrBotContext) => void;
  fetchContext.mockResolvedValue({ isDark: false });
  window.AstrBotPluginPage = {
    ready: async () => ({}),
    onContext: (callback) => {
      notify = callback;
      return () => {};
    },
    apiGet: async () => null,
    apiPost: async () => null,
    subscribeSSE: async () => "test",
    unsubscribeSSE: () => {},
  };
  const { useTheme } = await import("@/shared/lib/useTheme");
  const { result, unmount } = renderHook(() => useTheme());
  await waitFor(() => expect(result.current.isDark).toBe(false));
  const before = result.current.revision;
  act(() => notify({ isDark: false, themeColors: { primary: "#123456", secondary: "#abcdef" } }));
  expect(result.current.revision).toBeGreaterThan(before);
  expect(result.current.isDark).toBe(false);
  expect(document.documentElement.style.getPropertyValue("--primary")).toBe(
    getHostThemeStyles({ primary: "#123456" }, false)["--primary"],
  );
  expect(document.documentElement.style.getPropertyValue("--primary-foreground")).toBe("#ffffff");
  const stable = result.current.revision;
  act(() => notify({ isDark: false, themeColors: { primary: "#123456", secondary: "#abcdef" } }));
  expect(result.current.revision).toBe(stable);
  act(() => notify({ isDark: true }));
  expect(document.documentElement.style.getPropertyValue("--primary")).toBe("");
  expect(document.documentElement.style.getPropertyValue("--secondary")).toBe("");
  expect(document.documentElement.style.getPropertyValue("--warning")).toBe("#aa8800");
  expect(document.documentElement.style.getPropertyValue("--destructive")).toBe("#bb1111");
  unmount();
});

it("只含配色的较新通知也优先于迟到的初始化结果", async () => {
  vi.resetModules();
  document.documentElement.style.cssText = "";
  let notify!: (context: AstrBotContext) => void;
  let resolve!: (context: AstrBotContext) => void;
  fetchContext.mockReturnValue(
    new Promise<AstrBotContext>((done) => {
      resolve = done;
    }),
  );
  window.AstrBotPluginPage = {
    ready: async () => ({}),
    onContext: (callback) => {
      notify = callback;
      return () => {};
    },
    apiGet: async () => null,
    apiPost: async () => null,
    subscribeSSE: async () => "test",
    unsubscribeSSE: () => {},
  };
  await import("@/shared/lib/useTheme");
  notify({ themeColors: { primary: "#123456" } });
  resolve({ isDark: true, themeColors: { primary: "#ffffff" } });
  await Promise.resolve();
  expect(document.documentElement.style.getPropertyValue("--primary")).toBe(
    getHostThemeStyles({ primary: "#123456" }, false)["--primary"],
  );
});
