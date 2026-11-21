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
import random
import time
from collections import deque
from dataclasses import asdict, dataclass
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
TILE_ID = "win0divPTNUI_LAND_REC_GROUPLET$0"
CAPTCHA_SEL = 'iframe[src*="recaptcha"], iframe[title*="reCAPTCHA"], .g-recaptcha'


@dataclass
class Config:
    term: str = "5050"
    subject: str = "COMP_SCI"
    catalog_nbr: str = "340-0"
    seat_limit: int = 150
    interval: int = 60

    @classmethod
    def load(cls) -> "Config":
        try:
            data = json.loads(paths.config_path().read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()

    def save(self) -> None:
        paths.config_path().write_text(json.dumps(asdict(self), indent=2))


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


JITTER = 15  # seconds of random +/- added to each check interval


class NeedsSignIn(Exception):
    pass


def by_id(scope, element_id: str):
    # PeopleSoft ids contain "$", so use an attribute selector rather than "#id".
    return scope.locator(f'[id="{element_id}"]')


class Checker:
    def __init__(self, on_alert: Optional[Callable[[str], None]] = None):
        self.config = Config.load()
        self.status = "idle"  # idle | signing_in | starting | monitoring | needs_signin | alert | error
        self.message = "Ready. If a captcha appears, solve it once in Chrome."
        self.enrollment: Optional[int] = None
        self._no_cap = False
        self.capacity: Optional[int] = None  # read from the class page on the first check
        self.last_check: Optional[float] = None
        self.next_check: Optional[float] = None
        self.alert_id = 0
        self.log: deque[str] = deque(maxlen=200)
        self._task: Optional[asyncio.Task] = None
        self._on_alert = on_alert

    # ---- state ----
    def snapshot(self) -> dict:
        return {
            "status": self.status,
            "message": self.message,
            "enrollment": self.enrollment,
            "capacity": self.capacity,
            "available": (self.capacity - self.enrollment) if self.capacity is not None and self.enrollment is not None else None,
            "last_check": self.last_check,
            "next_check": self.next_check,
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
        self.log.append(f"{time.strftime('%H:%M:%S')}  {line}")

    # ---- control ----
    def sign_in(self) -> bool:
        if self.busy:
            return False
        self._task = asyncio.create_task(self._guard(self._sign_in()))
        return True

    def start(self, config: Config) -> bool:
        if self.busy:
            return False
        self.config = config
        config.save()
        self.enrollment = None
        self.capacity = None
        self._no_cap = False
        self._task = asyncio.create_task(self._guard(self._monitor()))
        return True

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self.next_check = None
        if self.status not in ("alert", "needs_signin", "error"):
            self._set("idle", "Stopped.")

    async def _guard(self, coro) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except NeedsSignIn as e:
            self._set("needs_signin", str(e))
        except Exception as e:  # noqa: BLE001
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
    async def _monitor(self) -> None:
        self._set("starting", "Starting headless Chrome…")
        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(channel="chrome", headless=True, args=CHROME_ARGS)
            ctx: BrowserContext = await browser.new_context(storage_state=str(paths.storage_state_path()) if paths.storage_state_path().exists() else None)
            ctx.set_default_timeout(TIMEOUT)
            page = await ctx.new_page()
            try:
                await self._open_search(page)
                self._set("monitoring", "Monitoring.")
                errors = 0
                while True:
                    try:
                        enrolled, cap = await self._read_enrollment(page)
                        errors = 0
                        self.enrollment, self.last_check = enrolled, time.time()
                        if cap is not None and self.capacity is None:
                            # First look at the class page: alert below the real capacity, not a typed guess.
                            self.capacity = cap
                            self.config.seat_limit = cap
                            self.config.save()
                            self._log(f"Capacity {cap}: alerting when enrollment drops below {cap}")
                        elif cap is not None:
                            self.capacity = cap
                        self._log(f"Enrollment: {enrolled}" + (f" / {cap}" if cap is not None else ""))
                        if enrolled < self.config.seat_limit:
                            self.alert_id += 1
                            self.next_check = None
                            self._set("alert", f"Seat available! Enrollment is {enrolled}.")
                            if self._on_alert:
                                self._on_alert(self.message)
                            return
                        wait = max(5, self.config.interval + random.randint(-JITTER, JITTER))
                        self.next_check = time.time() + wait
                        await asyncio.sleep(wait)
                        self.next_check = None
                        await by_id(page, "CLASS_SRCH_WRK2_SSR_PB_BACK").evaluate("el => el.click()")
                        await asyncio.sleep(3)
                        await self._raise_if_challenged(page)
                    except (NeedsSignIn, asyncio.CancelledError):
                        raise
                    except Exception as e:  # noqa: BLE001
                        errors += 1
                        self._log(f"Error: {str(e).splitlines()[0] if str(e) else type(e).__name__}")
                        await self._raise_if_challenged(page)
                        await asyncio.sleep(10)
                        if errors >= 3:  # page state is probably lost: redo the search from scratch
                            self._log("Re-running search from the start…")
                            await self._open_search(page)
                            errors = 0
            finally:
                await browser.close()

    async def _raise_if_challenged(self, page: Page) -> None:
        captcha = page.locator(CAPTCHA_SEL)
        if await captcha.count() and await captcha.first.is_visible():
            raise NeedsSignIn("Captcha appeared. Solve it in Chrome, then start again.")
        # Redirected to a login page: the landing tile and the search frame are both missing.
        if await by_id(page, TILE_ID).count() == 0 and await page.locator("#main_target_win0").count() == 0:
            raise NeedsSignIn("Verification needed. Solve the captcha, then start again.")

    async def _open_search(self, page: Page) -> None:
        c = self.config
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

    async def _read_enrollment(self, page: Page) -> tuple[int, Optional[int]]:
        """Return (enrolled, capacity). Capacity is None if the page doesn't show it."""
        frame = page.frame_locator("#main_target_win0")
        await by_id(frame, "MTG_CLASSNAME$0").evaluate("el => el.click()")
        text = await by_id(frame, "SSR_CLS_DTL_WRK_ENRL_TOT").inner_text()
        cap: Optional[int] = None
        if self._no_cap:
            return int(text.strip()), None
        try:
            cap_text = await by_id(frame, "SSR_CLS_DTL_WRK_ENRL_CAP").inner_text(timeout=3000)
            cap = int(cap_text.strip())
        except Exception:  # noqa: BLE001 - capacity is best-effort
            self._no_cap = True  # don't pay the timeout every loop
            self._log("Couldn't read class capacity; using the 'Alert below' number.")
        return int(text.strip()), cap
