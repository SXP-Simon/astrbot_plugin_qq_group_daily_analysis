import { useEffect, useState } from "react";
import { useTraceDetail } from "./useTraceDetail";
import { useTraceActions } from "./useTraceActions";

export function useTraceDrawerViewModel(traceId: string | null, open: boolean) {
  const [selection, setSelection] = useState<{ sourceId: string; id: string } | null>(null);
  const activeId = selection?.sourceId === traceId ? selection.id : traceId;
  const detail = useTraceDetail(activeId, open);
  useEffect(() => {
    setSelection(null);
  }, [traceId, open]);
  const actions = useTraceActions(traceId, open, detail.trace, (id) => {
    if (!traceId) return;
    setSelection({ sourceId: traceId, id });
    if (id === activeId) detail.refresh();
  });
  return { ...detail, ...actions };
}
