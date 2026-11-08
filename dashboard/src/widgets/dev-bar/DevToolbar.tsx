import { IconAdjustments, IconBolt, IconSunMoon } from "@tabler/icons-react";
import { toast } from "sonner";
import { getDevBridgeMode, setDevBridgeMode } from "../../shared/api/devBridge";
import { mockSSEService } from "../../mocks/sseMock";
import { Button } from "../../shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../../shared/ui/dialog";
import { NativeSelect } from "../../shared/ui/native-select";

export function DevToolbar() {
  const mode = getDevBridgeMode();

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
              const current = localStorage.getItem("astrbot_plugin_theme_is_dark") === "true";
              localStorage.setItem("astrbot_plugin_theme_is_dark", String(!current));
              window.location.reload();
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
      </DialogContent>
    </Dialog>
  );
}
