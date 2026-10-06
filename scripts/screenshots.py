#!/usr/bin/env python3
"""Screenshot every slide in both languages and check the safe-area rules.

Usage (with the Django server running and the frontend built):
    uv run python scripts/screenshots.py --base-url http://localhost:4173

Writes screenshots/<slide>-<lang>.png (git-ignored) and exits non-zero when any visible text
lies outside the content-safe area or a slide overflows its box.
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import yaml
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SAFE = {"left": 96, "top": 204, "right": 1824, "bottom": 768}
TOLERANCE = 2

CHECK_JS = """
({safe, tolerance}) => {
  const stage = document.querySelector('[data-stage]');
  const area = document.querySelector('[data-safe-area]');
  if (!stage || !area) return {errors: ['stage or safe area missing']};
  const stageRect = stage.getBoundingClientRect();
  const errors = [];
  const clipsOverflow = (value) => ['hidden', 'clip', 'auto', 'scroll'].includes(value);
  // Visible text is what matters: intersect each text rect with every clipping ancestor.
  const clipRect = (node) => {
    let rect = {left: -Infinity, top: -Infinity, right: Infinity, bottom: Infinity};
    for (let el = node.parentElement; el && el !== area.parentElement; el = el.parentElement) {
      const style = getComputedStyle(el);
      const clamped = style.webkitLineClamp && style.webkitLineClamp !== 'none';
      if (clipsOverflow(style.overflowX) || clipsOverflow(style.overflowY) || clamped) {
        const box = el.getBoundingClientRect();
        rect = {
          left: Math.max(rect.left, box.left), top: Math.max(rect.top, box.top),
          right: Math.min(rect.right, box.right), bottom: Math.min(rect.bottom, box.bottom),
        };
      }
    }
    return rect;
  };
  const walker = document.createTreeWalker(area, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim()) continue;
    const clip = clipRect(node);
    const allowClip = Boolean(node.parentElement.closest('[data-allow-clip]'));
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const rect of range.getClientRects()) {
      const left = Math.max(rect.left, clip.left), top = Math.max(rect.top, clip.top);
      const right = Math.min(rect.right, clip.right), bottom = Math.min(rect.bottom, clip.bottom);
      const clippedBy = Math.max(clip.left - rect.left, clip.top - rect.top,
                                 rect.right - clip.right, rect.bottom - clip.bottom);
      if (clippedBy > tolerance && !allowClip) {
        const snippet = node.textContent.trim().slice(0, 40);
        errors.push(`text clipped by its box: "${snippet}" (${Math.round(clippedBy)}px)`);
      }
      if (right - left <= 1 || bottom - top <= 1) continue;
      const x1 = left - stageRect.left, y1 = top - stageRect.top;
      const x2 = right - stageRect.left, y2 = bottom - stageRect.top;
      if (x1 < safe.left - tolerance || y1 < safe.top - tolerance ||
          x2 > safe.right + tolerance || y2 > safe.bottom + tolerance) {
        const snippet = node.textContent.trim().slice(0, 40);
        const box = [x1, y1, x2, y2].map(Math.round).join(',');
        errors.push(`text outside safe area: "${snippet}" at ${box}`);
      }
    }
  }
  const slide = area.querySelector('[data-slide]');
  if (slide && slide.scrollHeight > slide.clientHeight + tolerance) {
    errors.push(`slide overflows by ${slide.scrollHeight - slide.clientHeight}px`);
  }
  return {errors};
}
"""


def chromium_path() -> str | None:
    candidates = glob.glob("/opt/pw-browsers/chromium*/chrome-linux*/chrome") + glob.glob(
        "/opt/pw-browsers/chromium"
    )
    return candidates[0] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:4173")
    parser.add_argument("--screen", default="main")
    parser.add_argument("--out", default=str(ROOT / "screenshots"))
    parser.add_argument(
        "--slides", nargs="*", help="Slide keys; default: all in content/slides.yaml"
    )
    parser.add_argument("--langs", default="hu,en")
    args = parser.parse_args()

    with (ROOT / "content" / "slides.yaml").open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    default_mode = document.get("defaults", {}).get("bilingual_mode", "alternate")
    modes = {s["id"]: s.get("bilingual_mode", default_mode) for s in document["slides"]}
    slides = args.slides or list(modes)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as playwright:
        launch_kwargs: dict = {}
        try:
            browser = playwright.chromium.launch(**launch_kwargs)
        except PlaywrightError:
            path = chromium_path()
            if not path:
                raise
            browser = playwright.chromium.launch(executable_path=path)
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        for slide in slides:
            # Stacked slides show both languages on one pass, so shoot that pass instead.
            langs = ["both"] if modes.get(slide) == "stacked" else args.langs.split(",")
            for lang in langs:
                url = f"{args.base_url}/display/{args.screen}/?preview={slide}&lang={lang}"
                page.goto(url, wait_until="networkidle")
                try:
                    page.wait_for_selector("[data-slide]", timeout=10_000)
                except PlaywrightError:
                    failures.append(f"{slide}/{lang}: no slide rendered")
                    page.screenshot(path=str(out / f"{slide}-{lang}.png"))
                    continue
                page.evaluate("document.fonts.ready")
                page.wait_for_timeout(600)
                page.screenshot(path=str(out / f"{slide}-{lang}.png"))
                result = page.evaluate(CHECK_JS, {"safe": SAFE, "tolerance": TOLERANCE})
                for error in result["errors"]:
                    failures.append(f"{slide}/{lang}: {error}")
        browser.close()

    print(f"screenshots for {len(slides)} slides written to {out}")
    for failure in failures:
        print("FAIL", failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
