#!/usr/bin/env python3
"""
Import an external markdown document into the blog.

The blog renders markdown with react-markdown + rehype-(slug|katex) and does
NOT ship rehype-raw, so raw HTML in the source document is escaped and shown
as literal text. This script converts the common "centered image" pattern

    <div align="center">
      <img src="foo.png" alt="描述" width="520">
    </div>

(also `<p align="center">`, `<center>`, or a bare `<img>`) into a plain
markdown image, and copies/scales the referenced images into the site's image
directory. The `width` attribute is baked into the file by resizing the
bitmap, because markdown has no way to express display width.

Usage
-----
    python3 build/import_doc.py \
        --md /path/to/doc.md \
        --slug my-post \
        --title "我的文章" \
        --date 2026-05-06 \
        --category 算子优化 \
        --tags "标签1,标签2" \
        --excerpt "一句话摘要"

    # then regenerate the site
    python3 build/build.py /my-repo/

Options
-------
--image-dir   sub-directory under images/ to copy images into
              (default: derived from the markdown file name)
--keep-toc    keep a leading "## 目录" section (dropped by default, since the
              blog generates its own table of contents)
--dry-run     show what would happen without writing anything
"""
import argparse
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(ROOT, "content", "articles.json")
IMAGES_ROOT = os.path.join(ROOT, "images")

# <div|p|span align="center"><img ...></div|p|span>  (whitespace tolerant)
IMG_BLOCK = re.compile(
    r'<(div|p|span)\b[^>]*\balign=["\']center["\'][^>]*>\s*(<img\b[^>]*>)\s*</\1>',
    re.IGNORECASE,
)
# <center><img ...></center>
IMG_CENTER = re.compile(
    r'<center>\s*(<img\b[^>]*>)\s*</center>',
    re.IGNORECASE,
)
# any remaining bare <img ...>
IMG_TAG = re.compile(r'<img\b[^>]*>', re.IGNORECASE)
ATTR = re.compile(r'([a-zA-Z-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')

H1 = re.compile(r'^#\s+.*$', re.MULTILINE)


def parse_attrs(tag):
    """Parse attributes from an HTML tag, tolerating single or double quotes."""
    out = {}
    for m in ATTR.finditer(tag):
        # findall() reports non-participating groups as "" rather than None,
        # which cannot be told apart from a genuinely empty value, so use
        # finditer() and .group() here.
        val = m.group(2) if m.group(2) is not None else m.group(3)
        out[m.group(1).lower()] = val
    return out


def drop_leading_h1(text):
    """Drop the first '# ...' line (the blog renders the title itself)."""
    m = H1.search(text)
    if not m:
        return text, None
    return (text[:m.start()] + text[m.end():]).lstrip("\n"), m.group(0).strip()


def drop_toc(text):
    """Drop a '## 目录' section, up to the next '## ' heading."""
    m = re.search(r'^##\s+目录\s*$', text, re.MULTILINE)
    if not m:
        return text, False
    nxt = re.search(r'^##\s+', text[m.end():], re.MULTILINE)
    end = m.end() + nxt.start() if nxt else len(text)
    return (text[:m.start()] + text[end:]).lstrip("\n"), True


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    import struct
    return struct.unpack(">II", head[16:24])


def convert_images(text, src_dir, out_dir, url_prefix, dry_run=False):
    """Rewrite centered <img> blocks into markdown images.

    Handles the three shapes seen in source documents:
        <div|p|span align="center"><img ...></div|p|span>
        <center><img ...></center>
        <img ...>                      (bare, converted with a warning)

    Returns (new_text, stats) where stats is a list of dicts describing each
    image: name, orig size, target width, whether it will be resized.
    """
    stats = []
    warned = set()
    if not dry_run:
        os.makedirs(out_dir, exist_ok=True)

    def emit(tag, wrapped):
        a = parse_attrs(tag)
        src = a.get("src", "")
        alt = a.get("alt", "")
        width = a.get("width", "")

        # source paths may carry a sub-directory (e.g. charts/fig1.png); we
        # flatten to the basename since the images land in one target dir
        name = os.path.basename(src)
        src_path = os.path.join(src_dir, src)
        dst_path = os.path.join(out_dir, name)

        if not os.path.exists(src_path):
            if src not in warned:
                warned.add(src)
                print("  !! 源图片缺失: %s" % src_path)
            return tag

        size = png_size(src_path)
        target = int(width) if width.isdigit() else None
        will_resize = bool(target and size and target < size[0])

        if not dry_run:
            if will_resize:
                from PIL import Image
                im = Image.open(src_path)
                h = round(im.height * target / im.width)
                im = im.convert("RGBA").resize((target, h), Image.LANCZOS)
                im.save(dst_path)
            else:
                shutil.copy2(src_path, dst_path)

        stats.append({
            "name": name,
            "orig": "%dx%d" % size if size else "?",
            "width": target,
            "resized": will_resize,
            "wrapped": wrapped,
        })
        return "![%s](%s%s)" % (alt, url_prefix, name)

    text = IMG_BLOCK.sub(lambda m: emit(m.group(2), True), text)
    text = IMG_CENTER.sub(lambda m: emit(m.group(1), True), text)
    text = IMG_TAG.sub(lambda m: emit(m.group(0), False), text)
    return text, stats


def main():
    ap = argparse.ArgumentParser(description="Import a markdown doc into the blog")
    ap.add_argument("--md", required=True, help="源 markdown 文件")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--category", required=True)
    ap.add_argument("--tags", required=True, help="逗号分隔（支持中英文逗号）")
    ap.add_argument("--excerpt", required=True)
    ap.add_argument("--image-dir", default=None,
                    help="images/ 下的子目录名，默认取 markdown 文件名")
    ap.add_argument("--title-from", default=None,
                    help="覆盖 title 的正文片段（默认删除首个 H1）")
    ap.add_argument("--keep-toc", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        sys.exit("ERROR: --date 必须是 YYYY-MM-DD")

    src_dir = os.path.dirname(os.path.abspath(args.md))
    text = open(args.md, encoding="utf-8").read()
    image_dir = args.image_dir or os.path.splitext(os.path.basename(args.md))[0]
    out_dir = os.path.join(IMAGES_ROOT, image_dir)
    url_prefix = "/images/%s/" % image_dir

    print("源文件   : %s (%d bytes)" % (args.md, len(text)))

    text, h1 = drop_leading_h1(text)
    if h1:
        print("删除 H1  : %s" % h1)
    if args.title_from:
        text = text.replace(args.title_from, "", 1).lstrip("\n")

    if not args.keep_toc:
        text, dropped = drop_toc(text)
        print("目录段   : %s" % ("已移除" if dropped else "未发现"))

    text, stats = convert_images(text, src_dir, out_dir, url_prefix, args.dry_run)

    print("图片     : %d 张 -> %s" % (len(stats), out_dir))
    for s in stats:
        act = "缩放到" if s["resized"] else "保持原尺寸"
        print("   %-24s %-11s %s%s" % (
            s["name"], s["orig"], act,
            (" %dpx" % s["width"]) if s["width"] else ""))

    bare = [s["name"] for s in stats if not s["wrapped"]]
    if bare:
        print("  !! %d 张图未包裹在居中标签内（已转换，靠 CSS 居中）: %s"
              % (len(bare), bare))

    # 转换之后正文里不该再有任何 HTML 标签
    remaining = sorted({t[1] for t in
                        re.findall(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>', text)})
    if remaining:
        print("  !! 正文仍含 HTML 标签（博客会当作纯文本显示）: %s" % remaining)

    entry = {
        "slug": args.slug,
        "title": args.title,
        "date": args.date,
        "category": args.category,
        "tags": [t.strip() for t in re.split(r"[,，]", args.tags) if t.strip()],
        "excerpt": args.excerpt,
        "content": text,
    }

    if args.dry_run:
        print("\n[dry-run] 未写入。文章正文预览:")
        print("-" * 60)
        print(text[:600])
        return

    arts = json.load(open(ARTICLES, encoding="utf-8"))
    for i, a in enumerate(arts):
        if a["slug"] == args.slug:
            arts[i] = entry
            print("\n已替换 articles.json 中已有的 %r" % args.slug)
            break
    else:
        arts.append(entry)
        print("\n已追加到 articles.json: %s" % args.slug)

    with open(ARTICLES, "w", encoding="utf-8") as f:
        json.dump(arts, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("正文长度 : %d 字符" % len(text))
    print("\n下一步: python3 build/build.py /<repo>/")


if __name__ == "__main__":
    main()
