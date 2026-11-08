import { afterEach, expect, it, vi } from "vitest";
import { devApiGet, getDevBridgeMode, setDevBridgeMode } from "../devBridge";

afterEach(() => vi.unstubAllGlobals());

it("切换模式同时更新显式 URL 和缓存，再刷新；保留其他参数与锚点", () => {
  const location = {
    href: "http://localhost/?devMode=mock&theme=dark#page-content",
    search: "?devMode=mock&theme=dark",
    reload: vi.fn(),
  };
  const localStorage = { getItem: vi.fn(() => "mock"), setItem: vi.fn() };
  const replaceState = vi.fn((_state, _unused, value: URL) => {
    location.href = value.href;
    location.search = value.search;
  });
  vi.stubGlobal("window", { location, localStorage, history: { replaceState } });
  setDevBridgeMode("proxy");
  expect(getDevBridgeMode()).toBe("proxy");
  expect(localStorage.setItem).toHaveBeenCalledWith("astrbot_dev_bridge_mode", "proxy");
  expect(location.href).toBe("http://localhost/?devMode=proxy&theme=dark#page-content");
  expect(location.reload).toHaveBeenCalledOnce();
});

it("无显式参数时校验缓存模式，未知旧值不会进入虚假的代理模式", () => {
  vi.stubGlobal("window", {
    location: { search: "" },
    localStorage: { getItem: () => "unexpected" },
  });
  expect(getDevBridgeMode()).toBe("mock");
});

it.each([
  ["1000", 1000],
  ["invalid", 50],
  ["999999", 5000],
])("Mock 读取延迟可调且有上限：%s", async (input, delay) => {
  vi.useFakeTimers();
  vi.stubGlobal("window", { location: { search: `?devMode=mock&mockDelay=${input}` } });
  try {
    const finished = vi.fn();
    const request = devApiGet("metrics/summary").then(finished);
    await vi.advanceTimersByTimeAsync(Number(delay) - 1);
    expect(finished).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    await request;
    expect(finished).toHaveBeenCalledOnce();
  } finally {
    vi.useRealTimers();
  }
});
