import "@testing-library/jest-dom/vitest";

// jsdom lacks ResizeObserver (React Flow and Recharts need it) and scrollIntoView.
if (typeof window !== "undefined") {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  window.ResizeObserver = ResizeObserverStub;
  Element.prototype.scrollIntoView = () => undefined;
}

// Zero-network guard: any test that reaches for the real network fails loudly. Tests that need
// responses pass their own `fetch` (see api/__tests__/helpers) or a stubbed `Api`.
import { beforeEach, vi } from "vitest";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      throw new Error("Unexpected network call in test");
    }),
  );
});
