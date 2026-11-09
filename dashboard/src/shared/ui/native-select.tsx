import * as React from "react";
import { IconChevronDown } from "@tabler/icons-react";
import { cn } from "@/shared/lib/cn";

export const NativeSelect = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <div className="relative w-full">
    <select
      ref={ref}
      data-slot="native-select"
      className={cn(
        "h-10 w-full min-w-0 appearance-none rounded-xl border border-solid border-input bg-background py-2 pl-3 pr-9 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
    <IconChevronDown
      className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
      aria-hidden="true"
    />
  </div>
));
NativeSelect.displayName = "NativeSelect";
