import { useState } from "react";
import { toast } from "sonner";
import {
  refreshComicPreview,
  type ComicPreviewRequest,
} from "../../../../entities/comic/api/comicApi";
import { comicPresets } from "../../../../entities/comic/model/comicPresets";
import { Button } from "../../../../shared/ui/button";
import { NativeSelect } from "../../../../shared/ui/native-select";

export function ComicPreviewRefresh({ onChanged }: { onChanged: () => void }) {
  const [presetId, setPresetId] = useState("classic");
  const [variant, setVariant] = useState<ComicPreviewRequest["variant"]>("thumbnail");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={async (event) => {
        event.preventDefault();
        if (busy) return;
        setBusy(true);
        setError("");
        try {
          await refreshComicPreview({ preset_id: presetId, variant });
          onChanged();
          toast.success("漫画样图已更新");
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : "重新获取漫画样图失败");
        } finally {
          setBusy(false);
        }
      }}
    >
      <label className="grid min-w-0 gap-1 text-sm text-muted-foreground">
        漫画风格
        <NativeSelect
          value={presetId}
          onChange={(event) => setPresetId(event.target.value)}
          disabled={busy}
        >
          {comicPresets.map(({ id, name }) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </NativeSelect>
      </label>
      <label className="grid gap-1 text-sm text-muted-foreground">
        样图类型
        <NativeSelect
          value={variant}
          onChange={(event) =>
            setVariant(event.target.value === "preview" ? "preview" : "thumbnail")
          }
          disabled={busy}
        >
          <option value="thumbnail">缩略图</option>
          <option value="preview">完整图</option>
        </NativeSelect>
      </label>
      <Button type="submit" variant="outline" disabled={busy}>
        {busy ? "正在获取样图…" : "重新获取样图"}
      </Button>
      {error && (
        <p role="alert" className="m-0 w-full text-sm text-destructive">
          {error}
        </p>
      )}
    </form>
  );
}
