import { useEffect, useRef, useState } from "react";
import { testTemplateCdn } from "../../../entities/config/api/configApi";
import type { TemplateCdnProbe } from "../../../entities/config/model/cdnProbe";

export function useTemplateCdnProbe(baseUrl: string) {
  const sequence = useRef(0);
  const pending = useRef(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TemplateCdnProbe | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    sequence.current += 1;
    pending.current = false;
    setLoading(false);
    setResult(null);
    setError("");
    return () => {
      sequence.current += 1;
    };
  }, [baseUrl]);

  const run = async () => {
    if (pending.current) return;
    pending.current = true;
    const requestId = ++sequence.current;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const data = await testTemplateCdn(baseUrl);
      if (sequence.current === requestId) setResult(data);
    } catch (err: unknown) {
      if (sequence.current === requestId) {
        setError(err instanceof Error ? err.message : "CDN 检测失败");
      }
    } finally {
      if (sequence.current === requestId) {
        pending.current = false;
        setLoading(false);
      }
    }
  };

  return { loading, result, error, run };
}
