import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "./app.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router";

import { App } from "./App";

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

const body = document.body.dataset;
const fallbackScreen = body.screen ?? "main";
const apiBase = body.apiBase ?? "/api/v1/";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/display/:slug" element={<App apiBase={apiBase} fallbackScreen={fallbackScreen} />} />
          <Route path="*" element={<App apiBase={apiBase} fallbackScreen={fallbackScreen} />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
