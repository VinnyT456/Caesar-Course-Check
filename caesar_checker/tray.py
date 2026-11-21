"""macOS menu bar item: NSStatusItem + NSPopover hosting a compact web view of the app UI.

HIG: popover transient (closes on outside click), sized to its content, one at a time.
Must be created and used on the Cocoa main thread.
"""
from __future__ import annotations

import os

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSImage,
    NSMenu,
    NSMenuItem,
    NSPopover,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSViewController,
)
from Foundation import NSMakeRect, NSObject, NSTimer, NSURL, NSURLRequest
from WebKit import WKWebView, WKWebViewConfiguration

# Icon is an SF Symbol (template image, adapts to light/dark menu bars). Title only when informative.
TITLES = {"needs_signin": " Captcha", "alert": " Seat open!", "error": " Error"}
POPOVER_SIZE = (340, 520)
NSMinYEdge = 1
NSPopoverBehaviorTransient = 1


class _Controller(NSObject):
    def initWithState_url_(self, state, url):
        self = objc.super(_Controller, self).init()
        self.state = state
        self.url = url
        self._ticked = False

        self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        btn = self.item.button()
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_("graduationcap.fill", "CAESAR Course Check")
        self.has_icon = img is not None
        if img is not None:
            img.setTemplate_(True)
            btn.setImage_(img)
        else:
            btn.setTitle_("CAESAR")
        btn.setTarget_(self)
        btn.setAction_("toggle:")

        w, h = POPOVER_SIZE
        self.web = WKWebView.alloc().initWithFrame_configuration_(NSMakeRect(0, 0, w, h), WKWebViewConfiguration.alloc().init())
        self.web.setValue_forKey_(False, "drawsBackground")  # no white flash before the page paints
        self.web.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(url + "/?view=popover")))
        vc = NSViewController.alloc().init()
        vc.setView_(self.web)
        self.popover = NSPopover.alloc().init()
        self.popover.setContentViewController_(vc)
        self.popover.setContentSize_((w, h))
        self.popover.setBehavior_(NSPopoverBehaviorTransient)
        self.popover.setAnimates_(True)

        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(2.0, self, "tick:", None, True)
        return self

    def toggle_(self, _):
        if self.popover.isShown():
            self.popover.performClose_(None)
        else:
            self.showPopover()

    def showPopover(self):
        btn = self.item.button()
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.popover.showRelativeToRect_ofView_preferredEdge_(btn.bounds(), btn, NSMinYEdge)
        print("tray: popover shown =", bool(self.popover.isShown()), flush=True)

    def closePopover(self):
        if self.popover.isShown():
            self.popover.performClose_(None)

    def tick_(self, _):
        s = self.state()
        if s is None:
            return
        st = s["status"]
        if st == "monitoring":
            title = f" {s['enrollment']}" if s["enrollment"] is not None else ""
        else:
            title = TITLES.get(st, "")
        if not self.has_icon and not title:
            title = "CAESAR"
        self.item.button().setTitle_(title)
        if not self._ticked:
            self._ticked = True
            print("tray: first tick ok, icon =", self.has_icon, flush=True)


_keep: list = []
_authorized: bool | None = None  # None until macOS answers the permission request


class _NoteDelegate(NSObject):
    """Show banners even while the app is frontmost (e.g. popover open)."""

    def userNotificationCenter_willPresentNotification_withCompletionHandler_(self, center, note, handler):
        import UserNotifications as UN

        handler(UN.UNNotificationPresentationOptionBanner | UN.UNNotificationPresentationOptionSound | UN.UNNotificationPresentationOptionList)


def request_notifications() -> None:
    """Ask for notification permission (a one-time system prompt) and install the delegate."""
    try:
        import UserNotifications as UN

        center = UN.UNUserNotificationCenter.currentNotificationCenter()
        delegate = _NoteDelegate.alloc().init()
        center.setDelegate_(delegate)
        _keep.append(delegate)

        def done(granted, error):
            global _authorized
            _authorized = bool(granted)
            print("notifications: granted =", bool(granted), "error =", error, flush=True)

        center.requestAuthorizationWithOptions_completionHandler_(
            UN.UNAuthorizationOptionAlert | UN.UNAuthorizationOptionSound, done
        )
    except Exception as e:
        print("notifications: unavailable:", e, flush=True)


def notify(title: str, message: str) -> bool:
    """Post a native notification attributed to this app. Returns False if the framework is unavailable."""
    if _authorized is False:  # macOS refused: a posted request would be silently dropped
        print("notifications: not authorized, using fallback", flush=True)
        return False
    try:
        import uuid

        import UserNotifications as UN

        center = UN.UNUserNotificationCenter.currentNotificationCenter()
        content = UN.UNMutableNotificationContent.alloc().init()
        content.setTitle_(title)
        content.setBody_(message)
        content.setSound_(UN.UNNotificationSound.defaultSound())
        req = UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(str(uuid.uuid4()), content, None)

        def done(error):
            print("notifications: posted, error =", error, flush=True)

        center.addNotificationRequest_withCompletionHandler_(req, done)
        return True
    except Exception as e:
        print("notifications: post failed:", e, flush=True)
        return False


def _install_edit_menu() -> None:
    """Menu-bar-only apps have no main menu, so Cmd+C/V/X/A/Z beep in text fields. Add an Edit menu."""
    app = NSApplication.sharedApplication()
    main = NSMenu.alloc().init()
    holder = NSMenuItem.alloc().init()
    main.addItem_(holder)
    edit = NSMenu.alloc().initWithTitle_("Edit")
    for title, sel, key in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"),
                            ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")]:
        edit.addItemWithTitle_action_keyEquivalent_(title, sel, key)
    holder.setSubmenu_(edit)
    app.setMainMenu_(main)
    _keep.extend([main, holder, edit])


def install(state, url: str, show_on_launch: bool = False) -> None:
    # Accessory policy = menu bar only, no Dock icon.
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    _install_edit_menu()
    request_notifications()
    c = _Controller.alloc().initWithState_url_(state, url)
    _keep.append(c)  # keep alive
    print("tray: installed", flush=True)
    if show_on_launch or os.environ.get("CAESAR_DEBUG_POPOVER") == "1":
        NSTimer.scheduledTimerWithTimeInterval_repeats_block_(0.8, False, lambda _t: c.showPopover())


def show_popover() -> None:
    if _keep:
        _keep[0].showPopover()


def close_popover() -> None:
    if _keep:
        _keep[0].closePopover()
