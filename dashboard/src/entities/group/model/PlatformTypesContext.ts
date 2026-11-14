import { createContext } from "react";

export const PlatformTypesContext = createContext<ReadonlyMap<string, string>>(new Map());
