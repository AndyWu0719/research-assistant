# Research Assistant

Version 1.0.0

本项目是一个原生 macOS 桌面研究工作台，用于配置研究任务、调用本地 Codex CLI、查看结果、管理自动化调度，并通过 GitHub Releases 分发更新。

默认执行链路：

```text
Research Assistant Desktop
  -> local workspace
  -> Codex CLI
  -> Markdown + JSON outputs
  -> GitHub release update checks
```

## 1. 任务理解

目标是提供一个不依赖浏览器套壳的桌面应用，完成以下能力：

- 研究任务配置
- 本地执行
- 结果回读
- 自动化调度
- 安装包分发
- 版本检查与覆盖升级

## 2. 当前平台范围

- 当前正式发布平台：macOS
- 当前安装格式：`.app` 与 `.pkg`
- 当前应用版本：`Version 1.0.0`

## 3. 项目结构

```text
research-assistant/
├── AGENTS.md
├── desktop/
│   ├── app.py
│   ├── main.py
│   └── runtime.py
├── research_assistant/
│   ├── app_update.py
│   ├── automation_runtime.py
│   ├── codex_bridge.py
│   ├── config_store.py
│   ├── file_naming.py
│   ├── language.py
│   ├── paper_sources.py
│   ├── pdf_extractor.py
│   ├── prompt_builder.py
│   ├── result_loader.py
│   └── ui_text.py
├── configs/
│   ├── app_update.yaml
│   ├── scan_defaults.yaml
│   └── automations/
├── outputs/
├── packaging/
│   ├── runtime-requirements.txt
│   ├── requirements-build.txt
│   └── macos/
│       ├── sign_and_notarize.py
│       ├── signing.env.example
│       └── store_notary_credentials.sh
├── scripts/
│   ├── bootstrap.py
│   ├── build_installer.py
│   ├── run_automation.py
│   └── smoke_test.py
└── skills/
```

目录职责：

- `desktop/`：桌面窗口、页面布局、运行时入口
- `research_assistant/`：任务执行、结果加载、更新检查、配置管理
- `configs/`：默认配置、自动化配置、更新配置
- `outputs/`：研究结果、自动化结果、smoke test 报告
- `packaging/`：构建、签名、公证
- `scripts/`：启动、打包、自动化、验证

## 4. 运行时工作区

开发态：

- 默认直接使用当前仓库作为工作区

打包态：

- 首次启动会同步模板到  
  `~/Library/Application Support/Research Assistant/workspace`
- 用户配置、自动化状态、结果输出都写入这个工作区

## 5. 本地启动

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python desktop/main.py
```

也可以直接执行：

```bash
python scripts/bootstrap.py
```

## 6. Codex CLI 要求

桌面应用执行研究任务时依赖本地 `Codex CLI`。

建议先确认：

```bash
codex --version
codex login status
```

说明：

- 应用会优先从当前环境的 `PATH` 查找 `codex`
- 在 macOS 图形界面环境下，如果 Finder 启动时缺少 shell `PATH`，应用也会额外尝试常见安装路径
- `codex login status` 为可用状态时，应用会直接调用本地 CLI

## 7. 自动化

查看状态：

```bash
python desktop/main.py --status
```

强制执行当前自动化：

```bash
python scripts/run_automation.py --active-only --force
```

启动本地调度器：

```bash
python scripts/run_automation.py --daemon
```

## 8. 版本与更新

桌面应用顶栏会显示当前版本，并提供 `检查更新` 按钮。默认行为如下：

- 启动时自动检查更新
- 24 小时内只做一次自动检查
- 发现新版本后可直接在应用内下载 `.pkg`
- 下载完成后自动打开安装器，按提示覆盖安装

当前默认更新源是 GitHub Releases，不需要额外服务器。

更新配置文件：

- `configs/app_update.yaml`

默认内容：

```yaml
provider: github_release
github_repo: AndyWu0719/research-assistant
github_asset_pattern: ResearchAssistant-macos-*.pkg
github_token_env: ""
manifest_url: ""
channel: stable
check_on_launch: true
check_interval_hours: 24
download_in_app: true
open_download_in_browser: false
```

说明：

- `provider: github_release`：直接读取 GitHub 最新 release
- `github_repo`：GitHub 仓库，格式 `owner/repo`
- `github_asset_pattern`：用于匹配 macOS 安装包资产
- `github_token_env`：私有仓库时可填一个环境变量名，用于读取 GitHub token
- `manifest_url`：保留为通用更新清单模式的备用入口，不是默认模式

发布新版本时，至少需要满足：

1. 生成新的 `.pkg`，文件名形如 `ResearchAssistant-macos-1.0.1.pkg`
2. 推送代码与 tag
3. 在 GitHub Releases 创建一个 release
4. 上传对应 `.pkg` 作为 release asset

客户端会读取最新 release，并从 asset 文件名、release 名称或 tag 中解析版本号。

当前未接入 Sparkle。原因很简单：

- 当前链路已经能做到“自动检查 + 应用内下载 + 打开安装器覆盖更新”
- Sparkle 主要价值在于更原生的后台更新、签名校验、delta 更新和更完整的 macOS 自更新体验
- 如果后续需要更强的“静默感”和更少的安装步骤，再把 Sparkle 作为第二阶段接入

## 9. macOS 安装与覆盖升级

当前 `.pkg` 支持覆盖安装。

升级行为：

- 若本机已有 `/Applications/Research Assistant.app`
- 直接安装新版 `.pkg` 即可覆盖旧版
- 用户工作区与输出结果会保留

当前不属于正常升级链路的错误安装目录：

- `/Applications/Research Assistant`
- `/Applications/Research Assistant.localized`

若机器上还保留这两类旧目录，需要手动删除。

## 10. macOS 构建

安装依赖：

```bash
python -m pip install -r requirements.txt
python -m pip install -r packaging/requirements-build.txt
```

构建 `.app` 与 `.pkg`：

```bash
python scripts/build_installer.py --platform macos --version 1.0.0
```

构建产物：

- `dist/installers/macos/pyinstaller/Research Assistant.app`
- `dist/installers/macos/ResearchAssistant-macos-1.0.0.pkg`

## 11. macOS 签名与公证

一次性写入 notarization 凭据：

```bash
source packaging/macos/signing.env
bash packaging/macos/store_notary_credentials.sh
```

正式签名与公证：

```bash
source packaging/macos/signing.env
python packaging/macos/sign_and_notarize.py --version 1.0.0
```

仅签名、不提交公证：

```bash
python packaging/macos/sign_and_notarize.py --version 1.0.0 --skip-notarize
```

## 12. 验证

桌面 smoke test：

```bash
python scripts/smoke_test.py
```

该脚本会检查：

- 桌面窗口是否可实例化
- Codex CLI 状态
- 调度器状态
- PDF resolve-only 链路
- 更新检查基础能力

结果输出目录：

- `outputs/smoke_tests/`

## 13. 当前限制

- 研究任务仍依赖外部检索质量与本地 Codex CLI 可用性
- GitHub 更新链路依赖你创建 GitHub Release 并上传 `.pkg`
- 对外分发时仍需要你自己的 Apple Developer 证书与 notarization 凭据
