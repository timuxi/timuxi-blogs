#!/usr/bin/env python3
"""本地预览：模拟 GitHub Pages 的静态托管行为。

普通 `python3 -m http.server` 有两个问题，会让这个博客看起来"坏掉"：
  1. 不知道站点是部署在子路径（如 /timuxi-blogs/）下的，访问根路径会 404
  2. 路径未命中时直接返回错误页，而 GitHub Pages 会返回 404.html，
     SPA 才能接管 /article/<slug> 这类深链接

本脚本补齐这两点：

    python3 tools/preview.py                 # 自动识别 base 路径，端口 8099
    python3 tools/preview.py -p 9000         # 换端口
    python3 tools/preview.py --base /        # 手动指定部署在域名根目录

base 路径默认从 index.html 里引用的 JS 资源推断，与 build/build.py 保持一致。
"""
import argparse
import http.server
import io
import os
import re
import socketserver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def detect_base():
    """从 index.html 里解析出部署用的 base 路径，例如 /timuxi-blogs/。"""
    index = os.path.join(ROOT, "index.html")
    try:
        html = open(index, encoding="utf-8").read()
    except OSError:
        return "/"
    m = re.search(r'src="(/[^"]*?)assets/[^"]+"', html)
    return m.group(1) if m else "/"


def norm_base(raw):
    raw = (raw or "/").strip()
    if not raw.startswith("/"):
        raw = "/" + raw
    if not raw.endswith("/"):
        raw += "/"
    return raw


def make_handler(base):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=ROOT, **kw)

        def translate_path(self, path):
            # 剥掉 base 前缀，让 /<base>/foo 映射到 <project>/foo
            if base != "/" and path.startswith(base):
                path = "/" + path[len(base):]
            return super().translate_path(path)

        def send_head(self):
            target = self.translate_path(self.path)
            if os.path.isdir(target):
                target = os.path.join(target, "index.html")
            if os.path.exists(target):
                return super().send_head()
            # GitHub Pages 行为：未命中 -> 404.html（状态码仍是 404）
            page = os.path.join(ROOT, "404.html")
            if os.path.exists(page):
                body = open(page, "rb").read()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return io.BytesIO(body)
            self.send_error(404)

        def log_message(self, fmt, *args):
            print("  %s" % (fmt % args), flush=True)

    return Handler


def main():
    ap = argparse.ArgumentParser(description="本地预览（模拟 GitHub Pages）")
    ap.add_argument("-p", "--port", type=int, default=8099)
    ap.add_argument("--base", default=None,
                    help="部署用的 base 路径，默认从 index.html 自动推断")
    ap.add_argument("--host", default="127.0.0.1",
                    help="监听地址，默认 127.0.0.1")
    args = ap.parse_args()

    base = norm_base(args.base if args.base is not None else detect_base())
    url = "http://%s:%d%s" % (args.host, args.port, base)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, args.port), make_handler(base)) as httpd:
        print("站点根目录: %s" % ROOT)
        print("base 路径  : %s%s" % (base, "  (自动推断)" if args.base is None else ""))
        print("访问地址   : %s" % url)
        print("深链接示例 : %sarticle/deepseek-v4-attention" % url)
        print("Ctrl-C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
