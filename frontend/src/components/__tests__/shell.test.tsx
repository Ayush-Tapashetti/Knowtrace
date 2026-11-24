// @vitest-environment jsdom
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, NetworkError } from "../../api/errors";
import { quietLearner, stubApi } from "../../api/__tests__/helpers";
import { AppRoutes } from "../../app/App";
import { describeBackend } from "../layout/backendState";
import { readyStatus, renderApp } from "../../test/render";

const ready = () =>
  stubApi({ ...quietLearner, getStatus: () => Promise.resolve(readyStatus()) });

afterEach(() => {
  vi.restoreAllMocks();
});

describe("app shell", () => {
  it("renders the landmarks, the skip link and the disclaimer on every page", async () => {
    renderApp(<AppRoutes client={ready()} />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    const footer = screen.getByRole("contentinfo");
    expect(
      within(footer).getByText(/never a real name or roll number/i),
    ).toBeInTheDocument();
    expect(
      within(footer).getByText(/no AI model involved/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /skip to main content/i }),
    ).toHaveAttribute("href", "#main");
    expect(
      screen.getByRole("heading", { level: 1, name: "Practice" }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Server ready")).toBeInTheDocument();
    });
  });

  it("has one h1 per page and marks the current page in both navs", () => {
    renderApp(<AppRoutes client={ready()} />, "/map");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(
      screen.getByRole("heading", { level: 1, name: "Knowledge map" }),
    ).toBeInTheDocument();
    const current = screen.getAllByRole("link", { current: "page" });
    expect(current.map((l) => l.textContent)).toEqual([
      "Knowledge map",
      "Knowledge map",
    ]); // top nav + tab bar
    expect(document.title).toBe("Knowledge map | KnowTrace");
  });

  it("navigates with the keyboard", async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes client={ready()} />);
    const nav = screen.getAllByRole("navigation", { name: "Primary" })[0];
    if (!nav) throw new Error("no nav");
    await user.click(within(nav).getByRole("link", { name: "Evaluation" }));
    expect(
      screen.getByRole("heading", { level: 1, name: "Evaluation" }),
    ).toBeInTheDocument();
  });

  it("shows a 404 page with a way home for unknown addresses", () => {
    renderApp(<AppRoutes client={ready()} />, "/nope/at/all");
    expect(
      screen.getByRole("heading", { level: 1, name: "Page not found" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Go to Practice" }),
    ).toHaveAttribute("href", "/");
  });
});

describe("status banners", () => {
  it("is silent when the server is ready in deterministic mode", async () => {
    renderApp(<AppRoutes client={ready()} />);
    await waitFor(() => {
      expect(screen.getByText("Server ready")).toBeInTheDocument();
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("announces an unreachable server, and clears once Try again succeeds", async () => {
    const user = userEvent.setup();
    const getStatus = vi
      .fn()
      .mockRejectedValueOnce(new NetworkError("unreachable"))
      .mockResolvedValue(readyStatus());
    renderApp(<AppRoutes client={stubApi({ ...quietLearner, getStatus })} />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Can't reach the server");
    expect(screen.getByText("Server unreachable")).toBeInTheDocument();
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
    expect(getStatus).toHaveBeenCalledTimes(2);
  });

  it("explains a server that is up but has no curriculum", async () => {
    const getStatus = vi
      .fn()
      .mockRejectedValue(
        new ApiError({ status: 503, code: "not_ready", message: "x" }),
      );
    renderApp(<AppRoutes client={stubApi({ ...quietLearner, getStatus })} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /no curriculum loaded/i,
    );
  });

  it("reports a degraded /status (curriculum missing) the same way", async () => {
    const s = readyStatus({
      status: "degraded",
      curriculum_loaded: false,
      curriculum_hash: null,
    });
    renderApp(
      <AppRoutes
        client={stubApi({
          ...quietLearner,
          getStatus: () => Promise.resolve(s),
        })}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /no curriculum loaded/i,
    );
  });

  it("warns when the browser goes offline", async () => {
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    renderApp(<AppRoutes client={ready()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You're offline",
    );
    expect(
      screen.queryByRole("button", { name: "Try again" }),
    ).not.toBeInTheDocument();
  });

  it("tells learners when the optional model is on, and lets them dismiss that note only", async () => {
    const user = userEvent.setup();
    const s = readyStatus({
      llm_mode: "model",
      fallback_active: false,
      llm_model: "m",
    });
    renderApp(
      <AppRoutes
        client={stubApi({
          ...quietLearner,
          getStatus: () => Promise.resolve(s),
        })}
      />,
    );
    const note = (await screen.findByText("AI rewording is on")).closest(
      '[role="status"]',
    );
    expect(note).toBeInTheDocument();
    expect(
      screen.getByText(
        /Lesson wording may be rewritten by a language model\. The diagnosis/,
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("AI rewording is on")).not.toBeInTheDocument();
  });
});

describe("describeBackend", () => {
  const base = { online: true, isPending: false, data: undefined, error: null };
  it.each([
    [{ ...base, isPending: true }, "checking", false],
    [{ ...base, data: readyStatus() }, "ready", false],
    [{ ...base, online: false }, "offline", true],
    [{ ...base, error: new NetworkError("timeout") }, "unreachable", true],
    [
      {
        ...base,
        error: new ApiError({
          status: 500,
          code: "internal_error",
          message: "boom",
        }),
      },
      "error",
      true,
    ],
    [
      { ...base, data: readyStatus({ database_ok: false }) },
      "no-database",
      true,
    ],
  ])("%#", (input, kind, hasBanner) => {
    const s = describeBackend(input);
    expect(s.kind).toBe(kind);
    expect(s.banner !== null).toBe(hasBanner);
  });
});
