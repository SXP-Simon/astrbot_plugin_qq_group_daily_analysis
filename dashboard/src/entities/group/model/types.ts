import type { components } from "../../../shared/api/generated/schema";
import { z } from "zod";

export type ConnectedPlatform = components["schemas"]["ConnectedPlatform"];

export type GroupItem = components["schemas"]["GroupItem"];

export const groupItemSchema: z.ZodType<GroupItem> = z.object({
  group_id: z.string().min(1),
  group_name: z.string(),
  platform: z.string(),
});
