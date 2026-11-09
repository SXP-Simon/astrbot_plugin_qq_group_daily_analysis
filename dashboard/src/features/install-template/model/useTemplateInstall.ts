import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  installTemplateFromUrl,
  installTemplateFromFile,
  type TemplateInstallResult,
} from "@/entities/report/api/reportApi";

export function useTemplateInstall(
  open: boolean,
  onClose: () => void,
  onInstalled?: (result: TemplateInstallResult) => void,
) {
  const [method, setMethod] = useState("url");
  const [url, setUrl] = useState("");
  const [names, setNames] = useState({ url: "", file: "" });
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const epoch = useRef(0);
  const pending = useRef(false);
  const visible = useRef(open);
  visible.current = open;
  useEffect(() => {
    const lifecycle = epoch;
    lifecycle.current++;
    pending.current = false;
    setBusy(false);
    if (!open) {
      setUrl("");
      setNames({ url: "", file: "" });
      setFile(null);
      setError("");
    }
    return () => {
      lifecycle.current++;
    };
  }, [open]);
  return {
    method,
    url,
    names,
    file,
    busy,
    error,
    setMethod,
    setUrl,
    setName: (name: string) => setNames((current) => ({ ...current, [method]: name })),
    pickFile: (picked: File | null) => {
      if (pending.current) return;
      if (picked && !/\.zip$/i.test(picked.name)) {
        setError("请选择 ZIP 压缩包。");
        return;
      }
      setFile(picked);
      setError("");
    },
    close: () => {
      if (!pending.current) onClose();
    },
    install: async () => {
      if (pending.current || !visible.current) return;
      if (
        method === "url" &&
        !/^https:\/\/(?:www\.)?github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:[/?#]|$)/i.test(
          url.trim(),
        )
      ) {
        setError("请填写 GitHub 仓库链接，例如 https://github.com/owner/repo。");
        return;
      }
      if (method === "file" && !file) {
        setError("请先选择 ZIP 压缩包。");
        return;
      }
      const request = epoch.current;
      pending.current = true;
      setBusy(true);
      setError("");
      try {
        const name = (method === "file" ? names.file : names.url).trim() || undefined;
        const result =
          method === "file" && file
            ? await installTemplateFromFile(file, name)
            : await installTemplateFromUrl({ repo_url: url.trim(), name });
        if (request !== epoch.current || !visible.current) return;
        if (!result) throw new Error("安装未完成，请检查模板入口与服务器日志。");
        toast.success(`模板已安装：${result.label}（${result.name}）`);
        onInstalled?.(result);
        onClose();
      } catch (cause) {
        if (request === epoch.current && visible.current)
          setError(
            cause instanceof Error ? cause.message : "安装失败，请检查网络和模板内容后重试。",
          );
      } finally {
        if (request === epoch.current) {
          pending.current = false;
          setBusy(false);
        }
      }
    },
  };
}
