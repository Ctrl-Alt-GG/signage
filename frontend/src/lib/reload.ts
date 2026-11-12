import { useInterval } from "usehooks-ts";

/* A screen runs for days, so the page is loaded again now and then: a new release is
   picked up, and whatever a long session accumulates is dropped. A reload that lands
   while the server is restarting would leave the kiosk on the browser's own error page
   with nothing to bring it back, so the page is only reloaded once the server has just
   served it. */

const CHECK_EVERY_MS = 5 * 60 * 1000;
const RELOAD_AFTER_MS = 6 * 60 * 60 * 1000;

/** The scripts a page loads, which Vite names after their content: a new build has others. */
export function buildOf(html: string): string {
  const scripts = html.match(/\/assets\/[\w.-]+\.js/g) ?? [];
  return [...new Set(scripts)].sort().join(",");
}

/** The page as the server has it now, or null when it cannot be had. */
async function servedPage(): Promise<string | null> {
  try {
    const response = await fetch("/", { cache: "no-store" });
    const html = response.ok ? await response.text() : "";
    return html.includes('id="root"') ? html : null;
  } catch {
    return null;
  }
}

const reloadPage = () => window.location.reload();

/** Reload now if the server can serve the page, and say whether it could. */
export async function reloadWhenServed(reload: () => void = reloadPage): Promise<boolean> {
  if ((await servedPage()) === null) return false;
  reload();
  return true;
}

/** Reload if a new build is out, or if this page has been running for `ageMs` and that
    is long enough. Does nothing while the server does not answer. */
export async function reloadWhenDue(
  ageMs: number,
  loadedHtml: string,
  reload: () => void = reloadPage,
): Promise<boolean> {
  const html = await servedPage();
  if (html === null) return false;
  const loaded = buildOf(loadedHtml);
  const served = buildOf(html);
  const isNewBuild = loaded !== "" && served !== "" && served !== loaded;
  if (!isNewBuild && ageMs <= RELOAD_AFTER_MS) return false;
  reload();
  return true;
}

/** Keeps a long-running page fresh: reloads it when a new build is out, and every few
    hours regardless. */
export function useFreshPage(enabled: boolean): void {
  useInterval(
    () => void reloadWhenDue(performance.now(), document.documentElement.outerHTML),
    enabled ? CHECK_EVERY_MS : null,
  );
}
