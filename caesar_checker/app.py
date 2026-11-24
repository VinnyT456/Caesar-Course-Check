"""Desktop entry point.

macOS: menu bar only. The whole UI is the popover under the status item (no window, no Dock icon).
Windows (and anything else): a normal standalone window. Closing it quits; minimise it to keep monitoring.
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


def _flash(win) -> None:
    """Make the taskbar button flash until the user looks at the window (Windows only)."""
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                        ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]

        hwnd = int(win.native.Handle.ToInt64())
        # FLASHW_ALL | FLASHW_TIMERNOFG: flash caption and taskbar until the window is foreground
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 3 | 12, 0, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception as e:  # noqa: BLE001 - flashing is a nicety
        print("flash failed:", e, flush=True)


def main() -> None:
    holder: dict = {"window": None}
    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    def on_alert(message: str, title: str = "Seat available!") -> None:
        """A seat opened (or a test, or the captcha expired): send a real OS notification, then open the popover."""
        silent = app.state.checker.config.sound == "off"
        if IS_MAC:
            from PyObjCTools import AppHelper

            from . import tray

            def _mac() -> None:  # AppKit is main-thread only
                if not tray.notify(title, message, silent):
                    sound = "" if silent else ' sound name "Glass"'
                    subprocess.Popen(["osascript", "-e", f'display notification "{message}" with title "{title}"{sound}'])
                tray.show_popover()

            AppHelper.callAfter(_mac)
            return
        win = holder["window"]
        if sys.platform == "win32":
            try:
                import ctypes

                if not silent:
                    ctypes.windll.user32.MessageBeep(0x40)
            except Exception:
                pass
            try:  # a Windows toast; the window also pops up and flashes below
                from plyer import notification

                notification.notify(title=title, message=message, app_name="CAESAR Course Check", timeout=10)
            except Exception as e:  # noqa: BLE001
                print("toast failed:", e, flush=True)
        if win is not None:
            try:  # bring the window forward (restores it if minimised), then let it behave normally again
                win.restore()
                win.show()
                win.on_top = True
                win.on_top = False
            except Exception as e:
                print("show window failed:", e, flush=True)
            if sys.platform == "win32":
                _flash(win)

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
        elif holder["window"] is not None:
            holder["window"].destroy()

    app = create_app(on_alert=on_alert, on_quit=quit_app)
    checker = app.state.checker

    def open_caesar() -> str:
        """Open CAESAR (in Chrome when installed), copy the open class's number to the clipboard, close the popover.

        Returns the text that was copied ("" if nothing was).
        """
        import webbrowser

        from .checker import CAESAR_URL

        checker.ack()
        label, nbr = checker.open_target()
        text = nbr or label
        copied = ""
        try:
            if IS_MAC:
                subprocess.run(["pbcopy"], input=text.encode(), check=True, timeout=3)
            elif sys.platform == "win32":
                subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True, timeout=3, shell=True)
            copied = text
        except Exception as e:  # noqa: BLE001 - the clipboard is a convenience
            print("clipboard failed:", e, flush=True)
        opened = IS_MAC and subprocess.run(["open", "-a", "Google Chrome", CAESAR_URL], capture_output=True).returncode == 0
        if not opened:
            webbrowser.open(CAESAR_URL)
        if IS_MAC:
            from PyObjCTools import AppHelper

            from . import tray

            AppHelper.callAfter(tray.close_popover)  # let the browser come to the front
        return copied

    app.state.open_caesar = open_caesar
    app.state.test_alert = lambda: on_alert("Test alert: this is how a seat opening will look.")

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

        tray.on_click = open_caesar
        tray.install(checker.snapshot, url)  # opens only when you click the icon (or a seat opens)
        AppHelper.runEventLoop(installInterrupt=True)
    else:
        import webview

        window = webview.create_window(
            "CAESAR Course Check", url + "/?view=window", width=380, height=600, min_size=(340, 540), text_select=True,
        )
        holder["window"] = window
        webview.start()  # returns when the window is closed

    server.should_exit = True
    thread.join(timeout=10)


if __name__ == "__main__":
    main()
