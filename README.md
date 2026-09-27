# Timuxi 学习笔记

## 部署 (GitHub Pages)

仓库根目录本身就是可部署的站点，不需要构建步骤：

```
index.html          # 入口
404.html            # 与 index.html 相同，用于 SPA 深链接回退
.nojekyll           # 关闭 Jekyll 处理
assets/             # JS / CSS / KaTeX 字体
images/dsv4/        # 文章里的两张配图
content/articles.json  # 从 bundle 里抽出的文章数据（备查/后续编辑）
build/              # 原始构建产物 + 重新生成脚本
```

在 GitHub 仓库 `Settings → Pages` 里设置 **Source = Deploy from a branch**，
分支选 `main`，目录选 `/ (root)`，保存后即可访问
`https://<user>.github.io/<repo>/`。

`404.html` 的存在让 `/article/<slug>` 这类深链接可以直接访问（GitHub Pages 会把
未命中的路径交给 `404.html`，SPA 随即接管路由）。

## 重新构建 / 换成别的部署路径

`build/origin/` 里保存着从原站抓取的原始文件：

- `index.html`（含 Qoder 浮水印脚本）
- `app.js`（未打补丁的 bundle）
- `app.css`

`build/build.py` 负责生成根目录下的成品。它接受一个 base path 参数：

```bash
python3 build/build.py /            # 部署在域名根目录（<user>.github.io 用户页）
python3 build/build.py /my-blog/    # 部署在项目子路径（<user>.github.io/my-blog/）
```

脚本做的事：

| 文件 | 改动 |
|------|------|
| `index.html` / `404.html` | 删除 Qoder 浮水印 `<script>`；把 `/assets/...` 重写成 `<base>/assets/...` |
| `assets/index-*.js` | 注入 react-router `basename`，并把 markdown 里的 `/images/...` 重写成 `<base>/images/...` |
| `assets/index-*.css` | 把 KaTeX 字体的 `url(/assets/...)` 改成相对路径 `url(./...)` |

## 本地预览

```bash
python3 build/build.py /my-blog/
# 用一个会把 404 回退到 404.html 的静态服务器预览（普通 http.server 不会这么做）
```

直接双击 `index.html` 打开也能看到首页，但 `article/...` 这类深链接需要一个
支持 404 回退的静态服务器。

## 内容

| 日期 | 分类 | 标题 |
|------|------|------|
| 2026-09-19 | 大模型 | DeepSeek V4 注意力架构拆解：Compressor、Indexer、HCA 与 CSA |
| 2026-08-20 | 工具使用 | Vim 高效编辑工作流：从入门到肌肉记忆 |
| 2026-08-12 | 读书笔记 | 《设计模式之禅》读书笔记：SOLID 原则再审视 |

文章正文（Markdown）在 `content/articles.json` 里，字段为
`slug / title / date / category / tags / excerpt / content`。
注意：正文是打包进 JS bundle 的，改 `articles.json` 不会影响站点显示，
要改内容需要重新打包源码。
