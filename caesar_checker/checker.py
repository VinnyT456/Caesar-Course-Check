"""Async Playwright monitor for CAESAR class enrollment.

Two browser modes share one account session:
  * sign_in()  -> HEADED Chrome on a persistent profile. The user solves the reCAPTCHA by hand (no CAESAR login).
                  The resulting cookies are saved to storage_state.json.
  * start()    -> HEADLESS Chrome using that saved state. If a login page or captcha shows up,
                  monitoring stops with status "needs_signin". Captchas are never solved automatically.
"""
from __future__ import annotations

import asyncio
import json
import re
import random
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from . import paths

URL = "https://search.caesar.northwestern.edu/psc/csnu/EMPLOYEE/SA/c/NUI_FRAMEWORK.PT_LANDINGPAGE.GBL?"
TIMEOUT = 15_000  # ms
CHROME_ARGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]
# Where "Open CAESAR" sends the user: the normal sign-in page (their own browser session, not the monitor's).
CAESAR_URL = "https://caesar.ent.northwestern.edu/psp/csnu/?&cmd=start"
TILE_ID = "win0divPTNUI_LAND_REC_GROUPLET$0"
CAPTCHA_SEL = 'iframe[src*="recaptcha"], iframe[title*="reCAPTCHA"], .g-recaptcha'


@dataclass
class ClassCfg:
    term: str = "5050"
    subject: str = "COMP_SCI"
    catalog_nbr: str = "340-0"
    class_nbr: str = ""  # specific section's class number; empty = first section listed
    seat_limit: int = 0  # alert when enrollment drops below this; 0 = auto (the class capacity: any open seat)


@dataclass
class Config:
    classes: list[ClassCfg] = field(default_factory=lambda: [ClassCfg()])
    interval: int = 60
    after_alert: str = "stop"  # stop | keep | repeat
    quiet_on: bool = False
    quiet_start: str = "23:00"
    quiet_end: str = "07:00"
    sound: str = "beep"  # beep | chime | bell | off
    volume: int = 60

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        data = dict(data)
        raw = data.get("classes")
        if not raw:  # old flat config: term/subject/catalog_nbr/class_nbr/seat_limit
            raw = [{k: data[k] for k in ClassCfg.__dataclass_fields__ if k in data}]
        classes = [ClassCfg(**{k: v for k, v in c.items() if k in ClassCfg.__dataclass_fields__}) for c in raw][:MAX_CLASSES]
        rest = {k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k != "classes"}
        return cls(classes=classes, **rest)

    @classmethod
    def load(cls) -> "Config":
        try:
            return cls.from_dict(json.loads(paths.config_path().read_text()))
        except Exception:
            return cls()

    def save(self) -> None:
        paths.config_path().write_text(json.dumps(asdict(self), indent=2))


def parse_hm(text: str) -> int | None:
    try:
        h, m = text.split(":")
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    return h * 60 + m if 0 <= h < 24 and 0 <= m < 60 else None


def quiet_end_ts(ts: float, start: str, end: str) -> float | None:
    """If ts falls inside the quiet window (it may wrap midnight), return when the window ends; else None."""
    s, e = parse_hm(start), parse_hm(end)
    if s is None or e is None or s == e:
        return None
    now = datetime.fromtimestamp(ts)
    m = now.hour * 60 + now.minute
    inside = s <= m < e if s < e else (m >= s or m < e)
    if not inside:
        return None
    end_dt = now.replace(hour=e // 60, minute=e % 60, second=0, microsecond=0)
    if end_dt <= now:
        end_dt += timedelta(days=1)
    return end_dt.timestamp()


def is_graduate(catalog_nbr: str) -> bool:
    """400-level and up is a graduate-school search ("340-0" -> 340 -> undergrad, "428-0" -> grad)."""
    digits = ""
    for ch in catalog_nbr.strip():
        if ch.isdigit():
            digits += ch
        else:
            break
    return bool(digits) and int(digits) >= 400


def pick_career(options: list[tuple[str, str]], grad: bool) -> str | None:
    """Pick the value of the School/Career option for undergraduate or graduate, matching on its label.

    CAESAR calls the graduate option "The Graduate School". Exact labels win over looser matches
    (e.g. "Kellogg Graduate School").
    """
    exact = ("the graduate school", "graduate school", "graduate") if grad else ("undergraduate",)
    for want in exact:
        for value, label in options:
            if label.strip().lower() == want:
                return value
    for value, label in options:
        low = label.lower()
        if grad and "graduate" in low and "undergrad" not in low:
            return value
        if not grad and "undergrad" in low:
            return value
    return None


def find_section(texts: list[str], class_nbr: str) -> int | None:
    """Index of the first result row whose text contains the class number as a whole number."""
    pat = re.compile(rf"(?<!\d){re.escape(class_nbr)}(?!\d)")
    for i, t in enumerate(texts):
        if pat.search(t):
            return i
    return None


MAX_CLASSES = 5
REPEAT_SECS = 300  # re-alert interval in 'repeat' mode
JITTER = 15  # seconds of random +/- added to each check interval


class NeedsSignIn(Exception):
    pass


def by_id(scope, element_id: str):
    # PeopleSoft ids contain "$", so use an attribute selector rather than "#id".
    return scope.locator(f'[id="{element_id}"]')


@dataclass
class ClassState:
    enrollment: Optional[int] = None
    capacity: Optional[int] = None
    waitlist: Optional[int] = None
    last_check: Optional[float] = None
    open: bool = False
    error: str = ""
    history: deque = field(default_factory=lambda: deque(maxlen=120))  # (timestamp, enrolled)


class Checker:
    def __init__(self, on_alert: Optional[Callable[..., None]] = None):
        self.config = Config.load()
        self.status = "idle"  # idle | signing_in | starting | monitoring | needs_signin | alert | error
        self.message = "Ready. If a captcha appears, solve it once in Chrome."
        self.cs: list[ClassState] = [ClassState() for _ in self.config.classes]
        self._no_cap = False
        self._no_wait = False
        self.next_check: Optional[float] = None
        self.quiet_until: Optional[float] = None
        self.alert_id = 0
        self._last_alert = 0.0
        self._acked = False
        self._fresh = False
        self._back_pending = False
        self._reached = False
        self.sections_stage: Optional[tuple[int, str]] = None  # (percent, text) while list_sections runs
        self._wanted = False  # user pressed Start and has not pressed Stop: resume after a captcha
        self.log: deque[str] = deque(maxlen=200)
        self._task: Optional[asyncio.Task] = None
        self._on_alert = on_alert  # on_alert(message, title="Seat available!")

    # ---- state ----
    def _primary(self) -> int:
        """The class the menu bar and header show: the first with a seat open, else the first."""
        for i, c in enumerate(self.cs):
            if c.open:
                return i
        return 0

    def snapshot(self) -> dict:
        p = self.cs[self._primary()]
        avail = lambda c: max(0, c.capacity - c.enrollment) if c.capacity is not None and c.enrollment is not None else None  # noqa: E731
        return {
            "status": self.status,
            "message": self.message,
            "enrollment": p.enrollment,
            "capacity": p.capacity,
            "available": avail(p),
            "classes": [
                {
                    "enrollment": c.enrollment, "capacity": c.capacity, "available": avail(c), "waitlist": c.waitlist,
                    "open": c.open, "error": c.error, "last_check": c.last_check, "history": list(c.history),
                    "limit": self._limit(i),
                }
                for i, c in enumerate(self.cs)
            ],
            "last_check": max((c.last_check for c in self.cs if c.last_check), default=None),
            "next_check": self.next_check,
            "sections": {"pct": self.sections_stage[0], "text": self.sections_stage[1]} if self.sections_stage else None,
            "quiet_until": self.quiet_until,
            "alert_id": self.alert_id,
            "signed_in": paths.storage_state_path().exists(),
            "busy": self.busy,
            "config": asdict(self.config),
            "log": list(self.log),
            "now": time.time(),
        }

    @property
    def busy(self) -> bool:
        return self._task is not None and not self._task.done()

    def _set(self, status: str, message: str) -> None:
        self.status, self.message = status, message
        self._log(message)

    def _log(self, line: str) -> None:
        entry = f"{time.strftime('%H:%M:%S')}  {line}"
        self.log.append(entry)
        print(entry, flush=True)  # the Activity tab is gone: app.log is where the history lives

    # ---- control ----
    def sign_in(self) -> bool:
        if self.busy:
            return False
        self._task = asyncio.create_task(self._guard(self._sign_in_then_resume()))
        return True

    async def _sign_in_then_resume(self) -> None:
        try:
            await self._sign_in()
        except BaseException:
            self._wanted = False  # Chrome closed or captcha timed out: don't start monitoring later by surprise
            raise
        if self._wanted:  # monitoring was on when the captcha came back: pick it up again
            self._log("Captcha solved. Resuming monitoring.")
            self._begin()

    def start(self, config: Config) -> bool:
        if self.busy:
            return False
        self.config = config
        config.save()
        self._wanted = True
        if not paths.storage_state_path().exists():
            self._log("Not verified yet: opening Chrome first, monitoring starts after the captcha.")
            self._task = asyncio.create_task(self._guard(self._sign_in_then_resume()))
            return True
        self._begin()
        return True

    def _begin(self) -> None:
        self.cs = [ClassState() for _ in self.config.classes]
        self._no_cap = False
        self._no_wait = False
        self._acked = False
        self._reached = False
        self.quiet_until = None
        self._task = asyncio.create_task(self._guard(self._monitor(), nudge=True))

    def ack(self) -> None:
        """The user saw the alert: stop repeating it."""
        self._acked = True

    async def stop(self) -> None:
        self._wanted = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self.next_check = None
        self.quiet_until = None
        if self.status not in ("alert", "needs_signin", "error"):
            self._set("idle", "Stopped.")

    async def _guard(self, coro, nudge: bool = False) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except NeedsSignIn as e:
            self.next_check = None
            self._set("needs_signin", str(e))
            if nudge and self._reached and self._on_alert:  # nudge: monitoring died, nobody is watching
                self._on_alert("Captcha expired. Open the app and solve it in Chrome; monitoring restarts by itself.", "Captcha needed")
        except Exception as e:  # noqa: BLE001
            self._wanted = False
            text = str(e)
            if "Executable doesn't exist" in text or "chrome" in text.lower() and "distribution" in text.lower():
                self._set("error", "Google Chrome was not found. Install Chrome, then try again.")
            else:
                self._set("error", f"{type(e).__name__}: {text.splitlines()[0] if text else ''}")

    # ---- sign in (headed) ----
    async def _sign_in(self) -> None:
        self._set("signing_in", "Chrome opened. Solve the captcha if one shows. It closes by itself once the page loads.")
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                str(paths.profile_dir()), channel="chrome", headless=False, args=CHROME_ARGS, no_viewport=True
            )
            try:
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                await page.goto(URL)
                deadline = time.time() + 15 * 60
                while time.time() < deadline:
                    if not ctx.pages:
                        raise NeedsSignIn("Chrome was closed before the captcha was solved.")
                    try:
                        if await by_id(page, TILE_ID).count():
                            await ctx.storage_state(path=str(paths.storage_state_path()))
                            self._set("idle", "Verified. Session saved. You can start monitoring.")
                            return
                    except Exception:
                        pass  # page navigating
                    await asyncio.sleep(1)
                raise NeedsSignIn("Captcha not solved within 15 minutes.")
            finally:
                await ctx.close()

    # ---- monitor (headless) ----
    def _label(self, i: int) -> str:
        c = self.config.classes[i]
        return f"{c.subject} {c.catalog_nbr}".strip()

    def _fire(self, message: str, title: str = "Seat available!") -> None:
        self.alert_id += 1
        self._last_alert = time.time()
        self._acked = False
        self._set("alert", message)
        if self._on_alert:
            self._on_alert(message, title)

    def _limit(self, i: int) -> Optional[int]:
        """Alert threshold for class i: the one the user set, else its real capacity (any open seat)."""
        limit, cap = self.config.classes[i].seat_limit, self.cs[i].capacity
        return min(limit, cap) if limit and cap else (limit or cap)

    def open_target(self) -> tuple[str, str]:
        """(label, class number) of the class a seat opened in, for the "Open CAESAR" button."""
        i = self._primary()
        return self._label(i), self.config.classes[i].class_nbr.strip()

    def _evaluate(self, i: int) -> None:
        """Compare one class against its alert threshold; fire on a closed->open change, or repeat if asked."""
        cs = self.cs[i]
        limit = self._limit(i)
        is_open = cs.enrollment is not None and limit is not None and cs.enrollment < limit
        multi = len(self.cs) > 1
        text = (f"{self._label(i)}: " if multi else "") + f"seat available! Enrollment is {cs.enrollment}."
        text = text[0].upper() + text[1:]
        if is_open and not cs.open:
            cs.open = True
            self._fire(text)
        elif is_open and self.config.after_alert == "repeat" and not self._acked and time.time() - self._last_alert >= REPEAT_SECS:
            self._fire(text)
        cs.open = is_open

    async def _monitor(self) -> None:
        self._set("starting", "Starting headless Chrome…")
        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(channel="chrome", headless=True, args=CHROME_ARGS)
            ctx: BrowserContext = await browser.new_context(storage_state=str(paths.storage_state_path()) if paths.storage_state_path().exists() else None)
            ctx.set_default_timeout(TIMEOUT)
            page = await ctx.new_page()
            try:
                self._fresh = False  # page already sits on this class's search results
                await self._open_search(page, self.config.classes[0])
                self._fresh = True
                self._back_pending = False
                self._set("monitoring", "Monitoring.")
                self._reached = True
                errors = 0
                while True:
                    cfg = self.config
                    qend = quiet_end_ts(time.time(), cfg.quiet_start, cfg.quiet_end) if cfg.quiet_on else None
                    if qend:
                        self.quiet_until = self.next_check = qend
                        self._set("monitoring", f"Quiet hours until {time.strftime('%H:%M', time.localtime(qend))}.")
                        await asyncio.sleep(max(1, qend - time.time()))
                        self.quiet_until = self.next_check = None
                        self._fresh, self._back_pending = False, False  # the session went stale overnight: search again
                        self._set("monitoring", "Monitoring.")
                        continue
                    failed = 0
                    for i in range(len(cfg.classes)):
                        try:
                            await self._check_class(page, i)
                        except (NeedsSignIn, asyncio.CancelledError):
                            raise
                        except Exception as e:  # noqa: BLE001
                            failed += 1
                            msg = str(e).splitlines()[0] if str(e) else type(e).__name__
                            self.cs[i].error = msg
                            self._fresh, self._back_pending = False, False  # page state unknown: search again next time
                            self._log(f"Error ({self._label(i)}): {msg}")
                    if failed == len(cfg.classes):
                        errors += 1
                        await self._raise_if_challenged(page)
                        await asyncio.sleep(10)
                        if errors >= 3:  # page state is probably lost: redo the search from scratch
                            self._log("Re-running search from the start…")
                            await self._open_search(page, cfg.classes[0])
                            self._fresh, self._back_pending, errors = True, False, 0
                        continue
                    errors = 0
                    if any(c.open for c in self.cs):
                        if cfg.after_alert == "stop":
                            self.next_check = None
                            self._wanted = False
                            return
                    elif self.status == "alert":
                        self._set("monitoring", "Monitoring.")
                    wait = max(5, cfg.interval + random.randint(-JITTER, JITTER))
                    self.next_check = time.time() + wait
                    await asyncio.sleep(wait)
                    self.next_check = None
            finally:
                await browser.close()

    async def _check_class(self, page: Page, i: int) -> None:
        cfg = self.config
        c = cfg.classes[i]
        if len(cfg.classes) > 1:
            if not (self._fresh and i == 0):
                await self._open_search(page, c)  # several classes: every read starts a fresh search
                await self._raise_if_challenged(page)
        elif self._back_pending:
            await by_id(page, "CLASS_SRCH_WRK2_SSR_PB_BACK").evaluate("el => el.click()")
            await asyncio.sleep(3)
            await self._raise_if_challenged(page)
        elif not self._fresh:
            await self._open_search(page, c)
            await self._raise_if_challenged(page)
        self._fresh = False
        self._back_pending = True
        enrolled, cap, wait = await self._read_enrollment(page, c)
        cs = self.cs[i]
        now = time.time()
        cs.enrollment, cs.waitlist, cs.last_check, cs.error = enrolled, wait, now, ""
        cs.history.append((now, enrolled))
        if cap is not None:
            if c.seat_limit > cap:  # a threshold above the class size would alert on a full class: pull it down
                self._log(f"{self._label(i)}: alert below {c.seat_limit} is above the class size, set to {cap}")
                c.seat_limit = cap
                cfg.save()
            elif cs.capacity is None:
                self._log(f"{self._label(i)}: capacity {cap}, alerting when enrollment drops below {c.seat_limit or cap}")
            cs.capacity = cap
        self._log(f"{self._label(i)}: enrollment {enrolled}" + (f" / {cap}" if cap is not None else "") + (f", waitlist {wait}" if wait is not None else ""))
        self._evaluate(i)

    async def _raise_if_challenged(self, page: Page) -> None:
        captcha = page.locator(CAPTCHA_SEL)
        if await captcha.count() and await captcha.first.is_visible():
            raise NeedsSignIn("Captcha appeared. Solve it in Chrome, then start again.")
        # Redirected to a login page: the landing tile and the search frame are both missing.
        if await by_id(page, TILE_ID).count() == 0 and await page.locator("#main_target_win0").count() == 0:
            raise NeedsSignIn("Verification needed. Solve the captcha, then start again.")

    async def _open_search(self, page: Page, c: ClassCfg) -> None:
        await page.goto(URL)
        tile = by_id(page, TILE_ID)
        try:
            await tile.wait_for(state="attached", timeout=TIMEOUT)
        except Exception:
            await self._raise_if_challenged(page)
            raise NeedsSignIn("Landing page did not load. Try solving the captcha again.")
        await tile.evaluate("el => el.click()")

        frame = page.frame_locator("#main_target_win0")
        await by_id(frame, "CLASS_SRCH_WRK2_STRM$35$").select_option(c.term)
        await asyncio.sleep(2)  # PeopleSoft reloads the form after the term changes
        await self._select_career(frame, is_graduate(c.catalog_nbr))
        await by_id(frame, "SSR_CLSRCH_WRK_SUBJECT_SRCH$0").select_option(c.subject)
        await by_id(frame, "SSR_CLSRCH_WRK_CATALOG_NBR$1").fill(c.catalog_nbr)
        await by_id(frame, "SSR_CLSRCH_WRK_SSR_OPEN_ONLY$3").evaluate("el => el.click()")
        await by_id(frame, "CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH").evaluate("el => el.click()")

    async def _select_career(self, frame, grad: bool) -> None:
        """Switch the School (career) dropdown to Graduate for 400+ courses, Undergraduate otherwise."""
        sel = frame.locator('select[id^="SSR_CLSRCH_WRK_ACAD_CAREER"]').first
        try:
            if await sel.count() == 0:
                self._log("School dropdown not found; leaving the default.")
                return
            options = await sel.evaluate("el => [...el.options].map(o => [o.value, o.text.trim()])")
            value = pick_career([(v, t) for v, t in options], grad)
            if value is None:
                self._log(f"No {'Graduate' if grad else 'Undergraduate'} option in the School dropdown: {[t for _, t in options]}")
                return
            await sel.select_option(value)
            self._log(f"School set to {'Graduate' if grad else 'Undergraduate'}.")
            await asyncio.sleep(2)  # the form reloads after the career changes (and so does the subject list)
        except Exception as e:  # noqa: BLE001
            self._log(f"Could not set School: {str(e).splitlines()[0] if str(e) else type(e).__name__}")

    async def list_sections(self, c: ClassCfg) -> list[dict]:
        """Every section CAESAR lists for a course (lectures, discussions, labs), read live in a throwaway headless Chrome."""
        if self.busy:
            raise RuntimeError("Stop monitoring first, then load the sections.")
        if not paths.storage_state_path().exists():
            raise NeedsSignIn("Verify with CAESAR first (Not verified, top right).")
        self._log(f"Loading sections for {c.subject} {c.catalog_nbr}")
        self.sections_stage = (8, "Starting Chrome")
        try:
            return await self._list_sections(c)
        finally:
            self.sections_stage = None

    async def _list_sections(self, c: ClassCfg) -> list[dict]:
        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(channel="chrome", headless=True, args=CHROME_ARGS)
            try:
                self.sections_stage = (22, "Opening CAESAR")
                ctx = await browser.new_context(storage_state=str(paths.storage_state_path()))
                ctx.set_default_timeout(30_000)
                page = await ctx.new_page()
                await self._open_search(page, c)
                self.sections_stage = (60, "Searching classes. CAESAR can be slow")
                frame = page.frame_locator("#main_target_win0")
                try:
                    await by_id(frame, "MTG_CLASSNAME$0").wait_for(state="attached", timeout=60_000)  # big or busy searches (CHEM) can take well over 15 s
                except Exception:  # noqa: BLE001
                    await self._raise_if_challenged(page)
                    raise RuntimeError("No classes came back for this search. Check the course number.")
                self.sections_stage = (88, "Reading sections")
                raw = await frame.locator("body").evaluate("""body => {
                    const out = []; let course = ''
                    const clean = (el) => el ? el.innerText.replace(/\\s+/g, ' ').trim() : ''
                    const get = (name, i) => body.querySelector('[id="' + name + '$' + i + '"]')
                    for (const el of body.querySelectorAll('[id^="win0divSSR_CLSRSLT_WRK_GROUPBOX2GP$"], [id^="MTG_CLASSNAME$"]')) {
                        if (el.id.startsWith('win0div')) { course = clean(el); continue }
                        if (el.id.includes('span')) continue
                        const i = el.id.split('$')[1]
                        out.push({ course, head: clean(el), id: clean(get('MTG_CLASS_NBR', i)), when: clean(get('MTG_DAYTIME', i)), room: clean(get('MTG_ROOM', i)), who: clean(get('MTG_INSTR', i)) })
                    }
                    return out
                }""")
                first = lambda t: re.split(r"(?<=[AP]M)\s+(?=[A-Z][a-z])", t, maxsplit=1)[0] if t else t  # noqa: E731
                want = f"{c.subject.replace('_', ' ')} {c.catalog_nbr}".upper()
                rows = []
                for r in raw:
                    if not r["id"] or not r["course"].upper().replace("_", " ").startswith(want + " "):
                        continue  # the search also returns other courses whose number contains this one
                    sec = r["head"].split()[0] if r["head"] else ""
                    rows.append({"id": r["id"], "sec": sec, "comp": sec.rsplit("-", 1)[-1] if "-" in sec else "", "when": first(r["when"]), "room": r["room"], "who": r["who"]})
                self._log(f"Found {len(rows)} sections for {c.subject} {c.catalog_nbr}")
                return rows
            finally:
                await browser.close()

    async def _open_section(self, frame, cfg: ClassCfg) -> None:
        """Open the class detail: the chosen section if one is set, else the first row."""
        want = cfg.class_nbr.strip()
        if not want:
            await by_id(frame, "MTG_CLASSNAME$0").evaluate("el => el.click()")
            return
        # The results load after the search click: wait for the first row before counting rows.
        try:
            await by_id(frame, "MTG_CLASSNAME$0").wait_for(state="attached", timeout=TIMEOUT)
        except Exception:  # noqa: BLE001
            raise RuntimeError("No classes came back for this search. Check the course number.")
        texts: list[str] = []
        for i in range(60):  # result rows are MTG_CLASSNAME$0, $1, ...
            row = by_id(frame, f"MTG_CLASSNAME${i}")
            if await row.count() == 0:
                break
            texts.append(await row.inner_text())
            nbr = by_id(frame, f"MTG_CLASS_NBR${i}")
            if await nbr.count():
                texts[-1] += " " + await nbr.inner_text()
        idx = find_section(texts, want)
        if idx is None:
            self._log(f"Section {want} not among {len(texts)} rows: {[x[:40] for x in texts[:5]]}")
            raise RuntimeError(f"Section {want} isn't in the search results.")
        await by_id(frame, f"MTG_CLASSNAME${idx}").evaluate("el => el.click()")

    async def _read_enrollment(self, page: Page, c: ClassCfg) -> tuple[int, Optional[int], Optional[int]]:
        """Return (enrolled, capacity, waitlist). Capacity and waitlist are None if the page doesn't show them."""
        frame = page.frame_locator("#main_target_win0")
        await self._open_section(frame, c)
        enrolled = int((await by_id(frame, "SSR_CLS_DTL_WRK_ENRL_TOT").inner_text()).strip())
        cap: Optional[int] = None
        if not self._no_cap:
            try:
                cap = int((await by_id(frame, "SSR_CLS_DTL_WRK_ENRL_CAP").inner_text(timeout=3000)).strip())
            except Exception:  # noqa: BLE001 - capacity is best-effort
                self._no_cap = True  # don't pay the timeout every loop
                self._log("Couldn't read class capacity; set 'Alert below' on the Alerts tab.")
        wait: Optional[int] = None
        if not self._no_wait:
            try:
                wait = int((await by_id(frame, "SSR_CLS_DTL_WRK_WAIT_TOT").inner_text(timeout=1500)).strip())
            except Exception:  # noqa: BLE001 - waitlist is best-effort
                self._no_wait = True
                self._log("Couldn't read the waitlist count.")
        return enrolled, cap, wait
