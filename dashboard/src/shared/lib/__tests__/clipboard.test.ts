import { afterEach, expect, it, vi } from "vitest";
import { copyToClipboard } from "../clipboard";

afterEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("优先使用现代剪贴板，不创建临时控件", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("isSecureContext", true);
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  expect(await copyToClipboard("示例地址")).toBe(true);
  expect(writeText).toHaveBeenCalledWith("示例地址");
  expect(document.querySelector("textarea")).toBeNull();
});

it("权限被拒绝时在当前弹窗内创建选区，完成后清理并恢复焦点", async () => {
  vi.stubGlobal("isSecureContext", true);
  vi.stubGlobal("navigator", {
    clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
  });
  const dialog = document.createElement("div");
  dialog.setAttribute("role", "dialog");
  const button = document.createElement("button");
  dialog.append(button);
  document.body.append(dialog);
  button.focus();
  const execCommand = vi.fn(() => {
    const area = dialog.querySelector("textarea");
    expect(area).toBe(document.activeElement);
    expect(area?.value).toBe("https://example.test/font");
    expect(area?.selectionEnd).toBe(area?.value.length);
    return true;
  });
  Object.defineProperty(document, "execCommand", { configurable: true, value: execCommand });
  try {
    expect(await copyToClipboard("https://example.test/font")).toBe(true);
    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(document.querySelector("textarea")).toBeNull();
    expect(document.activeElement).toBe(button);
  } finally {
    Reflect.deleteProperty(document, "execCommand");
  }
});

it("旧复制接口报错仍清理临时控件，不留下隐藏内容", async () => {
  vi.stubGlobal("navigator", {});
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    value: () => {
      throw new Error("blocked");
    },
  });
  try {
    expect(await copyToClipboard("示例内容")).toBe(false);
    expect(document.querySelector("textarea")).toBeNull();
  } finally {
    Reflect.deleteProperty(document, "execCommand");
  }
});
