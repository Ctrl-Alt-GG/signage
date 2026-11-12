import { afterEach, describe, expect, it, vi } from "vitest";

import { buildOf, reloadWhenDue, reloadWhenServed } from "./reload";

const page = (script: string) =>
  `<html><head><script type="module" src="/assets/${script}"></script></head>` +
  `<body><div id="root"></div></body></html>`;
const HOUR = 60 * 60 * 1000;

function serve(answer: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(answer));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("buildOf", () => {
  it("names the scripts a page loads", () => {
    expect(buildOf(page("index-AbC123.js"))).toBe("/assets/index-AbC123.js");
    expect(buildOf(page("index-AbC123.js"))).not.toBe(buildOf(page("index-XyZ789.js")));
  });

  it("is empty for the development server, which has no build", () => {
    expect(buildOf('<script type="module" src="/src/main.tsx"></script>')).toBe("");
  });
});

describe("reloading a kiosk", () => {
  it("does not reload into an error page while the server is away", async () => {
    const reload = vi.fn();
    serve(() => Promise.reject(new TypeError("Failed to fetch")));
    expect(await reloadWhenServed(reload)).toBe(false);
    serve(() => Promise.resolve(new Response("Bad Gateway", { status: 502 })));
    expect(await reloadWhenServed(reload)).toBe(false);
    // An answer that is not the display, such as a proxy's maintenance page.
    serve(() => Promise.resolve(new Response("<html>We are back soon</html>")));
    expect(await reloadWhenServed(reload)).toBe(false);
    expect(reload).not.toHaveBeenCalled();

    serve(() => Promise.resolve(new Response(page("index-AbC123.js"))));
    expect(await reloadWhenServed(reload)).toBe(true);
    expect(reload).toHaveBeenCalledOnce();
  });

  it("picks up a new release within minutes, and otherwise waits for its age", async () => {
    const reload = vi.fn();
    const loaded = page("index-AbC123.js");
    serve(() => Promise.resolve(new Response(loaded)));
    expect(await reloadWhenDue(HOUR, loaded, reload)).toBe(false);
    expect(await reloadWhenDue(7 * HOUR, loaded, reload)).toBe(true);

    serve(() => Promise.resolve(new Response(page("index-XyZ789.js"))));
    expect(await reloadWhenDue(HOUR, loaded, reload)).toBe(true);
    expect(reload).toHaveBeenCalledTimes(2);
  });

  it("leaves an old page running while the server cannot serve a new one", async () => {
    const reload = vi.fn();
    serve(() => Promise.reject(new TypeError("Failed to fetch")));
    expect(await reloadWhenDue(7 * HOUR, page("index-AbC123.js"), reload)).toBe(false);
    expect(reload).not.toHaveBeenCalled();
  });
});
