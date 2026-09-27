#!/usr/bin/env python3
"""
Rebuild the static blog for GitHub Pages from the pristine mirrored sources
in build/origin/.

Usage:
    python3 build/build.py                 # auto base = "/"  (user page / root)
    python3 build/build.py /my-repo/       # project page  -> /my-repo/

Data source
-----------
`content/articles.json` is the single source of truth for the post list.
It is parsed and injected into the JS bundle, replacing the original inline
array. To add or edit a post, edit that file (image paths stay canonical,
i.e. "/images/..." without the deploy base) and re-run this script.

What it patches
---------------
index.html / 404.html
  * drops the Qoder watermark <script> block
  * rewrites the JS + CSS asset hrefs to "<base>assets/..."

assets/index-*.js
  * replaces the inline post array with content/articles.json
  * injects react-router `basename="<base without trailing slash>"`
    so client side routes resolve under a project page sub-path
  * rewrites canonical image urls "/images/..." to "<base>images/..."

assets/index-*.css
  * makes the KaTeX font urls relative, so they work under any base path

404.html is an exact copy of index.html: GitHub Pages serves it for any
unknown path, which lets the SPA handle deep links like /repo/article/slug.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGIN = os.path.join(ROOT, "build", "origin")
ARTICLES = os.path.join(ROOT, "content", "articles.json")

JS_NAME = "index-C0lEgf8Y.js"
CSS_NAME = "index-K_R0l0Xa.css"

# Appended to the generated stylesheet. The source documents wrap figures in
# `<div align="center">`, which markdown cannot express, so we centre markdown
# images instead. Posts whose images are wider than the text column are
# unaffected (max-width:100% already stretches them edge to edge).
CSS_EXTRA = """
/* markdown 图片居中（原文档使用 <div align="center"> 包裹配图） */
.prose img{margin-left:auto;margin-right:auto}
"""

# boundaries of the inline post array inside the origin bundle
ARR_START = "Hr=["
ARR_END = "}];function Ur("
CAT_START = "Vr=["  # home page category filter buttons
BASE_SENTINEL = "(0,A.jsx)(Hn,{children:"  # react-router <Router> mount point


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
    return html[:start] + html[end:].lstrip("\n")


def js_literal(obj) -> str:
    """Serialise to a valid JS literal (JSON is a subset of JS)."""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    # U+2028 / U+2029 are legal in JSON but were illegal in JS string
    # literals before ES2019; escape them so every engine is happy.
    return s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def load_articles():
    with open(ARTICLES, encoding="utf-8") as f:
        arts = json.load(f)
    if not isinstance(arts, list) or not arts:
        raise SystemExit("ERROR: %s must hold a non-empty JSON array" % ARTICLES)
    required = {"slug", "title", "date", "category", "tags", "excerpt", "content"}
    seen = set()
    for a in arts:
        missing = required - set(a)
        if missing:
            raise SystemExit("ERROR: post %r missing fields: %s"
                             % (a.get("slug", "?"), sorted(missing)))
        if a["slug"] in seen:
            raise SystemExit("ERROR: duplicate slug %r" % a["slug"])
        seen.add(a["slug"])
    return arts


def replace_articles(js: str, articles) -> str:
    start = js.find(ARR_START)
    end = js.find(ARR_END)
    if start == -1 or end == -1:
        raise SystemExit("ERROR: could not locate the inline post array")
    end += 2  # keep the trailing "}]" (end of array + closing brace)

    # category filter buttons live just before the post array, as
    # `Vr=[...],Hr=[...]`. Derive them from the posts, keeping the order in
    # which each category first appears in articles.json.
    cats = []
    for a in articles:
        if a["category"] not in cats:
            cats.append(a["category"])

    cat_start = js.rfind(CAT_START, 0, start)
    if cat_start == -1:
        raise SystemExit("ERROR: could not locate the category list")

    return (js[:cat_start]
            + "Vr=" + js_literal(cats)
            + ",Hr=" + js_literal(articles)
            + js[end:])


def build(base: str) -> None:
    base = norm_base(base)
    basename = base.rstrip("/") or "/"
    articles = load_articles()

    # ---------- html ----------
    html = open(os.path.join(ORIGIN, "index.html"), encoding="utf-8").read()
    html = strip_watermark(html)
    html = html.replace("/assets/" + JS_NAME, base + "assets/" + JS_NAME)
    html = html.replace("/assets/" + CSS_NAME, base + "assets/" + CSS_NAME)

    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(ROOT, "404.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # ---------- css (font urls -> relative, images centred) ----------
    css = open(os.path.join(ORIGIN, "app.css"), encoding="utf-8").read()
    css = css.replace("url(/assets/", "url(./")
    css += CSS_EXTRA
    with open(os.path.join(ROOT, "assets", CSS_NAME), "w", encoding="utf-8") as f:
        f.write(css)

    # ---------- js ----------
    js = open(os.path.join(ORIGIN, "app.js"), encoding="utf-8").read()

    js = replace_articles(js, articles)

    before = js
    js = js.replace(
        BASE_SENTINEL,
        '(0,A.jsx)(Hn,{basename:"%s",children:' % basename,
        1,
    )
    if js == before:
        raise SystemExit("ERROR: router basename patch did not apply")

    before = js
    # canonical "/images/..." in articles.json -> "/<base>/images/..."
    js = js.replace("/images/", base + "images/")
    if js == before and any("/images/" in a["content"] for a in articles):
        raise SystemExit("ERROR: image path patch did not apply")

    with open(os.path.join(ROOT, "assets", JS_NAME), "w", encoding="utf-8") as f:
        f.write(js)

    # ---------- misc ----------
    open(os.path.join(ROOT, ".nojekyll"), "w").close()

    print("built base=%s basename=%s posts=%d" % (base, basename, len(articles)))
    for a in sorted(articles, key=lambda x: x["date"], reverse=True):
        print("  %s  %-8s %s" % (a["date"], a["category"], a["title"]))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/")
