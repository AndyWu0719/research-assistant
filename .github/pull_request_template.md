## Summary

- explain the user-facing change
- note any packaging or release impact
- if you touched the root legacy tree, explain why it still needs to be modified

## Validation

- [ ] `python -m py_compile MacOS/scripts/build_installer.py Windows/scripts/build_installer.py MacOS/research_assistant/config_store.py Windows/research_assistant/config_store.py MacOS/desktop/main.py Windows/desktop/main.py`
- [ ] `python MacOS/scripts/smoke_test.py` when applicable
- [ ] README updated if behavior changed

## Screenshots Or Logs

Add screenshots, terminal output, or release notes if helpful.
