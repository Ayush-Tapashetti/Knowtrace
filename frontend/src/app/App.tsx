import { Route, Routes } from "react-router-dom";

import { ApiContext } from "../api/context";
import { api, type Api } from "../api/endpoints";
import { AppShell } from "../components/layout/AppShell";
import { EvaluationPage } from "../pages/EvaluationPage";
import { GraphPage } from "../pages/GraphPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PracticePage } from "../pages/PracticePage";

/** Routes only; the router itself is provided by `main.tsx` (or a test). */
export function AppRoutes({ client }: { client?: Api }) {
  return (
    <ApiContext.Provider value={client ?? api}>
      <Routes>
        <Route element={<AppShell client={client} />}>
          <Route index element={<PracticePage />} />
          <Route path="map" element={<GraphPage />} />
          <Route path="evaluation" element={<EvaluationPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ApiContext.Provider>
  );
}
