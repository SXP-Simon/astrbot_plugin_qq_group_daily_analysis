/**
 * 健壮的跨环境剪贴板复制工具 (兼容 iframe / WebView 与 Permissions Policy 限制)
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  const previousFocus =
    document.activeElement instanceof HTMLElement ? document.activeElement : null;
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
  const textArea = document.createElement("textarea");
  const scrollPositions: { element: HTMLElement; top: number; left: number }[] = [];
  for (
    let element: HTMLElement | null = previousFocus ?? document.documentElement;
    element;
    element = element.parentElement
  ) {
    scrollPositions.push({ element, top: element.scrollTop, left: element.scrollLeft });
  }
  try {
    textArea.value = text;
    textArea.setAttribute("readonly", "");
    textArea.style.position = "fixed";
    textArea.style.top = "-9999px";
    textArea.style.left = "-9999px";
    textArea.style.opacity = "0";
    // 弹窗会限制焦点范围，临时选区也必须放在当前弹窗内。
    const container =
      previousFocus?.closest('[role="dialog"], [role="alertdialog"]') ?? document.body;
    container.appendChild(textArea);
    textArea.focus({ preventScroll: true });
    textArea.select();

    // 使用安全调用抹平 TypeScript ts(6387) 弃用警告
    const legacyDoc = document as unknown as {
      execCommand?: (commandId: string) => boolean;
    };
    const successful =
      typeof legacyDoc.execCommand === "function" ? legacyDoc.execCommand("copy") : false;

    return successful;
  } catch {
    return false;
  } finally {
    textArea.remove();
    if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    // select() 在部分 WebView 中仍可能滚动祖先，复制完成后恢复原阅读位置。
    for (const { element, top, left } of scrollPositions) {
      element.scrollTop = top;
      element.scrollLeft = left;
    }
  }
}
