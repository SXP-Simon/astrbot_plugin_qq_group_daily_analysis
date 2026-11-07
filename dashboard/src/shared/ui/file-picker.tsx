import { useId, useRef, type ReactNode } from "react";
import { Button } from "./button";

export function FilePicker({
  label,
  accept,
  disabled = false,
  onSelect,
  children,
}: {
  label: string;
  accept?: string;
  disabled?: boolean;
  onSelect: (file: File) => void;
  children: ReactNode;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  return (
    <span className="inline-flex">
      <input
        ref={input}
        id={id}
        type="file"
        className="sr-only"
        tabIndex={-1}
        aria-label={label}
        accept={accept}
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          // 先复位，允许校验失败或取消后再次选择同一个文件。
          event.target.value = "";
          if (file && !disabled) onSelect(file);
        }}
      />
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => input.current?.click()}
      >
        {children}
      </Button>
    </span>
  );
}
