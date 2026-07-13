import "@testing-library/jest-dom/vitest"

// jsdom has no ResizeObserver; recharts' ResponsiveContainer (rendered by the
// review page's MomentumGauge) requires one. A no-op stub is enough — layout
// never actually resizes under test.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
}
