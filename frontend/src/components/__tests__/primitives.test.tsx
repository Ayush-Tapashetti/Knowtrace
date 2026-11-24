// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError, NetworkError } from "../../api/errors";
import { Badge } from "../ui/Badge";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { Field, Input } from "../ui/Field";
import {
  EmptyState,
  ErrorBoundary,
  ErrorState,
  LoadingState,
  errorTitle,
} from "../ui/states";

describe("Button", () => {
  it("pending disables the button, marks it busy and keeps its label", async () => {
    const onClick = vi.fn();
    render(
      <Button pending onClick={onClick}>
        Save answer
      </Button>,
    );
    const b = screen.getByRole("button", { name: "Save answer" });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
    await userEvent.setup().click(b);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("is a non-submitting button by default", () => {
    render(<Button>Go</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });
});

describe("Field", () => {
  it("connects label, hint and error to the control", () => {
    render(
      <Field
        label="Your answer"
        hint="Use a fraction such as 3/4"
        error="Enter a number"
        required
      >
        {(c) => <Input {...c} />}
      </Field>,
    );
    const input = screen.getByLabelText(/Your answer/);
    expect(input).toBeInvalid();
    expect(input).toHaveAccessibleDescription(
      "Use a fraction such as 3/4 Enter a number",
    );
    expect(screen.getByText("(required)")).toBeInTheDocument();
  });

  it("has no error attributes when valid", () => {
    render(<Field label="Name">{(c) => <Input {...c} />}</Field>);
    const input = screen.getByLabelText("Name");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).not.toHaveAttribute("aria-describedby");
  });
});

describe("Banner and Badge", () => {
  it("announces errors as alerts and everything else as status", () => {
    render(
      <>
        <Banner tone="error" title="Broke" />
        <Banner tone="info" title="FYI" />
      </>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Broke");
    expect(screen.getByRole("status")).toHaveTextContent("FYI");
  });

  it("badges always carry text", () => {
    render(<Badge tone="gap">Missing concept</Badge>);
    expect(screen.getByText("Missing concept")).toBeInTheDocument();
  });
});

describe("state primitives", () => {
  it("LoadingState is announced once and busy", () => {
    render(<LoadingState label="Loading the map" />);
    const s = screen.getByRole("status");
    expect(s).toHaveAttribute("aria-busy", "true");
    expect(s).toHaveTextContent("Loading the map");
  });

  it("EmptyState offers a next action", () => {
    render(
      <EmptyState
        title="No attempts yet"
        description="Answer a question to start."
        action={<button>Start</button>}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "No attempts yet" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
  });

  it("ErrorState shows the server's message and retries on request", async () => {
    const onRetry = vi.fn();
    const err = new ApiError({
      status: 429,
      code: "rate_limited",
      message: "Too many requests; slow down.",
      retryAfterSeconds: 7,
    });
    render(<ErrorState error={err} onRetry={onRetry} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Too many requests");
    expect(alert).toHaveTextContent("Try again in 7 seconds.");
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("titles distinguish 'server said no' from 'server unreachable'", () => {
    expect(errorTitle(new NetworkError("unreachable"))).toBe(
      "Can't reach the server",
    );
    expect(errorTitle(new NetworkError("timeout"))).toBe(
      "The server is too slow",
    );
    expect(
      errorTitle(new ApiError({ status: 409, code: "conflict", message: "" })),
    ).toBe("That isn't possible right now");
    expect(
      errorTitle(new ApiError({ status: 404, code: "not_found", message: "" })),
    ).toBe("Not found");
    expect(errorTitle(new Error("bug"))).toBe("Something went wrong");
  });

  it("ErrorBoundary replaces a crashing page with a recovery screen", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const Boom = (): never => {
      throw new Error("kaboom");
    };
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This page hit a problem",
    );
    expect(screen.queryByText("kaboom")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reload page" }),
    ).toBeInTheDocument();
  });
});
