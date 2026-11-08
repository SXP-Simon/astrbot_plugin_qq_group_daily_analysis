import { useState } from "react";
import { IconFile, IconPhoto, IconPlus, IconTrash, IconUpload } from "@tabler/icons-react";
import { useConfigFiles, useConfigImage } from "../model/useConfigFiles";
import { Button } from "../../../shared/ui/button";
import { Input } from "../../../shared/ui/input";
import { ImagePreview } from "../../../shared/ui/image-preview";
import { FilePicker } from "../../../shared/ui/file-picker";

function ReferenceImage({ path }: { path: string }) {
  const image = useConfigImage(path);
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  return (
    <>
      <button
        type="button"
        aria-label={`预览参考图片 ${path}`}
        onClick={() => setOpen(true)}
        className="flex size-12 shrink-0 cursor-zoom-in items-center justify-center overflow-hidden rounded-lg border border-solid border-border bg-muted/40 text-secondary-ink focus-visible:outline-2 focus-visible:outline-ring"
      >
        {image.src && failed !== image.src ? (
          <img
            src={image.src}
            alt="参考图片"
            className="size-full object-cover"
            onError={() => setFailed(image.src)}
          />
        ) : (
          <IconPhoto aria-hidden="true" />
        )}
      </button>
      {open && (
        <ImagePreview
          src={image.src}
          loading={image.loading}
          error={image.error}
          title={`参考图片 · ${path.startsWith("data:") ? "内嵌图片" : path}`}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

export function ConfigFileField({
  value,
  multiple,
  path,
  onChange,
  fileTypes,
  scope,
}: {
  value: unknown;
  multiple: boolean;
  path: string;
  onChange: (value: unknown) => void;
  fileTypes?: string[];
  scope?: Readonly<Record<string, unknown>>;
}) {
  const vm = useConfigFiles(value, multiple, path, onChange, scope);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const add = () => {
    if (draft.trim()) {
      vm.add(draft);
      setDraft("");
      setAdding(false);
    }
  };
  return (
    <div className="grid min-w-0 gap-3">
      {vm.error && (
        <p role="alert" className="m-0 text-sm text-destructive">
          {vm.error}
        </p>
      )}
      {vm.files.length ? (
        <ul className="m-0 grid list-none gap-2 p-0">
          {vm.files.map((file, index) => {
            const image =
              /^(data:image\/|https?:\/\/|files\/)/.test(file) ||
              /\.(png|jpe?g|webp|gif|svg)$/i.test(file);
            return (
              <li
                key={`${file}:${index}`}
                className="flex min-w-0 items-center gap-3 rounded-xl bg-muted/40 p-2"
              >
                {image ? (
                  <ReferenceImage key={file} path={file} />
                ) : (
                  <IconFile className="size-6 shrink-0 text-muted-foreground" aria-hidden="true" />
                )}
                <div className="min-w-0 grow">
                  <code
                    className="block truncate text-xs"
                    title={file.startsWith("data:") ? "内嵌参考图片" : file}
                  >
                    {file.startsWith("data:") ? "内嵌参考图片" : file}
                  </code>
                  {image && <span className="text-xs text-muted-foreground">点击缩略图预览</span>}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={vm.busy}
                  className="text-destructive"
                  aria-label={`移除参考文件 ${index + 1}`}
                  onClick={() => vm.remove(index)}
                >
                  <IconTrash aria-hidden="true" />
                  移除
                </Button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="m-0 text-sm text-muted-foreground">
          尚未添加参考文件，可上传图片或填写地址。
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <FilePicker
          accept={fileTypes?.map((ext) => `.${ext.replace(/^\./, "")}`).join(",") || "image/*"}
          label="选择参考文件"
          disabled={vm.busy}
          {...(multiple
            ? { multiple: true as const, onSelect: (files: File[]) => void vm.upload(files) }
            : { multiple: false as const, onSelect: (file: File) => void vm.upload([file]) })}
        >
          <IconUpload aria-hidden="true" />
          {vm.busy ? "正在上传…" : "上传本地图片"}
        </FilePicker>
        <Button variant="outline" disabled={vm.busy} onClick={() => setAdding(true)}>
          <IconPlus aria-hidden="true" />
          添加图片 URL / 路径
        </Button>
      </div>
      {adding && (
        <div className="flex flex-wrap items-center gap-2">
          <Input
            className="min-w-40 basis-60 grow font-mono"
            aria-label="参考文件地址"
            placeholder="图片 URL 或相对路径"
            value={draft}
            disabled={vm.busy}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                add();
              }
            }}
          />
          <Button disabled={vm.busy || !draft.trim()} onClick={add}>
            添加
          </Button>
          <Button variant="outline" onClick={() => setAdding(false)}>
            取消
          </Button>
        </div>
      )}
    </div>
  );
}
