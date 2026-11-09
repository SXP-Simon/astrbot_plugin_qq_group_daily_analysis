import { useCallback, useEffect, useRef, useState } from "react";
import { fetchPluginConfig } from "@/entities/config/api/configApi";

export function useConfigFileReferences(enabled: boolean) {
  const [references, setReferences] = useState(new Map<string, string[]>());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    if (!enabled) return;
    setLoading(true);
    setError("");
    try {
      const result = await fetchPluginConfig();
      const found = new Map<string, string[]>();
      const stack: [string, unknown][] = [["", result.config]];
      while (stack.length) {
        const [key, value] = stack.pop()!;
        if (typeof value === "string" && !/^(https?:|data:)/i.test(value)) {
          const path = value.replace(/\\/g, "/").replace(/^\.\//, "");
          const marker = path.lastIndexOf("/files/");
          const name = path.startsWith("files/")
            ? path.slice(6)
            : marker >= 0
              ? path.slice(marker + 7)
              : "";
          if (name) found.set(name, [...(found.get(name) || []), key]);
        } else if (Array.isArray(value)) {
          value.forEach((entry: unknown, index) => stack.push([`${key}[${index}]`, entry]));
        } else if (value && typeof value === "object") {
          Object.entries(value).forEach(([field, entry]) =>
            stack.push([key ? `${key}.${field}` : field, entry]),
          );
        }
      }
      if (request === sequence.current) setReferences(found);
    } catch (cause) {
      if (request === sequence.current)
        setError(cause instanceof Error ? cause.message : "配置引用读取失败");
    } finally {
      if (request === sequence.current) setLoading(false);
    }
  }, [enabled]);
  useEffect(() => {
    const ref = sequence;
    void refresh();
    return () => {
      ref.current++;
    };
  }, [refresh]);
  return { references, loading, error, refresh };
}
