import { createContext, type ReactNode } from "react";

import { api, type Api } from "./endpoints";

/** Defaults to the shared client, so the app needs no provider; tests wrap pages in `ApiProvider`. */
export const ApiContext = createContext<Api>(api);

export function ApiProvider({
  client,
  children,
}: {
  client: Api;
  children: ReactNode;
}) {
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}
