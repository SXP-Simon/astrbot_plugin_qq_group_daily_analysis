import { createContext } from "react";

export interface ResourceManagementSelection { theme: string; cdnBaseUrl: string }
export interface ResourceManagementRequest extends ResourceManagementSelection { sequence: number }

/** 特征只声明素材管理意图，App 负责切页，分区页面消费一次请求。 */
export const ResourceManagementContext = createContext<{
  open: (selection: ResourceManagementSelection) => void;
  request: ResourceManagementRequest | null;
  handled: () => void;
  changed: () => void;
  version: number;
} | null>(null);
