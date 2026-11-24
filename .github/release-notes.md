## CAESAR Course Check

A menu-bar / system-tray app that watches a Northwestern CAESAR class and alerts you the moment a seat opens.

### What's in this release
- Lives in the **macOS menu bar** (Windows system tray); click the icon to open the popover. No main window, no Dock icon.
- Headless Chrome (Playwright) checks enrollment about once a minute and alerts with a sound and a notification when a seat opens.
- **Dropdowns** for term, subject and course, built from the scraped catalog (2027 Winter).
- Reads the class capacity on the first check and shows enrolled / capacity and seats open.
- Catalog numbers 400+ switch CAESAR's School to **The Graduate School** automatically.
- **Searchable** subject and course lists, with every school's own subjects (CHEM in Weinberg and SPS both show).
- **Discussions and labs:** load every section CAESAR lists for a course and monitor any of them.
- **Up to five classes**, per-class alert thresholds, waitlist count, enrollment history, quiet hours, sound picker, repeat alerts.
- **One-click first run** (Verify and start) and **automatic restart** after a captcha.
- Light and dark mode.

### Download
- **macOS (Apple Silicon):** `CAESAR-Course-Check.dmg`. Open it and drag the app to Applications.
- **Windows 10/11:** `CAESAR Course Check.exe`.

Requires **Google Chrome**. Builds are **unsigned**:
- macOS: right-click the app → **Open**, or run `xattr -dr com.apple.quarantine "/Applications/CAESAR Course Check.app"`.
- Windows: SmartScreen → **More info → Run anyway**.

### Known limitations
- **Windows is untested.** The tray icon, flyout and `.exe` were built by CI but have never been run on a real Windows machine.
- CAESAR shows a reCAPTCHA. The app never solves it: click **Solve captcha in Chrome** and solve it by hand once; the session is saved.
- The School dropdown and class-capacity field IDs are unconfirmed against the live CAESAR page. If either isn't found, the Activity log says so and the app falls back to the default School and your typed "Alert below" number.
- The macOS build is Apple Silicon only.
