import os
import random
import signal
import time

from plyer import notification
from playwright.sync_api import Page, sync_playwright
from tqdm import tqdm

URL = "https://search.caesar.northwestern.edu/psc/csnu/EMPLOYEE/SA/c/NUI_FRAMEWORK.PT_LANDINGPAGE.GBL?"
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pw-profile")
TERM = "5050"
SUBJECT = "COMP_SCI"
CATALOG_NBR = "340-0"
SEAT_LIMIT = 150
TIMEOUT = 10_000  # ms


def by_id(scope, element_id: str):
    # PeopleSoft ids contain "$", so use an attribute selector instead of "#id".
    return scope.locator(f'[id="{element_id}"]')


class CaesarChecker:
    def __init__(self):
        self.hide_requested = os.environ.get("CAESAR_HIDE") == "1"
        self.hidden = False
        signal.signal(signal.SIGUSR1, lambda *_: setattr(self, "hide_requested", True))

    def maybe_hide(self, page: Page):
        """Minimize via CDP. Playwright has no public minimize API."""
        if not self.hide_requested or self.hidden:
            return
        cdp = page.context.new_cdp_session(page)
        win = cdp.send("Browser.getWindowForTarget")
        cdp.send(
            "Browser.setWindowBounds",
            {"windowId": win["windowId"], "bounds": {"windowState": "minimized"}},
        )
        self.hidden = True
        print("Browser minimized. Not true headless.")

    def wait_for_human(self, page: Page):
        """If a reCAPTCHA / login challenge is showing, pause until the user clears it.

        Never auto-solve. Solve it by hand in the browser window.
        """
        challenge = page.locator(
            'iframe[src*="recaptcha"], iframe[title*="reCAPTCHA"], .g-recaptcha'
        )
        if challenge.count() == 0 or not challenge.first.is_visible():
            return
        print("CAPTCHA detected. Solve it in the browser window...")
        notification.notify(
            title="CAESAR Checker",
            message="CAPTCHA needs you. Solve it in the browser.",
            app_name="CAESAR Checker",
            timeout=10,
        )
        os.system("afplay /System/Library/Sounds/Ping.aiff")
        # Un-minimize if we hid the window, so user can see it.
        self.hidden = False
        self.hide_requested = False
        while challenge.count() and challenge.first.is_visible():
            time.sleep(1)
        print("CAPTCHA cleared, continuing.")

    def run(self):
        with sync_playwright() as p:
            # Persistent profile keeps cookies/SSO session so captcha/login is rarer.
            ctx = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                headless=False,
                args=[
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ],
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(TIMEOUT)
            page.goto(URL)

            # Login (SSO/Duo) and captcha are manual: wait up to ~3h for landing tile.
            tile = by_id(page, "win0divPTNUI_LAND_REC_GROUPLET$0")
            while True:
                self.wait_for_human(page)
                try:
                    tile.wait_for(state="attached", timeout=2000)
                    break
                except Exception:
                    pass
            tile.evaluate("el => el.click()")

            frame = page.frame_locator("#main_target_win0")

            by_id(frame, "CLASS_SRCH_WRK2_STRM$35$").select_option(TERM)
            time.sleep(2)  # PeopleSoft reloads the form after term change
            by_id(frame, "SSR_CLSRCH_WRK_SUBJECT_SRCH$0").select_option(SUBJECT)
            by_id(frame, "SSR_CLSRCH_WRK_CATALOG_NBR$1").fill(CATALOG_NBR)
            by_id(frame, "SSR_CLSRCH_WRK_SSR_OPEN_ONLY$3").evaluate("el => el.click()")
            by_id(frame, "CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH").evaluate("el => el.click()")

            self.maybe_hide(page)

            while True:
                try:
                    self.maybe_hide(page)
                    self.wait_for_human(page)

                    # 1. open the course
                    by_id(frame, "MTG_CLASSNAME$0").evaluate("el => el.click()")

                    # 2. read enrollment
                    enrolled = int(
                        by_id(frame, "SSR_CLS_DTL_WRK_ENRL_TOT").inner_text().strip()
                    )
                    print("Enrollment:", enrolled)

                    # 3. seat open -> alert + stop
                    if enrolled < SEAT_LIMIT:
                        notification.notify(
                            title="🚨 CAESAR Alert",
                            message=f"Seat available! Current enrollment: {enrolled}",
                            app_name="CAESAR Checker",
                            timeout=10,
                        )
                        os.system("afplay /System/Library/Sounds/Glass.aiff")
                        break

                    # 4. wait
                    wait = 60 + random.randint(-15, 15)
                    print(f"Waiting {wait} seconds before next check...")
                    for _ in tqdm(range(wait), desc="Next check in"):
                        time.sleep(1)
                        self.maybe_hide(page)
                        page.evaluate("1")  # keep connection alive

                    # 5. back to results
                    by_id(frame, "CLASS_SRCH_WRK2_SSR_PB_BACK").evaluate("el => el.click()")
                    time.sleep(3)

                except Exception as e:
                    print("Error during loop:", e)
                    time.sleep(10)

            ctx.close()


if __name__ == "__main__":
    CaesarChecker().run()
