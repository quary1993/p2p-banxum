import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test } from "vitest";

import { App } from "./App";

function renderApp() {
  const queryClient = new QueryClient();

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

test("renders the BANXUM scaffold shell", () => {
  renderApp();

  expect(screen.getByRole("heading", { name: "BANXUM" })).toBeInTheDocument();
  expect(screen.getByText("Garanta Finanzgruppe AG")).toBeInTheDocument();
  expect(screen.getByText("Agent-ready scaffold")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Admin portal" })).toBeInTheDocument();
});
