import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { fetchConfigFileContent, uploadConfigFile } from "../../../entities/config/api/configApi";

export function useConfigFiles(
  value: unknown,
  multiple: boolean,
  path: string,
  onChange: (value: unknown) => void,
  scope?: Readonly<Record<string, unknown>>,
) {
  const files = Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()))
    : typeof value === "string" && value.trim()
      ? [value.trim()]
      : [];
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const locked = useRef(false);
  const latest = useRef({ value, onChange, path, scope });
  latest.current = { value, onChange, path, scope };
  useEffect(() => {
    const request = sequence;
    locked.current = false;
    setBusy(false);
    setError("");
    return () => {
      request.current++;
      locked.current = false;
    };
  }, [path, scope]);
  const upload = async (selected: File[]) => {
    if (locked.current || !selected.length) return;
    locked.current = true;
    const request = ++sequence.current;
    const before = latest.current;
    setBusy(true);
    setError("");
    try {
      const results = await Promise.allSettled(
        selected.map((file) => uploadConfigFile(file, path)),
      );
      if (
        request !== sequence.current ||
        latest.current.scope !== before.scope ||
        latest.current.path !== before.path ||
        latest.current.value !== before.value
      )
        return;
      const uploaded = results.flatMap((result) =>
        result.status === "fulfilled" && result.value?.path ? [result.value.path] : [],
      );
      if (!uploaded.length) {
        setError("参考文件上传失败，请检查连接后重试。");
        return;
      }
      const next = [...files.filter((file) => !file.startsWith("data:image/")), ...uploaded];
      latest.current.onChange(multiple ? next : uploaded[0]);
      if (uploaded.length !== selected.length)
        toast.warning(
          `已添加 ${uploaded.length} 个文件，另有 ${selected.length - uploaded.length} 个未能上传，请重新选择后重试。`,
        );
      else toast.success(`已添加 ${uploaded.length} 个参考文件`);
    } finally {
      if (request === sequence.current) {
        locked.current = false;
        setBusy(false);
      }
    }
  };
  return {
    files,
    busy,
    error,
    upload,
    remove: (index: number) => {
      if (!locked.current) {
        const next = files.filter((_, i) => i !== index);
        onChange(multiple ? next : next[0] || "");
      }
    },
    add: (entry: string) => {
      const target = entry.trim();
      if (!locked.current && target) onChange(multiple ? [...files, target] : target);
    },
  };
}

/** 本地引用通过既有配置 API 读取，外链图片由浏览器加载。 */
export function useConfigImage(path: string) {
  const remote = /^(https?:\/\/|data:image\/)/.test(path);
  const [result, setResult] = useState<{ path: string; src: string | null; error: string } | null>(
    null,
  );
  useEffect(() => {
    if (remote || !path) return;
    let active = true;
    void fetchConfigFileContent(path)
      .then((data) => {
        if (active)
          setResult({
            path,
            src: data?.data_url ?? null,
            error: data?.data_url ? "" : "参考图片无法读取，请检查文件是否存在。",
          });
      })
      .catch(() => {
        if (active) setResult({ path, src: null, error: "参考图片读取失败，请检查连接后重试。" });
      });
    return () => {
      active = false;
    };
  }, [path, remote]);
  if (remote) return { src: path, loading: false, error: "" };
  const current = result?.path === path ? result : null;
  return {
    src: current?.src ?? null,
    loading: Boolean(path && !current),
    error: current?.error ?? "",
  };
}
