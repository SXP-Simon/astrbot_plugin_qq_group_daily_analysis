import { useEffect, useState } from "react";
import { useManagedFiles } from "../../../features/manage-stored-files/model/useManagedFiles";
import { useConfigFileReferences } from "../../../features/manage-stored-files/model/useConfigFileReferences";
import { partitionNavigation, type PartitionNavigation } from "../../../entities/plugin-data/model/partitionPresentation";
import type { ManagedPartition } from "../../../entities/plugin-data/api/managedFilesApi";
import type { FontManagementRequest } from "../../../features/manage-typst-fonts/model/FontManagementContext";

export interface StorageNavigation {
  onNavigate?: (page: "reports" | "config" | "traces") => void;
  onOpenDataTab?: (tab: "records" | "incremental" | "checkpoints") => void;
  fontRequest?: FontManagementRequest | null;
  onFontRequestHandled?: () => void;
}

export function usePartitionManager({ onNavigate, onOpenDataTab, fontRequest, onFontRequestHandled }: StorageNavigation) {
  const files = useManagedFiles();
  const [installing, setInstalling] = useState(false);
  const [fontSelection, setFontSelection] = useState<FontManagementRequest | null>(null);
  useEffect(() => {
    if (!fontRequest) return;
    const target = files.partitions.find(item => item.key === "typst_fonts");
    if (!target) return;
    setInstalling(false); setFontSelection(fontRequest); files.select(target); onFontRequestHandled?.();
    // select 只更新本地抽屉状态；请求消费后不会因刷新分区重新打开抽屉。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fontRequest, files.partitions, onFontRequestHandled]);
  const partition = files.partitions.find(item => item.key === files.partition?.key) || files.partition;
  const references = useConfigFileReferences(partition?.key === "config_files");
  const links = (partitionNavigation[partition?.key || ""] || []).filter(link => link.kind === "page" ? !!onNavigate : !!onOpenDataTab);
  return { files, partition, references, links, installing, setInstalling, fontSelection,
    openPartition: (value: ManagedPartition) => { setInstalling(false); setFontSelection(null); files.select(value); },
    navigate: (link: PartitionNavigation) => { files.select(null); if (link.kind === "page") onNavigate?.(link.destination); else onOpenDataTab?.(link.destination); },
    refresh: () => { void files.load(); void files.refresh(); void references.refresh(); },
  };
}
