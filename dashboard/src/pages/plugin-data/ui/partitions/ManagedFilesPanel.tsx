import {
  usePartitionManager,
  type StorageNavigation,
} from "@/pages/plugin-data/model/usePartitionManager";
import { StorageOverview } from "./StorageOverview";
import { ManagedPartitionDrawer } from "./ManagedPartitionDrawer";

export function ManagedFilesPanel(navigation: StorageNavigation) {
  const manager = usePartitionManager(navigation);
  return (
    <div className="grid min-w-0 gap-5">
      <StorageOverview vm={manager.files} onSelect={manager.openPartition} />
      <ManagedPartitionDrawer manager={manager} />
    </div>
  );
}
