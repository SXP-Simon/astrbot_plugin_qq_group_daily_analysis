import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";

export interface SectionStats {
  count: number;
  size_bytes: number;
}

export interface PluginDataOverview {
  avatars: SectionStats;
  custom_templates: SectionStats;
  config_files: SectionStats;
  config_backups: SectionStats;
  reports: SectionStats;
  temp_files: SectionStats;
}

export async function fetchPluginDataOverview(): Promise<PluginDataOverview> {
  const res = await apiGet<PluginDataOverview>("plugin-data/overview");
  const data = extractData<PluginDataOverview>(res);
  return (
    data ?? {
      avatars: { count: 0, size_bytes: 0 },
      custom_templates: { count: 0, size_bytes: 0 },
      config_files: { count: 0, size_bytes: 0 },
      config_backups: { count: 0, size_bytes: 0 },
      reports: { count: 0, size_bytes: 0 },
      temp_files: { count: 0, size_bytes: 0 },
    }
  );
}

export async function clearAvatarCache(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/avatars/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearReports(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/reports/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearTempFiles(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/temp/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearCustomTemplates(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/custom-templates/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearConfigFiles(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/config-files/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearConfigBackups(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/config-backups/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

