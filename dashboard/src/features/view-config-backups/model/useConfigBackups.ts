import { useRef, useState } from "react";
import {
  fetchConfigBackup,
  fetchConfigBackups,
} from "../../../entities/plugin-data/api/pluginDataApi";
import type {
  ConfigBackupDetail,
  ConfigBackupInfo,
} from "../../../entities/plugin-data/model/configBackup";

export function useConfigBackups() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ConfigBackupInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<ConfigBackupDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const listRequest = useRef(0);
  const detailRequest = useRef(0);

  const load = async () => {
    const request = ++listRequest.current;
    ++detailRequest.current;
    setOpen(true);
    setLoading(true);
    setItems([]);
    setError("");
    setDetail(null);
    setDetailError("");
    setDetailLoading(false);
    try {
      const backups = await fetchConfigBackups();
      if (request === listRequest.current) setItems(backups);
    } catch {
      if (request === listRequest.current)
        setError("备份列表暂时读不到，请稍后刷新重试。");
    } finally {
      if (request === listRequest.current) setLoading(false);
    }
  };

  const select = async (filename: string) => {
    const request = ++detailRequest.current;
    setDetail(null);
    setDetailLoading(true);
    setDetailError("");
    try {
      const backup = await fetchConfigBackup(filename);
      if (request === detailRequest.current) setDetail(backup);
    } catch {
      if (request === detailRequest.current)
        setDetailError(
          "这份备份暂时无法打开，可能已被清理或内容损坏。请刷新列表后重试。",
        );
    } finally {
      if (request === detailRequest.current) setDetailLoading(false);
    }
  };

  const close = () => {
    ++listRequest.current;
    ++detailRequest.current;
    setOpen(false);
    setDetail(null);
  };

  return {
    open,
    items,
    loading,
    error,
    detail,
    detailLoading,
    detailError,
    load,
    select,
    close,
  };
}
