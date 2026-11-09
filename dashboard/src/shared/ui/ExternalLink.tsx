import { useEffect, useRef, useState, type ReactNode } from "react";
import { IconCopy } from "@tabler/icons-react";
import { copyToClipboard } from "@/shared/lib/clipboard";
import { Button } from "./button";
import { Input } from "./input";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./dialog";

/** 宿主可能限制打开新标签页，保留可手动选择和复制的外部地址。 */
export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [copying, setCopying] = useState(false);
  const [result, setResult] = useState<"success" | "failure" | null>(null);
  const pending = useRef(false);
  const generation = useRef(0);
  useEffect(() => {
    const requests = generation;
    ++requests.current;
    pending.current = false;
    setCopying(false);
    setResult(null);
    return () => {
      ++requests.current;
    };
  }, [href]);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        ++generation.current;
        pending.current = false;
        setCopying(false);
        setResult(null);
        setOpen(next);
      }}
    >
      <DialogTrigger asChild>
        <Button
          variant="link"
          size="sm"
          className="h-auto whitespace-normal p-0 text-secondary-ink decoration-secondary-line hover:text-secondary-ink hover:decoration-secondary-ink"
        >
          {children}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>{children}</DialogTitle>
        <DialogDescription>复制地址后，在浏览器的新标签页打开。</DialogDescription>
        <Input
          aria-label="外部地址"
          readOnly
          value={href}
          className="font-mono text-sm"
          onFocus={(event) => event.currentTarget.select()}
        />
        <Button
          variant="outline"
          disabled={copying}
          onClick={async () => {
            if (pending.current) return;
            pending.current = true;
            setCopying(true);
            setResult(null);
            const current = generation.current;
            const copied = await copyToClipboard(href);
            if (current !== generation.current) return;
            pending.current = false;
            setCopying(false);
            setResult(copied ? "success" : "failure");
          }}
        >
          <IconCopy aria-hidden="true" />
          {copying ? "正在复制…" : "复制地址"}
        </Button>
        {result && (
          <p
            role="status"
            className={`m-0 text-sm ${result === "success" ? "text-success" : "text-warning"}`}
          >
            {result === "success" ? "地址已复制" : "无法自动复制，请选择上方地址后手动复制。"}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
