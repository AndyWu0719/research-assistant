# Site Auth Center And Source Expansion Design

**Date:** 2026-04-20  
**Status:** Drafted from approved design discussion  
**Platforms:** `MacOS/`, `Windows/`  
**Verified baseline:** `MacOS/` remains the implementation baseline; `Windows/` must stay structurally mirrored

---

## 1. Goal

Add a secure, global "site account center" to the desktop app so users can preconfigure site credentials for protected paper platforms, then automatically fill credentials and continue access when a paper page or PDF download requires login.

At the same time:
- extend the source catalog beyond current AI/CS-focused sites to include well-known social science and humanities sources;
- replace cramped time-range dropdown labels like `最近 90 天` with compact controls such as `最近 [30] 天`;
- keep the current public-source download flow unchanged for open platforms like `arXiv` and `OpenReview`.

This is a structure-and-capability feature, not a broad refactor of research logic.

---

## 2. User Problem

Current paper access works well for public sources, but breaks down on platforms that require:
- a site account and password;
- institution SSO redirects;
- a short interactive MFA step before the session becomes usable.

Today the app has no secure place to store those credentials, no reusable login session model, and no way to distinguish between:
- a search source used for literature discovery;
- a protected full-text platform used to actually access or download the paper.

The current time-range UI also uses long fixed phrases inside dropdowns, which makes labels cramped and hard to read.

---

## 3. Non-Negotiable Constraints

### Security

- Sensitive credentials must **not** be stored in existing YAML/JSON preference files.
- Passwords must be stored in platform-native secure storage:
  - macOS: Keychain
  - Windows: Credential Manager
- Plaintext credentials must never be written to:
  - `configs/*.yaml`
  - `outputs/`
  - sidecar files
  - prompt payloads

### Platform structure

- `MacOS/` is the behavior baseline.
- `Windows/` should receive the same feature shape with minimal divergence.
- Root thin compatibility layer should not become the feature implementation home.

### Scope control

- No "support every possible website" promise.
- No generic fully automatic SSO/MFA engine in v1.
- No large shared-core refactor.
- No UI redesign unrelated to this feature.

---

## 4. Proposed Feature

### 4.1 Global Site Account Center

Add a new global toolbar entry to the desktop app:

```text
[准备 Codex] [完成登录] [站点账号] [语言]
```

The new `站点账号` button opens a modal account center. It is a global capability panel, not a new left-nav primary page.

This center manages:
- protected site credential records;
- safe storage of usernames/passwords;
- per-site session state;
- test login / clear session / delete credential actions.

### 4.2 Protected-Site Assisted Access

When the user fetches a PDF or opens a paper from a protected site:

```text
Paper URL / DOI / landing page
  -> detect source platform
  -> if public site: existing downloader path
  -> if protected site:
       check cached session
       -> session valid: continue access/download
       -> session missing/expired:
            open controlled login window
            auto-fill username/password
            user completes SSO/MFA if needed
            save session
            resume access/download
```

### 4.3 Source Catalog Expansion

Extend the discovery/source options to include broader disciplines, especially social science and humanities.

### 4.4 Compact Time-Range Controls

Replace long time-range dropdown labels with fixed text plus compact variable controls:

```text
最近 [30] 天
最近 [1] 年
```

The fixed semantic parts should live outside the dropdown itself. Only the variable value and unit remain selectable.

---

## 5. Architecture

## 5.1 Data Layers

The design uses three data layers.

### Layer A: Non-sensitive metadata

Stored in the app's normal config system. Example fields:
- `site_key`
- `account_label`
- `username_hint`
- `login_mode`
- `institution_hint`
- `auto_fill_enabled`
- `has_secret`
- `last_login_success_at`
- `last_session_refresh_at`

This layer is safe to keep in app-managed config files.

### Layer B: Sensitive credentials

Stored only in OS-native secure storage.

Example fields:
- full username
- password
- optional institution identifier when it is part of the login path

This layer must not appear in YAML/JSON config.

### Layer C: Session state

Short-lived site session material is stored separately from normal preferences and separately from long-lived secrets.

Requirements:
- isolated by site/account;
- revocable;
- clearable from the UI;
- not stored in public output files.

This layer holds session cookies/token state needed to resume authenticated access without relogin.

## 5.2 Execution Responsibility Split

### UI layer

Responsible for:
- toolbar entry;
- account center modal;
- compact time-range controls;
- task-page status summaries and shortcut button.

### Secure credential layer

Responsible for:
- storing/retrieving secrets from Keychain/Credential Manager;
- storing non-sensitive credential metadata in app config;
- deleting and listing credential records.

### Site access/session layer

Responsible for:
- deciding whether a site is public or protected;
- reusing cached sessions;
- invoking controlled login flow when required;
- resuming the original paper access/download action.

### Download layer

Responsible for:
- existing public downloader path for open sites;
- delegating to protected-site access flow when needed.

---

## 6. UI Design

## 6.1 Global Toolbar Entry

Add `站点账号` beside the existing Codex setup/login controls.

Optional small status text may show:
- number of configured protected sites;
- or number of sites with active sessions.

## 6.2 Account Center Modal

Recommended structure:

### Left pane

- All
- Configured
- Active sessions
- AI / Computer Science
- General academic
- Social sciences
- Humanities
- Protected full-text platforms

### Right pane

For the selected site:
- site description
- supported login mode
- username field
- password field (stored securely, never re-displayed as plaintext)
- optional institution/school hint field
- auto-fill toggle
- test login
- clear session
- delete credential

At the top of the right pane:
- credential state
- last login success time
- current session validity state

## 6.3 Task Page Integration

Task pages should not embed full credential forms. They should only show:
- a short account-status summary;
- a `管理站点账号` shortcut button.

This keeps task pages clean while still making the feature discoverable.

## 6.4 Compact Time Controls

At minimum, convert these pages to the compact time control model:
- Literature Scout
- Automation
- Topic Mapper

Rule:
- fixed text like `最近` should not live inside a dropdown option;
- only numeric value and unit remain variable controls.

The same treatment should be used for any other similarly cramped fixed-phrase controls found during implementation.

---

## 7. Site Scope

## 7.1 Discovery/Search Sources

These are selectable research sources for literature discovery.

### AI / Computer Science
- `arXiv`
- `OpenReview`
- `ACL Anthology`
- `CVF Open Access`
- `PMLR`

### General Academic
- `Semantic Scholar`
- `Crossref`
- `Google Scholar`

### Additional Social Science / Education / Medical Discovery
- `SSRN`
- `PubMed`
- `ERIC`

### Additional Humanities / Social Science Discovery
- `JSTOR`
- `Project MUSE`
- `PhilPapers`

## 7.2 Protected Full-Text Platforms

These are primarily account-center targets, not necessarily default discovery sources:

- `JSTOR`
- `Project MUSE`
- `ProQuest`
- `EBSCOhost`
- `ScienceDirect`
- `SpringerLink`
- `Wiley Online Library`
- `Taylor & Francis`
- `Sage Journals`

---

## 8. Login And Access Flow

## 8.1 Public Sites

Public sites should continue using the existing direct downloader path.

Examples:
- `arXiv`
- `OpenReview`
- `ACL Anthology`
- `CVF Open Access`
- `PMLR`

No login modal should appear for these platforms unless the source unexpectedly redirects into a protected flow.

## 8.2 Protected Sites

For protected full-text platforms:

1. Detect site/platform from paper URL or landing page.
2. Look up configured account metadata.
3. Attempt session reuse first.
4. If session is missing or invalid, open a controlled login window.
5. Auto-fill username/password when applicable.
6. If institution SSO takes over, let the user continue the flow manually.
7. If MFA appears, let the user complete it manually.
8. On success, persist session state.
9. Resume the original paper access/download action.

## 8.3 MFA Boundary

The app should support MFA **compatibly**, not fully automate it.

Meaning:
- The app can reach the MFA step by auto-filling the credential stage.
- The user completes the MFA interaction.
- Once complete, the session is reused.

The app does **not** promise to automatically solve:
- SMS codes
- email OTP
- TOTP entry
- push approval flows

## 8.4 Failure Fallback

Required fallback behaviors:

- No credential configured:
  - open account center focused on the requested site.
- Auto-fill fails:
  - keep the login window open for manual completion.
- SSO page not recognized:
  - allow manual continuation in the same window.
- MFA canceled/timed out:
  - fail gracefully without deleting saved credentials.
- Login success but PDF still inaccessible:
  - open the landing page for manual inspection.
- Session expired:
  - automatically request re-login.

---

## 9. v1 In-Scope / Out-Of-Scope

## 9.1 In Scope

- global site account center;
- secure credential storage;
- session reuse model;
- protected-site login assist for supported sites;
- integration into:
  - PDF Fetcher
  - Paper Reader automatic PDF fetch;
- source option expansion;
- compact time controls;
- task-page account summary + shortcut entry.

## 9.2 Out Of Scope

- support for arbitrary unknown websites;
- fully background, no-window SSO automation;
- fully automatic MFA completion;
- batch full-text login/download automation for all Literature Scout results;
- cloud sync for site credentials;
- complex multi-account prioritization rules.

---

## 10. File-Level Implementation Boundary

Expected primary touch points:

### UI
- `MacOS/desktop/app.py`
- `Windows/desktop/app.py`

### Config and metadata
- `MacOS/research_assistant/config_store.py`
- `Windows/research_assistant/config_store.py`

### New secure credential helpers
- `MacOS/research_assistant/site_credentials.py`
- `Windows/research_assistant/site_credentials.py`

### New site access/session helpers
- `MacOS/research_assistant/site_access.py`
- `Windows/research_assistant/site_access.py`

### Downloader integration
- `MacOS/skills/paper-fetcher/scripts/download_paper.py`
- `Windows/skills/paper-fetcher/scripts/download_paper.py`

### Tests
- new tests for credential metadata, secure storage boundaries, time-range control mapping, protected-site detection, and session fallback behavior.

This feature should not be implemented inside the root thin compatibility layer except where compatibility wrappers must continue to point at `MacOS/` and `Windows/`.

---

## 11. Risks

### Risk 1: Site-specific DOM variation

Mitigation:
- implement a supported-site whitelist;
- avoid claiming a universal login engine.

### Risk 2: SSO unpredictability

Mitigation:
- automate only the pre-SSO credential stage;
- let the user complete the institution flow in-window.

### Risk 3: MFA brittleness

Mitigation:
- do not automate the MFA step;
- persist the resulting session after successful manual completion.

### Risk 4: Cross-platform secure storage differences

Mitigation:
- keep OS-specific secret access behind a small helper API;
- do not let UI or downloader code talk directly to platform secret primitives.

### Risk 5: UI regression

Mitigation:
- keep existing page layout largely intact;
- add a global entry and small task-page summaries instead of embedding large new forms into every task.

---

## 12. Testing Strategy

### Configuration/Security
- verify sensitive data never lands in YAML/JSON config;
- verify metadata and secure secret lookups stay consistent;
- verify delete/remove actions actually remove secret access.

### UI
- toolbar button opens account center;
- account summary appears on relevant task pages;
- compact time controls map correctly to internal `time_range` values;
- expanded source options appear on both platforms.

### Access Flow
- public-source download path remains unchanged;
- protected-site detection triggers login/session flow;
- valid session suppresses repeated login prompts;
- expired session triggers re-login;
- MFA interruption exits gracefully without crashing or wiping secrets.

### Platform
- macOS secure storage path works with Keychain;
- Windows secure storage path works with Credential Manager.

---

## 13. Recommended Delivery Order

```text
Account-center metadata model
  -> secure storage interface
  -> compact time controls + source expansion
  -> protected-site detection
  -> controlled login window + session reuse
  -> PDF Fetcher / Paper Reader integration
  -> regression verification
```

This order keeps the highest-risk login/session work behind the already-correct config and UI boundaries.

---

## 14. Decision Summary

Approved design direction:
- **Approach:** global account center (`方案 A`)
- **Credential policy:** secure OS-native storage only
- **Login scope:** direct username/password + institution SSO assistance
- **MFA scope:** manual completion supported, not fully automated
- **UI scope:** compact time controls, expanded sources, global account management
- **Execution scope:** start with PDF Fetcher and Paper Reader auto-fetch, not broad batch full-text automation
