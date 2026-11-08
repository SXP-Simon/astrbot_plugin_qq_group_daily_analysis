import { useId, useRef, type ReactNode } from "react";
import { Button } from "./button";

type FilePickerProps = {
  label: string;
  accept?: string;
  disabled?: boolean;
  children: ReactNode;
} & (
  | { multiple?: false; onSelect: (file: File) => void }
  | { multiple: true; onSelect: (files: File[]) => void }
);

export function FilePicker(props: FilePickerProps) {
  const { label, accept, disabled = false, children } = props;
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
        multiple={props.multiple}
        disabled={disabled}
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          // 先复位，允许校验失败或取消后再次选择同一个文件。
          event.target.value = "";
          if (!disabled && files.length) {
            if (props.multiple) props.onSelect(files);
            else props.onSelect(files[0]);
          }
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
