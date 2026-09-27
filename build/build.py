#!/usr/bin/env python3
"""
Rebuild the static blog for GitHub Pages from the pristine mirrored sources
in build/origin/.

Usage:
    python3 build/build.py                 # auto base = "/"  (user page / root)
    python3 build/build.py /my-repo/       # project page  -> /my-repo/

What it patches
---------------
index.html / 404.html
  * drops the Qoder watermark <script> block
  * rewrites the JS + CSS asset hrefs to "<base>assets/..."

assets/index-*.js
  * injects react-router `basename="<base without trailing slash>"`
    so client side routes resolve under a project page sub-path
  * rewrites the inline markdown image urls "/images/..." to "<base>images/..."

assets/index-*.css
  * makes the KaTeX font urls relative, so they work under any base path

404.html is an exact copy of index.html: GitHub Pages serves it for any
unknown path, which lets the SPA handle deep links like /repo/article/slug.
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGIN = os.path.join(ROOT, "build", "origin")

JS_NAME = "index-C0lEgf8Y.js"
CSS_NAME = "index-K_R0l0Xa.css"


def norm_base(raw: str) -> str:
    """Return a base path that always starts and ends with '/'."""
    raw = (raw or "/").strip()
    if not raw:
        raw = "/"
    if not raw.startswith("/"):
        raw = "/" + raw
    if not raw.endswith("/"):
        raw += "/"
    return raw


def strip_watermark(html: str) -> str:
    start = html.find("<script data-qoder-watermark")
    if start == -1:
        return html
    end = html.find("</script>", start)
    if end == -1:
        return html
    end += len("</script>")
    # also swallow trailing whitespace/newline left behind
    return html[:start] + html[end:].lstrip("\n")


def build(base: str) -> None:
    base = norm_base(base)
    basename = base.rstrip("/") or "/"

    # ---------- html ----------
    html = open(os.path.join(ORIGIN, "index.html"), encoding="utf-8").read()
    html = strip_watermark(html)
    html = html.replace("/assets/" + JS_NAME, base + "assets/" + JS_NAME)
    html = html.replace("/assets/" + CSS_NAME, base + "assets/" + CSS_NAME)

    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(ROOT, "404.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # ---------- css (font urls -> relative) ----------
    css = open(os.path.join(ORIGIN, "app.css"), encoding="utf-8").read()
    css = css.replace("url(/assets/", "url(./")
    with open(os.path.join(ROOT, "assets", CSS_NAME), "w", encoding="utf-8") as f:
        f.write(css)

    # ---------- js ----------
    js = open(os.path.join(ORIGIN, "app.js"), encoding="utf-8").read()
    before = js

    js = js.replace(
        "(0,A.jsx)(Hn,{children:",
        '(0,A.jsx)(Hn,{basename:"%s",children:' % basename,
        1,
    )
    if js == before:
        raise SystemExit("ERROR: router basename patch did not apply")
    before = js

    js = js.replace("/images/dsv4/", base + "images/dsv4/")
    if js == before:
        raise SystemExit("ERROR: image path patch did not apply")

    with open(os.path.join(ROOT, "assets", JS_NAME), "w", encoding="utf-8") as f:
        f.write(js)

    # ---------- misc ----------
    open(os.path.join(ROOT, ".nojekyll"), "w").close()

    print("built base=%s basename=%s" % (base, basename))
    print("  index.html + 404.html")
    print("  assets/%s" % JS_NAME)
    print("  assets/%s" % CSS_NAME)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/")
