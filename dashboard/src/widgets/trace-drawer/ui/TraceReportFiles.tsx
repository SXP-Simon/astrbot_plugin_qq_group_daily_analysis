import { IconDownload, IconEye, IconFile } from "@tabler/icons-react";
import { Button } from "@/shared/ui/button";
import { formatBytes } from "@/shared/lib/formatters";

interface TraceReportFilesProps {
  files: { filename: string; isHtml: boolean; isComic: boolean; size?: number }[];
  downloading?: boolean;
  onPreviewFile: (filename: string, isHtml: boolean) => void;
  onDownloadFile: (filename: string, isHtml: boolean) => void;
}

export function TraceReportFiles({
  files,
  downloading,
  onPreviewFile,
  onDownloadFile,
}: TraceReportFilesProps) {
  if (files.length === 0) return null;
  return (
    <ul aria-label="报告文件" className="m-0 grid list-none gap-2 p-0">
      {files.map((file) => (
        <li
          key={file.filename}
          className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-2 rounded-xl bg-muted/60 px-3 py-2 sm:flex"
        >
          <IconFile className="size-4 shrink-0" aria-hidden="true" />
          <span className="min-w-0 flex-1 break-all font-mono text-xs">{file.filename}</span>
          <div className="col-span-2 flex flex-wrap items-center justify-end gap-2">
            <span className="mr-auto text-xs text-muted-foreground">
              {file.isComic ? "群漫画" : file.isHtml ? "HTML" : "图片"}
              {file.size != null ? ` · ${formatBytes(file.size)}` : ""}
            </span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onPreviewFile(file.filename, file.isHtml)}
            >
              <IconEye aria-hidden="true" />
              预览
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={downloading}
              onClick={() => onDownloadFile(file.filename, file.isHtml)}
            >
              <IconDownload aria-hidden="true" />
              下载
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
