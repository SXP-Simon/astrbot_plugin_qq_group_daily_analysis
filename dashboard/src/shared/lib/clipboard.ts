/**
 * 健壮的跨环境剪贴板复制工具 (兼容 iframe / WebView 与 Permissions Policy 限制)
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // 1. 优先尝试现代 navigator.clipboard API
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 捕获 Permissions Policy 或 iframe 限制错误，转入传统 execCommand 兜底
    }
  }

  // 2. 兜底机制：创建临时隐藏 textarea 并通过选区复制 (兼容受限 iframe)
  try {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.setAttribute("readonly", "");
    textArea.style.position = "fixed";
    textArea.style.top = "-9999px";
    textArea.style.left = "-9999px";
    textArea.style.opacity = "0";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    // 使用安全调用抹平 TypeScript ts(6387) 弃用警告
    const legacyDoc = document as unknown as {
      execCommand?: (commandId: string) => boolean;
    };
    const successful =
      typeof legacyDoc.execCommand === "function"
        ? legacyDoc.execCommand("copy")
        : false;

    document.body.removeChild(textArea);
    return successful;
  } catch {
    return false;
  }
}
