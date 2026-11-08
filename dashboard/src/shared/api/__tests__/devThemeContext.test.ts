import { beforeEach, expect, it, vi } from "vitest";
import { devFetchContext } from "../devBridge";
import { devSubscribeContext, getDevThemeContext, setDevThemeContext } from "../devThemeContext";

beforeEach(() => localStorage.clear());
it("模拟配色经过上下文通知与初始化读取，恢复默认不保留旧颜色", async () => {
  const receive = vi.fn();
  const off = devSubscribeContext(receive);
  const context = { isDark: true, themeColors: { primary: "#123456", secondary: "#abcdef" } };
  setDevThemeContext(context);
  expect(receive).toHaveBeenLastCalledWith(context);
  expect(await devFetchContext()).toMatchObject(context);
  expect(getDevThemeContext()).toEqual(context);
  setDevThemeContext({ isDark: false });
  expect(getDevThemeContext().themeColors).toBeUndefined();
  off();
  receive.mockClear();
  setDevThemeContext(context);
  expect(receive).not.toHaveBeenCalled();
});
it("损坏的缓存与受限存储不阻断预览通知", () => {
  localStorage.setItem("astrbot_dev_theme_context", "bad json");
  expect(getDevThemeContext()).toEqual({});
  const receive = vi.fn();
  const off = devSubscribeContext(receive);
  const storage = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  try {
    setDevThemeContext({ isDark: true });
    expect(receive).toHaveBeenLastCalledWith({ isDark: true });
  } finally {
    storage.mockRestore();
    off();
  }
});
