import { useEffect, useRef, useState } from "react";
import { testCustomT2i } from "../../../entities/config/api/configApi";
import type { CustomT2iProbe, CustomT2iProbeInput } from "../../../entities/config/model/customT2iProbe";

export function useCustomT2iProbe(input: CustomT2iProbeInput) {
  const sequence = useRef(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CustomT2iProbe | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    sequence.current += 1;
    setLoading(false);
    setResult(null);
    setError("");
    return () => { sequence.current += 1; };
  }, [input.service_endpoint, input.service_token, input.timeout, input.request_timeout]);

  const run = async () => {
    if (loading) return;
    const requestId = ++sequence.current;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const data = await testCustomT2i(input);
      if (sequence.current === requestId) setResult(data);
    } catch (err: unknown) {
      if (sequence.current === requestId) setError(err instanceof Error ? err.message : "测试没能完成，请稍后再试。");
    } finally {
      if (sequence.current === requestId) setLoading(false);
    }
  };

  return { loading, result, error, run };
}
