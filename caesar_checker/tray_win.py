"""Windows system tray icon + flyout window (pystray + a frameless pywebview window).

Left-click the tray icon toggles the flyout; it hides itself when it loses focus.
Untested on a real Windows machine: written against the pystray / pywebview APIs.
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes

import pystray
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 340, 520
MARGIN = 12


def _icon_image() -> Image.Image:
    # Simple purple tile with a white mortarboard shape; drawn so no asset file is needed.
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=14, fill=(78, 42, 132, 255))
    d.polygon([(32, 16), (54, 28), (32, 40), (10, 28)], fill=(255, 255, 255, 255))
    d.rectangle((20, 36, 44, 46), fill=(255, 255, 255, 255))
    return img


def _work_area() -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right, rect.bottom


class Flyout:
    def __init__(self, window, on_quit):
        self.window = window
        self.on_quit = on_quit
        self.visible = False
        self.shown_at = 0.0
        self.icon: pystray.Icon | None = None

    def _hwnd(self) -> int | None:
        try:
            return int(self.window.native.Handle.ToInt64())
        except Exception:
            return None

    def show(self, *_):
        try:
            _l, _t, r, b = _work_area()
            self.window.move(r - WIDTH - MARGIN, b - HEIGHT - MARGIN)
            self.window.show()
            self.visible = True
            self.shown_at = time.time()
            hwnd = self._hwnd()
            if hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception as e:
            print("flyout show failed:", e, flush=True)

    def hide(self, *_):
        try:
            self.window.hide()
        except Exception as e:
            print("flyout hide failed:", e, flush=True)
        self.visible = False

    def toggle(self, *_):
        self.hide() if self.visible else self.show()

    def quit(self, *_):
        if self.icon:
            self.icon.stop()
        self.on_quit()

    def _watch_focus(self):
        while True:
            time.sleep(0.3)
            if not self.visible or time.time() - self.shown_at < 1.0:
                continue
            hwnd = self._hwnd()
            if hwnd and ctypes.windll.user32.GetForegroundWindow() != hwnd:
                self.hide()

    def start(self, show_on_launch: bool = True):
        self.icon = pystray.Icon(
            "caesar-course-check",
            _icon_image(),
            "CAESAR Course Check",
            menu=pystray.Menu(
                pystray.MenuItem("Open", self.toggle, default=True),
                pystray.MenuItem("Quit", self.quit),
            ),
        )
        self.icon.run_detached()
        threading.Thread(target=self._watch_focus, daemon=True).start()
        if show_on_launch:
            threading.Timer(1.0, self.show).start()

    def notify(self, title: str, message: str):
        # pystray shows a Windows toast/balloon from the tray icon
        try:
            if self.icon:
                self.icon.notify(message, title)
        except Exception as e:
            print("tray notify failed:", e, flush=True)

    def set_tooltip(self, text: str):
        if self.icon:
            self.icon.title = text[:127]
