import sys

# Windowed frozen apps (notably on Windows) have no stdout/stderr. Uvicorn and Playwright
# touch them, so redirect to a log file before importing anything else.
if getattr(sys, "frozen", False) or sys.stdout is None or sys.stderr is None:
    from caesar_checker.paths import data_dir

    _log = open(data_dir() / "app.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = _log
    sys.stderr = _log

from caesar_checker.app import main

if __name__ == "__main__":
    main()
