# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

## Stack
Python (FastAPI + async Playwright) backend; Svelte + Vite UI; macOS menu bar popover (pyobjc NSStatusItem/NSPopover) and Windows tray flyout (pystray + pywebview). Packaged with PyInstaller (.app/.dmg, .exe).

## Users
A Northwestern student, and friends they share it with, watching a full class on CAESAR for a seat to open. Used as short glances during study, day or late night: click the tray icon, read the number, close.

## Product Purpose
Poll a CAESAR class's enrollment headlessly and alert the moment a seat opens, so the student does not have to refresh CAESAR by hand. Success: the student catches the seat; the app costs almost no attention until then.

## Positioning
Lives in the menu bar / tray instead of a window, and runs headless on a saved session after the user solves CAESAR's reCAPTCHA by hand once (no CAESAR login is involved). It never solves captchas.

## Constraints
- Popover/flyout about 420x640 or smaller; one screen, no navigation depth.
- Must read at a glance: status, enrolled count vs alert threshold, next check.
- Light and dark mode both required (follows OS).
- Northwestern purple (#4E2A84) is the one brand commitment.
- Unsigned builds; no network assets (offline fonts: system stacks only).
