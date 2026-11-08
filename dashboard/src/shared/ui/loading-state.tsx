import type { ComponentProps } from "react";
import { IconLoader2 } from "@tabler/icons-react";
import { cn } from "../lib/cn";

/** 在请求所属区域显示加载反馈；骨架只占位，不冒充真实数据。 */
export function LoadingState({
  children,
  className,
  skeleton = false,
  ...props
}: {
  skeleton?: boolean;
} & ComponentProps<"div">) {
  return (
    <div
      {...props}
      role="status"
      aria-live="polite"
      className={cn("grid gap-4 text-sm text-muted-foreground", className)}
    >
      <div className="flex items-center gap-2">
        <IconLoader2
          aria-hidden="true"
          data-slot="loading-spinner"
          className="size-4 shrink-0 animate-spin text-primary-ink motion-reduce:animate-none"
        />
        <span>{children}</span>
      </div>
      {skeleton && <LoadingSkeleton />}
    </div>
  );
}

/** 在表格内部或详情区域保持占位，避免表头随着加载提示上下移动。 */
export function LoadingSkeleton() {
  return (
    <div aria-hidden="true" className="grid gap-3 py-2 motion-safe:animate-pulse">
      <div className="h-4 w-2/3 rounded-md bg-secondary-soft" />
      <div className="h-4 w-full rounded-md bg-secondary-soft" />
      <div className="h-4 w-4/5 rounded-md bg-secondary-soft" />
    </div>
  );
}
