import { createContext } from "react";
import type { FontDownloadSource } from "../../../entities/config/model/typstFonts";

export interface FontManagementSelection {
  theme: string;
  cdnBaseUrl: string;
  source: FontDownloadSource;
}

export interface FontManagementRequest extends FontManagementSelection { sequence: number }

/** App 负责页面切换；字体功能只声明管理意图和变更通知，不依赖具体页面。 */
export const FontManagementContext = createContext<{
  open: (selection: FontManagementSelection) => void;
  changed: () => void;
  version: number;
} | null>(null);
