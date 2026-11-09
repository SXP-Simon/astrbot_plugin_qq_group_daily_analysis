import { IconAdjustments, IconBolt, IconSunMoon } from "@tabler/icons-react";
import { useState } from "react";
import { toast } from "sonner";
import { getDevBridgeMode, setDevBridgeMode } from "@/shared/api/devBridge";
import { mockSSEService } from "@/mocks/sseMock";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";
import { NativeSelect } from "@/shared/ui/native-select";
import { Switch } from "@/shared/ui/switch";
import { getDevThemeContext, setDevThemeContext } from "@/shared/api/devThemeContext";
import { useTheme } from "@/shared/lib/useTheme";
import { getDefaultThemeColors } from "@/shared/lib/themeColors";

export function DevToolbar() {
  const mode = getDevBridgeMode();
  const { isDark } = useTheme();
  const defaults = getDefaultThemeColors();
  const [palette, setPalette] = useState(
    () => getDevThemeContext().themeColors ?? getDefaultThemeColors(),
  );
  const [customColors, setCustomColors] = useState(() => Boolean(getDevThemeContext().themeColors));

  // 正式构建不包含此模块，宿主内也不显示独立开发操作。
  if (!import.meta.env.DEV || (typeof window !== "undefined" && window.AstrBotPluginPage)) {
    return null;
  }

  return (
    <Dialog>
      <div className="fixed bottom-3 right-3 z-50 flex items-center gap-2 rounded-xl border border-solid border-border bg-card px-3 py-1 text-foreground">
        <span className="font-mono text-xs text-muted-foreground">
          {mode === "mock" ? "DEV: MOCK" : "DEV: PROXY (:6185)"}
        </span>
        <DialogTrigger asChild>
          <Button variant="ghost" size="sm">
            <IconAdjustments aria-hidden="true" />
            开发工具箱
          </Button>
        </DialogTrigger>
      </div>
      <DialogContent>
        <DialogTitle>开发工具箱</DialogTitle>
        <DialogDescription>
          切换通信模式会刷新页面。Mock 使用示例数据，不请求真实业务。
        </DialogDescription>
        <label className="grid gap-2 text-sm">
          通信模式
          <NativeSelect
            value={mode}
            onChange={(event) => {
              const value = event.target.value;
              if (value === "mock" || value === "proxy") setDevBridgeMode(value);
            }}
          >
            <option value="mock">Mock 示例数据</option>
            <option value="proxy">Proxy 直连后端 (:6185)</option>
          </NativeSelect>
        </label>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setDevThemeContext({
                isDark: !isDark,
                ...(customColors ? { themeColors: palette } : {}),
              });
            }}
          >
            <IconSunMoon aria-hidden="true" />
            切换亮色 / 暗黑主题
          </Button>
          <Button
            variant="outline"
            disabled={mode !== "mock"}
            onClick={() => {
              if (mockSSEService.emitTaskHeartbeat()) {
                toast.success("已更新一个示例任务及其日志");
              } else {
                toast.info("没有运行中的示例任务，请先发起分析");
              }
            }}
          >
            <IconBolt aria-hidden="true" />
            注入测试 SSE 任务事件
          </Button>
        </div>
        <fieldset className="m-0 grid gap-3 rounded-xl border border-solid border-border p-4">
          <legend className="px-1 text-sm">宿主配色预览</legend>
          <label className="flex items-center justify-between gap-3 text-sm">
            模拟宿主自定义配色
            <Switch
              aria-label="模拟宿主自定义配色"
              checked={customColors}
              onCheckedChange={(checked) => {
                setCustomColors(checked);
                setDevThemeContext({ isDark, ...(checked ? { themeColors: palette } : {}) });
              }}
            />
          </label>
          <div className="grid grid-cols-2 gap-4">
            {(["primary", "secondary"] as const).map((key) => (
              <label key={key} className="grid gap-2 text-sm">
                {key === "primary" ? "主色" : "辅助色"}
                <input
                  type="color"
                  value={palette[key]}
                  disabled={!customColors}
                  className="h-10 w-full cursor-pointer rounded-lg border border-solid border-input bg-background disabled:opacity-50"
                  onChange={(event) => {
                    const next = { ...palette, [key]: event.target.value };
                    setPalette(next);
                    setDevThemeContext({ isDark, themeColors: next });
                  }}
                />
              </label>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            disabled={
              palette.primary === defaults.primary && palette.secondary === defaults.secondary
            }
            onClick={() => {
              const next = getDefaultThemeColors();
              setPalette(next);
              setDevThemeContext({ isDark, ...(customColors ? { themeColors: next } : {}) });
            }}
          >
            恢复插件默认配色
          </Button>
          <p className="m-0 text-xs text-muted-foreground">
            开关控制模拟，恢复按钮只重置颜色。仅缓存在当前浏览器，警告和错误色不变。
          </p>
        </fieldset>
      </DialogContent>
    </Dialog>
  );
}
