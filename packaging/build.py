"""Build the desktop app. macOS -> .app + .dmg, Windows -> single .exe.

    uv run python packaging/build.py
PyInstaller cannot cross-compile: run this on each target OS (see .github/workflows/build.yml).
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "CAESAR Course Check"
SEP = ";" if sys.platform == "win32" else ":"


def run(*cmd, cwd=ROOT):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(list(map(str, cmd)), cwd=cwd, check=True)


def make_assets():
    run(sys.executable, "packaging/make_icon.py")


def build_frontend():
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    run(npm, "ci", cwd=ROOT / "frontend")
    run(npm, "run", "build", cwd=ROOT / "frontend")


def build_bundle():
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", NAME,
        "--add-data", f"caesar_checker/static{SEP}caesar_checker/static",
        "--add-data", f"caesar_checker/catalog.json{SEP}caesar_checker",
        "--collect-all", "playwright",   # bundles the Node driver Playwright needs
        "--collect-submodules", "uvicorn",
        "--hidden-import", "webview",
    ]
    if sys.platform == "win32":
        args += ["--onefile", "--collect-submodules", "pystray", "--hidden-import", "pystray._win32"]
        args += ["--icon", "assets/icon.ico"]
    elif sys.platform == "darwin":
        # Trim size: Pillow is Windows-tray only; uvloop/httptools/watchfiles are optional uvicorn speedups.
        for m in ("PIL", "uvloop", "httptools", "watchfiles"):
            args += ["--exclude-module", m]
        args += ["--osx-bundle-identifier", "com.local.caesarcoursecheck", "--icon", "assets/AppIcon.icns"]
    run(*args, "run_app.py")


def patch_app():
    """Menu-bar app: no Dock icon from launch (LSUIElement), proper names; re-sign ad hoc after editing."""
    app = ROOT / "dist" / f"{NAME}.app"
    plist = app / "Contents" / "Info.plist"
    for key, kind, val in [("LSUIElement", "-bool", "true"), ("CFBundleDisplayName", "-string", NAME),
                           ("CFBundleName", "-string", NAME), ("CFBundleShortVersionString", "-string", "0.1.0"),
                           ("NSHumanReadableCopyright", "-string", "CAESAR Course Check")]:
        run("plutil", "-replace", key, kind, val, plist)
    # Playwright's bundled Node ships with symbols (~38 MB); strip them, then re-sign everything.
    for node in app.glob("Contents/**/playwright/driver/node"):
        run("strip", "-x", node)
    run("codesign", "--force", "--deep", "--sign", "-", app)


def make_dmg():
    app = ROOT / "dist" / f"{NAME}.app"
    dmg = ROOT / "dist" / "CAESAR-Course-Check.dmg"
    dmg.unlink(missing_ok=True)
    run(sys.executable, "-m", "dmgbuild", "-s", "packaging/dmg_settings.py", "-D", f"app={app}", NAME, dmg)
    print("DMG:", dmg)


if __name__ == "__main__":
    make_assets()
    build_frontend()
    build_bundle()
    if sys.platform == "darwin":
        patch_app()
        make_dmg()
    elif sys.platform == "win32":
        print("EXE:", ROOT / "dist" / f"{NAME}.exe")
