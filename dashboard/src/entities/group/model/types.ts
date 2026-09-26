import type { components } from "../../../shared/api/generated/schema";

export type ConnectedPlatform = components["schemas"]["ConnectedPlatform"];

export interface GroupItem {
  group_id: string;
  group_name: string;
  platform: string;
}
