# Contributing

Thanks for contributing to `research-assistant`.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r MacOS/requirements.txt
python -m pip install -r MacOS/packaging/requirements-build.txt
```

Launch the macOS baseline locally:

```bash
python MacOS/desktop/main.py
```

Preferred contribution target:

- put product changes into `MacOS/` first, because it is the verified baseline
- mirror intentionally into `Windows/` when the behavior should stay symmetric
- do not touch the root legacy tree unless you are explicitly maintaining compatibility or preparing retirement work

## Before Opening A Pull Request

Please keep changes focused and include the following checks when relevant:

```bash
python -m py_compile MacOS/scripts/build_installer.py Windows/scripts/build_installer.py MacOS/research_assistant/config_store.py Windows/research_assistant/config_store.py MacOS/desktop/main.py Windows/desktop/main.py
python MacOS/scripts/smoke_test.py
```

If your change affects packaging:

- verify the documented build command still works
- update `README.md` and `README.en.md` when user-facing behavior changes
- keep `MacOS/` and `Windows/` subtree changes aligned when behavior should stay symmetric
- if you modify the root legacy tree, explain why it still needs to exist and why the change cannot live only under `MacOS/` / `Windows/`

## Pull Request Expectations

- explain the user-facing change clearly
- note any platform limitations or build constraints
- include screenshots for desktop UI changes when practical
- avoid committing local runtime artifacts from `outputs/`, `dist/`, or personal config files

## Release Notes

If a PR changes installer names, release tags, or update behavior, include a short release note draft in the PR body.
