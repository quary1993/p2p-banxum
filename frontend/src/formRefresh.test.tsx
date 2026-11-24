// IP of Webby-Soft SRL.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { useState } from "react";
import { expect, test, vi } from "vitest";
import { getV1AdminOpsTasksRetrieveResponseMock, getV1AuthMeRetrieveQueryKey } from "./api/generated/banxumApi";
import { server } from "./api/mocks/server";
import { preloadableArea } from "./lazyAreas";
import { renderLiveApp } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

test("a cold-loaded area keeps its form and focus on a parent render", async () => {
  function Form({ label }: { label: string }) {
    const [text, setText] = useState("");
    return <input aria-label={label} value={text} onChange={event => setText(event.target.value)} />;
  }
  const Area = preloadableArea(async () => Form);
  const view = render(<Area label="Name" />);
  const input = await screen.findByRole("textbox");
  input.focus();
  fireEvent.change(input, { target: { value: "draft" } });
  view.rerender(<Area label="New label" />);
  expect(screen.getByLabelText("New label")).toBe(input);
  expect(input).toHaveFocus();
  expect(input).toHaveValue("draft");
});

test("a background session check cannot clear admin sign-in fields", async () => {
  const { AdminApp } = await import("./adminConsole/AdminApp");
  let pending = false;
  let finish: (() => void) | undefined;
  server.use(http.get("*/api/v1/auth/me/", async () => {
    if (pending) await new Promise<void>(resolve => { finish = resolve; });
    return HttpResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }));
  const { queryClient } = renderLiveApp(AdminApp, "/admin");
  const password = await screen.findByPlaceholderText("Admin password");
  fireEvent.change(password, { target: { value: "unsent-test-input" } });
  pending = true;
  let request: Promise<void>;
  act(() => { request = queryClient.refetchQueries({ queryKey: getV1AuthMeRetrieveQueryKey() }); });
  await waitFor(() => expect(finish).toBeDefined());
  expect(screen.getByPlaceholderText("Admin password")).toBe(password);
  await act(async () => { finish?.(); await request; });
  expect(screen.getByPlaceholderText("Admin password")).toHaveValue("unsent-test-input");
});

test("refreshing an admin task updates untouched fields without replacing draft notes", async () => {
  const { TaskDetailDrawer } = await import("./adminConsole/AdminTasksPanel");
  const task = getV1AdminOpsTasksRetrieveResponseMock({ title: "Task", status: "open", task_type: "other", notes: "Original" });
  const client = new QueryClient();
  const props = { events: [], eventsLoading: false, onClose: vi.fn(), onPreviewUpdate: vi.fn(), refetchEvents: vi.fn(), refetchTasks: vi.fn() };
  const renderTask = (title: string) => <QueryClientProvider client={client}><TaskDetailDrawer {...props} task={{ ...task, title }} /></QueryClientProvider>;
  const view = render(renderTask("Task"));
  const notes = within(screen.getByRole("dialog")).getByLabelText("Notes");
  fireEvent.change(notes, { target: { value: "Still editing" } });
  view.rerender(renderTask("Updated by colleague"));
  expect(screen.getByLabelText("Title")).toHaveValue("Updated by colleague");
  expect(notes).toHaveValue("Still editing");
});
