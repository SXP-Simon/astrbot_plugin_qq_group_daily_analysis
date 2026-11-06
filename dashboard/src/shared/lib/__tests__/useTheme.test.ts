import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AstrBotContext } from "../../api/bridge";

const fetchContext = vi.hoisted(() => vi.fn());
vi.mock("../../api/bridge", () => ({ fetchContext }));

describe("宿主主题同步", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    document.documentElement.className = "";
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
    await import("../useTheme");
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
    await import("../useTheme");
    notify?.({ isDark: true });
    resolve({ isDark: false });
    await Promise.resolve();
    expect(document.documentElement).toHaveClass("dark");
  });

  it("宿主初始化失败时继续使用缓存主题", async () => {
    localStorage.setItem("astrbot_plugin_theme_is_dark", "true");
    fetchContext.mockRejectedValue(new Error("宿主暂未就绪"));
    await import("../useTheme");
    await Promise.resolve();
    expect(document.documentElement).toHaveClass("dark");
  });
});
