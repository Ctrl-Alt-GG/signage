import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "./app.css";

import { StrictMode, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { fetchScreens, makeClient } from "./api/client";
import { App } from "./App";

// The frontend only ever talks to the backend, which nginx (or the Vite dev server)
// serves on the same origin.
const API_BASE = "/api/v1/";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 60_000),
      refetchOnWindowFocus: false,
      staleTime: 5_000,
      gcTime: Infinity,
    },
  },
});

/** Any path without a screen slug goes to the screen the admin marks as default. */
function DefaultScreen() {
  const client = useMemo(() => makeClient(window.location.origin), []);
  const query = useQuery({ queryKey: ["screens"], queryFn: () => fetchScreens(client) });
  if (query.isPending) return null;
  const target = query.data?.find((screen) => screen.is_default) ?? query.data?.[0];
  return <Navigate to={`/display/${target?.slug ?? "main"}/`} replace />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/display/:slug" element={<App apiBase={API_BASE} />} />
          <Route path="*" element={<DefaultScreen />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
