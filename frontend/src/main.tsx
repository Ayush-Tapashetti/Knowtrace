import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { queryClient } from "./api/queryClient";
import { AppRoutes } from "./app/App";
import { ErrorBoundary } from "./components/ui/states";
import "./index.css";

const root = document.getElementById("root");
if (root === null) throw new Error("#root missing from index.html");
createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
);
