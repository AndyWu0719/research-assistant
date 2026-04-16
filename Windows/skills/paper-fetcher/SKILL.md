---
name: paper-fetcher
description: 当用户明确表示想下载、保存或收集某篇论文 PDF 时使用；支持根据论文链接、arXiv 页面、OpenReview 页面、DOI 或直接 PDF 链接，将文件下载到 outputs/pdfs/，并默认用中文反馈结果。
---

# Paper Fetcher

## 何时使用

- 用户明确说要“下载这篇论文”“保存 PDF”“把这篇拉下来”。
- 用户已经对某篇论文表示兴趣，希望把 PDF 落到本地。
- 用户提供的是：
  - 直接 PDF 链接
  - arXiv 摘要页或 arXiv ID
  - OpenReview 页面
  - DOI
  - 一般论文落地页，且页面上能解析出 PDF 链接

## 何时不要执行下载

- 用户只是让你推荐、排序、总结或比较论文。
- 用户只是在问“这篇值不值得看”，但没有明确要求下载。
- 链接不明确、来源不可信，且无法稳定解析到 PDF。

## 输入

- 论文链接、arXiv ID 或 OpenReview 页面链接
- 或 DOI
- 可选文件名
- 可选输出目录，默认 `outputs/pdfs/`

## 执行方式

- 优先使用脚本：
  - [skills/paper-fetcher/scripts/download_paper.py](/Users/andywu/Documents/codex_workplace/projects/research-assistant/skills/paper-fetcher/scripts/download_paper.py)
- 默认命令：

```bash
python3 skills/paper-fetcher/scripts/download_paper.py "<url_or_id>"
```

- 仅当用户明确表示感兴趣并要求下载时才执行。

## 支持来源

- `arXiv`
  - `https://arxiv.org/abs/...`
  - `https://arxiv.org/pdf/...`
  - 纯 arXiv ID
- `OpenReview`
  - `https://openreview.net/forum?id=...`
  - `https://openreview.net/pdf?id=...`
- `DOI`
  - `10.xxxx/...`
  - `https://doi.org/...`
- 直接 PDF
  - 任意可直接下载的 `.pdf` 链接
- 一般论文页面
  - 如果页面里能解析出明确 PDF 链接，则继续下载

## 输出要求

- 默认使用中文反馈：
  - 解析到的 PDF 链接
  - 保存路径
  - 来源 sidecar 路径
  - 是否复用已有文件
  - 下载是否成功
- 下载成功后，文件应位于：
  - `outputs/pdfs/`
- 如果无法解析或下载失败，要明确说明失败原因。
- 如果无法稳定获取 PDF，要返回候选页面或候选链接。

## 质量要求

- 不重复下载同一路径文件，除非用户明确要求覆盖。
- 优先保留稳定、可读、可追踪的文件名。
- 如果能解析到标题、作者和年份，优先使用 `<year>-<first_author>-<short_title>.pdf` 形式。
- 对于 arXiv 和 OpenReview，优先生成平台相关文件名，避免不同来源互相覆盖。

## 通用要求

- 默认使用中文输出。
- 只有在用户明确表示感兴趣时才执行下载。
- 下载前应尽量确认链接最终指向的是论文 PDF，而不是无关附件。
