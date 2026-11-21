@echo off
REM Build the Windows .exe on a Windows machine. Requires: uv, Node.js 20+.
uv sync || exit /b 1
uv run python packaging/build.py || exit /b 1
echo Done: dist\CAESAR Course Check.exe
