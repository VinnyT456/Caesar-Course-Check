"""Desktop entry point.

macOS: menu bar only. The whole UI is the popover under the status item (no window, no Dock icon).
Windows: system tray icon + a frameless flyout window (hides on blur).
Other: a normal pywebview window.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
import urllib.request

import uvicorn

from .server import create_app

IS_MAC = sys.platform == "darwin"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    holder: dict = {"window": None}
    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    def on_alert(message: str) -> None:
        """A seat opened (or a test): send a real OS notification, then open the popover."""
        if IS_MAC:
            from PyObjCTools import AppHelper

            from . import tray

            def _mac() -> None:  # AppKit is main-thread only
                if not tray.notify("Seat available!", message):
                    subprocess.Popen(["osascript", "-e", f'display notification "{message}" with title "CAESAR Alert" sound name "Glass"'])
                tray.show_popover()

            AppHelper.callAfter(_mac)
            return
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.MessageBeep(0x40)
            except Exception:
                pass
            if holder.get("flyout") is not None:
                holder["flyout"].notify("Seat available!", message)
        if holder.get("flyout") is not None:
            holder["flyout"].show()
        elif holder["window"] is not None:
            try:
                holder["window"].show()
            except Exception as e:
                print("show window failed:", e, flush=True)

    def quit_app() -> None:
        if IS_MAC:
            from PyObjCTools import AppHelper

            def _shutdown() -> None:
                # Runs off the uvicorn thread: it cannot join itself, and the HTTP reply must finish first.
                time.sleep(0.3)
                server.should_exit = True  # lifespan shutdown closes headless Chrome
                thread.join(timeout=8)
                AppHelper.callAfter(AppHelper.stopEventLoop)

            threading.Thread(target=_shutdown, daemon=True).start()
        elif holder.get("flyout") is not None:
            holder["flyout"].quit()  # stops the tray icon, then destroys the window
        elif holder["window"] is not None:
            holder["window"].destroy()

    app = create_app(on_alert=on_alert, on_quit=quit_app)
    app.state.test_alert = lambda: on_alert("Test alert: this is how a seat opening will look.")
    checker = app.state.checker
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", log_config=None))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(100):
        try:
            urllib.request.urlopen(f"{url}/api/state", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)

    if IS_MAC:
        from PyObjCTools import AppHelper

        from . import tray

        tray.install(checker.snapshot, url)  # opens only when you click the icon (or a seat opens)
        AppHelper.runEventLoop(installInterrupt=True)
    else:
        import webview

        if sys.platform == "win32":
            from . import tray_win

            window = webview.create_window(
                "CAESAR Course Check", url + "/?view=popover", width=tray_win.WIDTH, height=tray_win.HEIGHT,
                frameless=True, on_top=True, hidden=True, resizable=False, shadow=True,
            )
            holder["window"] = window
            flyout = tray_win.Flyout(window, on_quit=window.destroy)
            holder["flyout"] = flyout
            flyout.start(show_on_launch=False)
            webview.start()  # flyout opens only from the tray icon (or a seat opening)
        else:
            window = webview.create_window("CAESAR Course Check", url, width=520, height=780, min_size=(420, 620))
            holder["window"] = window
            webview.start()

    server.should_exit = True
    thread.join(timeout=10)


if __name__ == "__main__":
    main()
