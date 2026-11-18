#!/usr/bin/env python3
"""Check the two images served together, as nginx and Django answer on one origin: the
display and its assets, the API, the admin and its static files, and the headers each of
them is meant to carry.

Usage (with the stack of compose.local.yaml running and an admin user created):
    uv run python scripts/smoke.py --base-url http://127.0.0.1:8080 \\
        --username smoke --password <password>

Exits non-zero and names every check that failed.
"""

from __future__ import annotations

import argparse
import re
import sys

import httpx


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def expect(self, condition: bool, what: str) -> None:
        if not condition:
            self.failures.append(what)


def check_display(client: httpx.Client, checks: Checks) -> None:
    for path in ("/", "/display/main/"):
        page = client.get(path)
        policy = page.headers.get("content-security-policy", "")
        checks.expect(page.status_code == 200, f"{path}: answered {page.status_code}")
        checks.expect('id="root"' in page.text, f"{path}: is not the display")
        checks.expect("default-src 'self'" in policy, f"{path}: no content security policy")
        checks.expect("frame-ancestors 'self'" in policy, f"{path}: may be framed by others")
        checks.expect(page.headers.get("cache-control") == "no-cache", f"{path}: is cached")
    scripts = re.findall(r"/assets/[\w.-]+\.js", client.get("/").text)
    checks.expect(bool(scripts), "/: names no script")
    for script in scripts[:1]:
        asset = client.get(script)
        checks.expect(asset.status_code == 200, f"{script}: answered {asset.status_code}")
        checks.expect("immutable" in asset.headers.get("cache-control", ""), f"{script}: not kept")


def check_api(client: httpx.Client, checks: Checks) -> None:
    screens = client.get("/api/v1/screens/")
    checks.expect(screens.status_code == 200, f"screens: answered {screens.status_code}")
    slugs = [screen["slug"] for screen in screens.json()] if screens.status_code == 200 else []
    checks.expect("main" in slugs, "screens: no main screen")

    bundle = client.get("/api/v1/screens/main/bundle/")
    checks.expect(bundle.status_code == 200, f"bundle: answered {bundle.status_code}")
    checks.expect(bundle.headers.get("cache-control") == "no-store", "bundle: may be cached")
    if bundle.status_code == 200:
        checks.expect(bool(bundle.json()["passes"]), "bundle: no slides")

    # Uploaded artwork is served from this origin, so it must not run as a document here.
    svg = client.get("/api/v1/display/background.svg")
    checks.expect(svg.status_code == 200, f"background: answered {svg.status_code}")
    checks.expect(
        svg.headers.get("content-type", "").startswith("image/svg+xml"), "background: not SVG"
    )
    checks.expect(
        "sandbox" in svg.headers.get("content-security-policy", ""), "background: not inert"
    )
    checks.expect(svg.headers.get("x-content-type-options") == "nosniff", "background: sniffed")

    health = client.get("/health/", params={"format": "json"})
    checks.expect(health.status_code == 200, f"health: answered {health.status_code}")


def check_admin(client: httpx.Client, checks: Checks, username: str, password: str) -> None:
    redirect = client.get("/admin")
    checks.expect(
        redirect.status_code == 301 and redirect.headers.get("location") == "/admin/",
        "/admin: does not lead to /admin/",
    )
    style = client.get("/static/admin/css/base.css")
    checks.expect(style.status_code == 200, f"admin styles: answered {style.status_code}")
    checks.expect(
        style.headers.get("content-type", "").startswith("text/css"), "admin styles: not CSS"
    )

    # Signing in checks what the proxy passes on: Django compares the Origin of the post
    # with the host it was asked for, and sets its cookies for this origin.
    form = client.get("/admin/login/")
    checks.expect(form.status_code == 200, f"login: answered {form.status_code}")
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', form.text)
    checks.expect(token is not None, "login: no form")
    if token is None:
        return
    signed_in = client.post(
        "/admin/login/",
        data={
            "csrfmiddlewaretoken": token[1],
            "username": username,
            "password": password,
            "next": "/admin/",
        },
        headers={
            "Origin": str(client.base_url).rstrip("/"),
            "Referer": f"{client.base_url}admin/login/",
        },
    )
    checks.expect(
        signed_in.status_code == 302 and signed_in.headers.get("location") == "/admin/",
        f"login: answered {signed_in.status_code} instead of signing in",
    )
    index = client.get("/admin/")
    checks.expect(index.status_code == 200, f"admin: answered {index.status_code} once signed in")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    checks = Checks()
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        check_display(client, checks)
        check_api(client, checks)
        check_admin(client, checks, args.username, args.password)
    for failure in checks.failures:
        print("FAIL", failure, file=sys.stderr)
    print(
        f"{len(checks.failures)} of the checks failed" if checks.failures else "all checks passed"
    )
    return 1 if checks.failures else 0


if __name__ == "__main__":
    sys.exit(main())
