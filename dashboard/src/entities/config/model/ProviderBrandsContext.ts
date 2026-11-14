import { createContext } from "react";

export const ProviderBrandsContext = createContext<ReadonlyMap<string, string>>(new Map());
