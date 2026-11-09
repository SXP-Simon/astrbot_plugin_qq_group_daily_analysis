import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  fetchComicRotation,
  resetComicRotation,
  type ComicRotationEntry,
  type ComicRotationScope,
} from "../../../entities/comic/api/comicApi";
import { Alert } from "../../../shared/ui/alert";
import { Button } from "../../../shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../../../shared/ui/dialog";

export function ComicRotationDialog() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ComicRotationEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const [target, setTarget] = useState<{ label: string; scope: ComicRotationScope } | null>(null);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setError("");
    void fetchComicRotation()
      .then((result) => {
        if (active) setItems(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setItems([]);
          setError(reason instanceof Error ? reason.message : "读取漫画轮换进度失败");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [open, version]);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (busy) return;
        if (!next) setTarget(null);
        setOpen(next);
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          查看轮换进度
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogTitle>漫画风格轮换进度</DialogTitle>
        <DialogDescription>
          这里显示已保存的轮换记录。重置后，下次生成时会为所选范围重新开始轮换。
        </DialogDescription>
        {error && <Alert variant="destructive">{error}</Alert>}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={busy || loading}
            onClick={() => setVersion((value) => value + 1)}
          >
            刷新进度
          </Button>
          <Button
            variant="outline"
            disabled={busy || loading || (!items.length && !error)}
            onClick={() => setTarget({ label: "全部群聊及共享范围", scope: { scope: "all" } })}
          >
            重置全部进度
          </Button>
        </div>
        {target && (
          <Alert variant="warning">
            <p className="m-0">重置「{target.label}」的轮换进度？</p>
            <div className="mt-2 flex gap-2">
              <Button size="sm" variant="outline" disabled={busy} onClick={() => setTarget(null)}>
                取消
              </Button>
              <Button
                size="sm"
                variant="destructive"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  try {
                    await resetComicRotation(target.scope);
                    setTarget(null);
                    setVersion((value) => value + 1);
                    toast.success("轮换进度已重置");
                  } catch (reason) {
                    setError(reason instanceof Error ? reason.message : "重置轮换进度失败");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? "正在重置…" : "确认重置"}
              </Button>
            </div>
          </Alert>
        )}
        {loading ? (
          <p role="status" className="m-0 text-sm text-muted-foreground">
            正在读取轮换进度…
          </p>
        ) : !items.length ? (
          !error && <p className="m-0 text-sm text-muted-foreground">暂无轮换记录。</p>
        ) : (
          <ul className="m-0 divide-y divide-border rounded-xl border border-border p-0">
            {items.map((item) => {
              const { platform_id, group_id } = item;
              const grouped = platform_id !== null && group_id !== null;
              const label = grouped ? `${platform_id} · ${group_id}` : "所有群共享";
              return (
                <li
                  key={JSON.stringify([item.platform_id, item.group_id])}
                  className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm"
                >
                  <div className="min-w-0 [overflow-wrap:anywhere]">
                    <p className="m-0 font-medium">{label}</p>
                    <p className="m-0 text-muted-foreground">
                      上次选择 {item.last_style_name || `方案 ${item.last_style_number}`} ·{" "}
                      {item.selected_date}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    aria-label={`重置 ${label} 的轮换进度`}
                    onClick={() =>
                      setTarget({
                        label,
                        scope: grouped
                          ? { scope: "group", platform_id, group_id }
                          : { scope: "global" },
                      })
                    }
                  >
                    重置
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}
