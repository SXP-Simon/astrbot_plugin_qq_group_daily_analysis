import { Space } from "antd";
import { usePartitionManager, type StorageNavigation } from "../../model/usePartitionManager";
import { StorageOverview } from "./StorageOverview";
import { ManagedPartitionDrawer } from "./ManagedPartitionDrawer";

export function ManagedFilesPanel(navigation: StorageNavigation) {
  const manager = usePartitionManager(navigation);
  return <Space direction="vertical" size="middle" style={{ width: "100%" }}>
    <StorageOverview vm={manager.files} onSelect={manager.openPartition} />
    <ManagedPartitionDrawer manager={manager} />
  </Space>;
}
