import { useEffect, useRef, useState } from "react";
import { IconPlayerStop } from "@tabler/icons-react";
import { Button } from "@/shared/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/ui/dialog";

interface CancelTaskButtonProps {
  taskId: string;
  taskLabel?: string;
  onCancel: (taskId: string) => Promise<boolean | void> | boolean | void;
  onRemovedFocus?: () => void;
}

export function CancelTaskButton({
  taskId,
  taskLabel,
  onCancel,
  onRemovedFocus,
}: CancelTaskButtonProps) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const pendingRef = useRef(false);
  const mounted = useRef(true);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const confirm = async () => {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    setError("");
    try {
      const accepted = await onCancel(taskId);
      if (!mounted.current) return;
      if (accepted === false) {
        setError("中止请求未成功。请检查连接，或刷新确认任务是否已结束。");
      } else {
        setOpen(false);
      }
    } catch {
      if (mounted.current) setError("中止请求未成功。请检查连接后重试。");
    } finally {
      pendingRef.current = false;
      if (mounted.current) setPending(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!pendingRef.current) {
          setOpen(next);
          setError("");
        }
      }}
    >
      <Button
        ref={triggerRef}
        size="sm"
        variant="ghost"
        className="text-destructive"
        onClick={() => setOpen(true)}
      >
        <IconPlayerStop aria-hidden="true" />
        中止
      </Button>
      <DialogContent
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          cancelRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (triggerRef.current?.isConnected) triggerRef.current.focus();
          else onRemovedFocus?.();
        }}
      >
        <DialogTitle>中止这项分析？</DialogTitle>
        <DialogDescription>
          只中止下方任务，不影响其他任务。后台收到请求后会停止后续处理并清理资源，这可能需要一点时间。
        </DialogDescription>
        <div className="min-w-0 space-y-1">
          {taskLabel && <p className="m-0 break-words text-sm">{taskLabel}</p>}
          <p className="m-0 break-all font-mono text-xs text-muted-foreground">{taskId}</p>
        </div>
        {error && (
          <p role="alert" className="m-0 text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button
            ref={cancelRef}
            variant="outline"
            disabled={pending}
            onClick={() => setOpen(false)}
          >
            继续分析
          </Button>
          <Button variant="destructive" disabled={pending} onClick={() => void confirm()}>
            {pending ? "正在请求…" : "确认中止"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
