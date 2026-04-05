# Contributing

Thanks for contributing to `research-assistant`.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r packaging/requirements-build.txt
```

Launch the desktop app locally:

```bash
python desktop/main.py
```

## Before Opening A Pull Request

Please keep changes focused and include the following checks when relevant:

```bash
python -m py_compile scripts/build_installer.py research_assistant/config_store.py research_assistant/app_update.py desktop/main.py
python scripts/smoke_test.py
```

If your change affects packaging:

- verify the documented build command still works
- update `README.md` and `README.en.md` when user-facing behavior changes
- keep macOS and Windows packaging instructions aligned

## Pull Request Expectations

- explain the user-facing change clearly
- note any platform limitations or build constraints
- include screenshots for desktop UI changes when practical
- avoid committing local runtime artifacts from `outputs/`, `dist/`, or personal config files

## Release Notes

If a PR changes installer names, release tags, or update behavior, include a short release note draft in the PR body.
