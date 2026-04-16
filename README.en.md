# Research Assistant

[简体中文](README.md) | [English](README.en.md)

> Current Version: `Version 1.0.0`

`research-assistant` is a local desktop research workstation. The desktop UI handles task configuration, local status, result review, and update prompts; the real execution is performed by a local `Codex CLI`; packaged macOS and Windows installs automatically prepare the local Codex CLI runtime on first launch; GitHub Releases is the default update source.

This project is not a browser shell and not a prompt-only wrapper.

## Repository Meta

- Contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security policy: [`SECURITY.md`](SECURITY.md)
- Windows build workflow: [`build-windows-installer.yml`](.github/workflows/build-windows-installer.yml)

## Architecture

```mermaid
flowchart LR
    A["Desktop UI"] --> B["Local Workspace"]
    B --> C["Codex CLI"]
    C --> D["Skills"]
    C --> E["Outputs (*.md + *.json)"]
    A --> E
    A --> F["GitHub Release Updates"]
```

## Current Scope

- Configure research tasks locally
- Execute real tasks through local `Codex CLI`
- Automatically prepare `Codex CLI` on first launch of the macOS and Windows installers, with no manual Codex installation step
- Read back Markdown and JSON outputs
- Manage local recurring automations
- Build macOS `.app` / `.pkg`
- Build Windows all-in-one installer `.exe`
- Check GitHub Releases and download the right installer per platform

## Platform Matrix

| Platform | Desktop UI | Runtime Workspace | Build Requirement | Installer Output |
| --- | --- | --- | --- | --- |
| macOS | Same PySide6 UI | `~/Library/Application Support/Research Assistant/workspace` | Must be built on a macOS host | `.app` + `.pkg` |
| Windows | Same PySide6 UI | `%LOCALAPPDATA%\\Research Assistant\\workspace` | Must be built on a Windows host or Windows CI | `.exe` |

Notes:

- The repository now uses two mirrored OS-specific subtrees: `MacOS/` and `Windows/`.
- `MacOS/` is the preserved, verified baseline in this migration stage, and `Windows/` mirrors it structurally.
- The Windows installer defaults to `%LOCALAPPDATA%\\Programs\\Research Assistant` and keeps the user workspace outside the install directory.

## Project Structure

```text
research-assistant/
├── .github/workflows/
├── MacOS/
│   ├── desktop/
│   ├── research_assistant/
│   ├── configs/
│   ├── outputs/
│   ├── packaging/
│   ├── scripts/
│   └── skills/
├── Windows/
│   ├── desktop/
│   ├── research_assistant/
│   ├── configs/
│   ├── outputs/
│   ├── packaging/
│   ├── scripts/
│   └── skills/
├── README.md
└── README.en.md
```

Directory responsibilities:

- `MacOS/`: current verified macOS baseline for local execution, packaging, and signing
- `Windows/`: mirrored Windows subtree for CI builds and future Windows-specific work
- repository root: docs, workflows, and the temporary migration compatibility baseline

## Runtime Workspace

Development mode:

- Use `MacOS/` as the preferred macOS workspace
- Use `Windows/` as the preferred Windows workspace
- The old root-level tree is still kept temporarily as a migration compatibility baseline

Packaged mode:

- macOS syncs to `~/Library/Application Support/Research Assistant/workspace` on first launch
- If `Codex CLI` is missing, macOS also prepares an app-managed Node.js / Codex CLI runtime under `~/Library/Application Support/Research Assistant/runtime/codex/`
- Windows syncs to `%LOCALAPPDATA%\\Research Assistant\\workspace` on first launch
- If `Codex CLI` is missing, Windows also prepares an app-managed Node.js / Codex CLI runtime under `%LOCALAPPDATA%\\Research Assistant\\runtime\\codex\\`
- User configs, automation state, and outputs are written there

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r MacOS/requirements.txt
python MacOS/desktop/main.py
```

Alternative launcher:

```bash
python MacOS/scripts/bootstrap.py
```

## Codex CLI Requirement

Research tasks still depend on a local `Codex CLI`, but packaged macOS and Windows builds now include the bootstrap flow, so users **no longer need to install Codex CLI manually**.

Current installer behavior:

- macOS and Windows first check for an existing system `codex`
- If none is found, it prepares a usable Node.js / npm runtime and installs `Codex CLI` into an app-managed directory
- If login has not been completed yet, it opens a terminal or command window and runs `codex login`
- In practice, the manual "install Codex CLI yourself" step is gone on the desktop installers; users usually only need to finish one authorization flow

Recommended checks:

```bash
codex --version
codex login status
```

Current behavior:

- The app first tries the current `PATH`
- It also probes the app-managed `Codex CLI`
- On macOS and Windows GUI launches, it also probes common install paths
- If `codex login status` is usable, the desktop app invokes the local CLI directly

## Automation

Check status:

```bash
python MacOS/desktop/main.py --status
```

Force-run the active automation:

```bash
python MacOS/scripts/run_automation.py --active-only --force
```

Start the local scheduler:

```bash
python MacOS/scripts/run_automation.py --daemon
```

## Build Installers

Install dependencies first:

```bash
python -m pip install -r MacOS/requirements.txt
python -m pip install -r MacOS/packaging/requirements-build.txt
```

### macOS

Build:

```bash
python MacOS/scripts/build_installer.py --platform macos --version 1.0.0
```

Artifacts:

- `MacOS/dist/installers/macos/pyinstaller/Research Assistant.app`
- `MacOS/dist/installers/macos/ResearchAssistant-macos-1.0.0.pkg`

Signing and notarization:

```bash
source MacOS/packaging/macos/signing.env
bash MacOS/packaging/macos/store_notary_credentials.sh
python MacOS/packaging/macos/sign_and_notarize.py --version 1.0.0
```

### Windows

Hard constraints:

- Build on a native Windows host, or use the included Windows GitHub Actions workflow
- Install NSIS to generate the all-in-one `.exe` installer

Local build prep:

```powershell
python -m pip install -r Windows/requirements.txt
python -m pip install -r Windows/packaging/requirements-build.txt
winget install NSIS.NSIS
```

Build:

```powershell
python Windows/scripts/build_installer.py --platform windows --version 1.0.0
```

Artifacts:

- `Windows/dist/installers/windows/pyinstaller/Research Assistant/`
- `Windows/dist/installers/windows/ResearchAssistant-windows-1.0.0.exe`

CI option:

- Workflow file: `.github/workflows/build-windows-installer.yml`
- It supports manual dispatch and tag-based builds on `v*`

## Updates

The top bar shows the current version and provides a `Check Updates` button.

Default behavior:

- Check on launch
- Throttle automatic checks to once per 24 hours
- Match release assets by platform
- Download `.pkg` on macOS
- Download `.exe` on Windows

Default config: `configs/app_update.yaml`

```yaml
provider: github_release
github_repo: AndyWu0719/research-assistant
github_asset_pattern: ""
github_asset_pattern_by_platform:
  macos: ResearchAssistant-macos-*.pkg
  windows: ResearchAssistant-windows-*.exe
github_token_env: ""
manifest_url: ""
channel: stable
check_on_launch: true
check_interval_hours: 24
download_in_app: true
open_download_in_browser: false
```

Release flow:

1. Build the installer for the target platform
2. Push code and a version tag
3. Create a GitHub Release
4. Upload the platform installer asset

## Validation

```bash
python MacOS/scripts/smoke_test.py
```

The current smoke test checks:

- Desktop window instantiation
- Codex CLI status
- Scheduler status
- PDF resolve-only path
- Basic update-check behavior

Windows installer UI validation:

- Workflow file: `.github/workflows/validate-windows-installer-ui.yml`
- Downloads `ResearchAssistant-windows-<version>.exe` from GitHub Releases
- Performs a silent install on a GitHub-hosted Windows runner, launches the installed app, captures a screenshot, and uploads the artifact
- Includes a `Windows vs macOS UI parity` note describing what is shared and what still differs at the OS level

Reports are written to:

- `outputs/smoke_tests/`

## Known Limits

- Research quality still depends on external retrieval quality and the local `Codex CLI`
- Windows installers can only be produced on native Windows or Windows CI
- GitHub-based updates require the correct platform asset on each release
- Public distribution still requires your own Apple / Windows signing setup
