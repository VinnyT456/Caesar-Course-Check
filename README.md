<p align="center"><img src="docs/icon.png" width="128" alt="CAESAR Course Check icon"></p>

# CAESAR Course Check

A small app that watches a Northwestern CAESAR class and alerts you the moment a seat opens.
On **macOS** it lives in the menu bar: click the icon and the whole app opens as a popover. On **Windows** it is a normal app window you can minimise.

**[⬇ Download the latest version](https://github.com/VinnyT456/Caesar-Course-Check/releases/latest)** (macOS `.dmg` or Windows `.exe`, listed under **Assets** on the release page). Setup steps are in [Install](#install).

| First run (light) | Monitoring (light) | Alert settings (light) | Seat found (dark) |
|---|---|---|---|
| ![First run](docs/screenshot-signin.png) | ![Monitoring](docs/screenshot-monitoring.png) | ![Alert settings](docs/screenshot-alerts.png) | ![Seat available](docs/screenshot-alert.png) |

> Screenshots use sample data and a browser render of the popover; the menu bar itself isn't pictured; Windows shows the same layout in a regular window.

## Design
Theme: **Purple Line wayfinding**, after the CTA Purple Line out of Evanston. A saturated Northwestern-purple header band, a course roundel, state as station bullets, and a route strip whose "train" is the time since the last check. Light mode is the daytime platform, dark mode the night platform.

## Features
- Checks enrollment about once a minute (a random ±15 s jitter is added) in a **headless** Chrome.
- Alerts with a sound, a macOS notification and by opening the popover when a seat opens, meaning enrollment drops below the class capacity.
- **Searchable dropdowns** for subject and course, built from the scraped course catalog: click and type ("comp sci", "machine") to filter. Subjects are listed under their own school, so a code that exists in two schools (like CHEM in Weinberg and SPS) shows both. Each list has an "Other…" option if you want to type your own.
- **One-click first run:** the button says **Verify and start** until you've solved the captcha once. It opens Chrome, and monitoring begins by itself afterwards. If the captcha comes back later you get a notification, and solving it restarts monitoring with your last settings.
- **Watch one section:** if a course has several sections, pick the one you want (days, time and instructor are listed) or leave it on "Any section".
- **Discussions and labs:** press "Load discussions & labs" under Section to list every section CAESAR has for the course (lectures, discussions, labs, with times and instructors), then pick one. A progress bar shows the search (big courses can take up to a minute). Needs a verified session and no monitoring running.
- **Watch up to five classes** at once. Each gets a chip on the Class tab; a green dot marks the one with a seat open. More classes means more page loads per round, so expect captchas a little more often.
- **After an alert:** stop, keep watching, or re-alert every 5 minutes until you open CAESAR or stop.
- **Sound and volume:** beep, chime, bell or off, with a volume slider (the slider affects the in-app sound; "Off" also silences the notification).
- **Quiet hours:** pause checks overnight; they resume with a fresh search.
- **Enrollment history** graph beside the count, and the **waitlist** count when CAESAR shows it.
- **Menu bar colour:** the icon turns green when a seat is open and red when monitoring needs you (macOS). Clicking a notification opens CAESAR.
- **Shows open seats:** the first check reads the class capacity and the header shows enrolled / capacity and seats open. "Alert below" is on Auto (any open seat) unless you set a number; a number above the class size is lowered to the class size after the first check.
- **Graduate courses just work:** catalog numbers 400 and up switch CAESAR's School to The Graduate School automatically.
- **macOS:** lives in the menu bar, no main window and no Dock icon. A cap icon plus the live enrollment number shows while monitoring. Monitoring keeps running while the popover is closed.
- **Windows:** a standalone window. Minimise it to keep monitoring (closing the window quits the app). A seat opening brings the window forward, flashes the taskbar, plays a sound and shows a toast.
- Light and dark mode.

> **Windows status: untested.** The Windows app (`app.py`'s window path, toast and taskbar flash) has never run on a real Windows machine, and no `.exe` has been checked by hand. Please report anything odd.

## Requirements
- **Google Chrome** installed.
- macOS (the CI build is Apple Silicon only; build locally for Intel) or Windows 10/11.

## Install
**[Download the latest release](https://github.com/VinnyT456/Caesar-Course-Check/releases/latest)** and grab the file for your system from its **Assets** list:
- macOS: open `CAESAR-Course-Check.dmg`, drag the app to **Applications**.
- Windows: run `CAESAR Course Check.exe`.

Each release is built by GitHub Actions when a version tag (like `v0.2.0`) is pushed, so the Releases page always holds the newest build. If the page has no files yet, build it yourself (see **Build** below).

The builds are **unsigned**, so the first launch needs one extra step:
- macOS: right-click the app → **Open** (or `xattr -dr com.apple.quarantine "/Applications/CAESAR Course Check.app"`).
- Windows: SmartScreen → **More info → Run anyway**.

## How to use
1. Launch the app. On macOS click its icon in the menu bar (it does not open by itself); on Windows the window opens. Pick the term, subject and course.
2. Click **Start monitoring**. It checks headless in the background.
3. CAESAR shows a reCAPTCHA, so the first run stops with **Captcha needed**. Click **Solve captcha in Chrome**, solve it by hand in the visible window, and it closes by itself. The session is saved, so you only repeat this when the captcha comes back.
4. Click **Start monitoring** again. When enrollment drops below the threshold you get an alert and monitoring stops.

No CAESAR login is involved, only the captcha. The app never solves captchas for you, and headless browsing tends to trigger them more often than a normal window.

## Develop
```bash
uv sync
(cd frontend && npm install && npm run build)
uv run python run_app.py
```

Stack: Python + FastAPI (API), async Playwright (browser automation), Svelte + Vite (UI), pyobjc NSStatusItem/NSPopover (macOS), pywebview window (Windows), PyInstaller (packaging).

```
caesar_checker/   backend: checker.py (Playwright), server.py (FastAPI), app.py (window), tray.py (macOS menu bar popover)
frontend/         Svelte UI, built into caesar_checker/static
packaging/        PyInstaller build, icon + DMG artwork (.app + .dmg on macOS, .exe on Windows)
scraper/          scrapes class-descriptions.northwestern.edu into data/; build_catalog.py writes caesar_checker/catalog.json (the dropdown data)
data/             scraped course catalog (JSON per school/subject)
scripts/          course_pw.py, the original standalone terminal checker
assets/ docs/     app icon / DMG art, README screenshots
run_app.py        app entry point (also the PyInstaller entry)
```

## Build
Icon and DMG artwork are generated by `packaging/make_icon.py` into `assets/` (the build runs it for you). The macOS build is a menu-bar-only `.app` (no Dock icon), ad-hoc signed, packed into a DMG with a drag-to-Applications layout.

```bash
uv run python packaging/build.py
```
- macOS → `dist/CAESAR-Course-Check.dmg`
- Windows → `dist/CAESAR Course Check.exe` (or run `packaging\build_windows.bat`)

PyInstaller can't cross-compile, so build the Windows `.exe` on Windows or with the included GitHub Actions workflow (`.github/workflows/build.yml`).

## Course catalog
The dropdowns read `caesar_checker/catalog.json`, which is built from the scraper's output in `data/`. To refresh it for a new term:

```bash
uv run python scraper/main.py            # scrape class-descriptions.northwestern.edu into data/ (slow)
uv run python scraper/build_catalog.py   # rebuild caesar_checker/catalog.json, then rebuild the app
```

> The School dropdown, the class-capacity field and the waitlist count use PeopleSoft element IDs that haven't been confirmed against the live CAESAR page. If one isn't found, the app logs it (see `app.log`) and falls back: the default School, your "Alert below" number, and no waitlist figure.

## Where data is stored
Session, saved settings and logs live in the per-user data folder `CaesarCourseCheck`
(`~/Library/Application Support/` on macOS, `%LOCALAPPDATA%` on Windows). Delete it to forget the saved captcha session.

## License
[MIT](LICENSE)
