import { z } from "zod";
import type { components } from "../../../shared/api/generated/schema";

export type ConfigBackupInfo = components["schemas"]["ConfigBackupInfo"];
export type ConfigBackupDetail = components["schemas"]["ConfigBackupDetail"];
export type BackupJsonValue = components["schemas"]["BackupJsonValue"];

export const configBackupInfoSchema: z.ZodType<ConfigBackupInfo> = z.object({
  filename: z.string().min(1),
  size_bytes: z.number().int().nonnegative(),
  kind: z.enum(["upgrade", "comic_migration", "other"]),
  plugin_version: z.string().nullable(),
  saved_at: z.string().nullable(),
  error: z.string().nullable(),
});

export const configBackupListSchema = z.object({
  items: z.array(configBackupInfoSchema),
});
export const configBackupDetailSchema: z.ZodType<ConfigBackupDetail> = z.object(
  {
    backup: configBackupInfoSchema,
    content: z.json(),
  },
);
