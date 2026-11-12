import "@testing-library/jest-dom/vitest";

/* jsdom has no layout, so it lacks the observers the carousel watches its size with.
   Nothing in the tests depends on a size; these let the carousel start. They are plain
   assignments, not stubs, so a test that removes its own stubs keeps them. */
class Observer {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

Object.assign(globalThis, {
  ResizeObserver: Observer,
  IntersectionObserver: Observer,
  matchMedia: (query: string): Partial<MediaQueryList> => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  }),
});
