import { Toaster as Sonner } from "sonner";
import {
  IconCheck,
  IconInfoCircle,
  IconAlertTriangle,
  IconAlertCircle,
  IconX,
  IconLoader2,
} from "@tabler/icons-react";
import { useTheme } from "../lib/useTheme";

export function Toaster() {
  const { isDark } = useTheme();
  return (
    <Sonner
      theme={isDark ? "dark" : "light"}
      position="top-center"
      customAriaLabel="操作通知（Alt+T）"
      closeButton
      visibleToasts={3}
      duration={5000}
      icons={{
        success: <IconCheck size={18} aria-hidden="true" />,
        info: <IconInfoCircle size={18} aria-hidden="true" />,
        warning: <IconAlertTriangle size={18} aria-hidden="true" />,
        error: <IconAlertCircle size={18} className="text-destructive" aria-hidden="true" />,
        loading: <IconLoader2 size={18} className="animate-spin" aria-hidden="true" />,
        close: <IconX size={14} aria-hidden="true" />,
      }}
      toastOptions={{
        closeButtonAriaLabel: "关闭提示",
        classNames: {
          toast: "focus-visible:outline-2 focus-visible:outline-ring",
          closeButton: "focus-visible:outline-2 focus-visible:outline-ring",
          description: "text-muted-foreground",
        },
        style: {
          background: "var(--card)",
          color: "var(--foreground)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          boxShadow: "none",
          fontFamily: "var(--font-sans)",
          fontSize: 14,
          fontWeight: 400,
        },
      }}
    />
  );
}
