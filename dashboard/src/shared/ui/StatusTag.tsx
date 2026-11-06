import {
  IconAlertCircle,
  IconCheck,
  IconClock,
  IconLoader2,
  IconPlayerStop,
  IconPlayerSkipForward,
  IconX,
} from "@tabler/icons-react";

export function StatusTag({ status }: { status: string }) {
  const states = new Map([
    ["pending", { label: "待处理", icon: IconClock }],
    ["succeeded", { label: "成功", icon: IconCheck }],
    ["completed", { label: "成功", icon: IconCheck }],
    ["warning", { label: "警告", icon: IconAlertCircle }],
    ["partial_success", { label: "部分成功", icon: IconAlertCircle }],
    ["failed", { label: "失败", icon: IconX }],
    ["running", { label: "运行中", icon: IconLoader2 }],
    ["aborted", { label: "已中止", icon: IconPlayerStop }],
    ["cancelled", { label: "已中止", icon: IconPlayerStop }],
    ["skipped", { label: "已跳过", icon: IconPlayerSkipForward }],
  ]);
  const item = states.get(status);
  const Icon = item?.icon ?? IconAlertCircle;
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg px-2 py-1 text-xs font-medium ${status === "failed" ? "bg-destructive/10 text-destructive" : status === "running" ? "bg-accent text-foreground" : "bg-muted text-foreground"}`}
    >
      <Icon
        className={`size-3.5 ${status === "running" ? "animate-spin" : ""}`}
        aria-hidden="true"
      />
      {item?.label ?? (status || "状态未记录")}
    </span>
  );
}
