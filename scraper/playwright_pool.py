import threading

from playwright.sync_api import Page, sync_playwright

_thread_local = threading.local()

_BLOCKED = {"image", "font", "media"}


def _abort_heavy(route) -> None:
    if route.request.resource_type in _BLOCKED:
        route.abort()
    else:
        route.continue_()


def worker_page() -> Page:
    """Playwright sync API must run on the thread that created it — one browser per worker thread."""
    page = getattr(_thread_local, "page", None)
    if page is not None and not page.is_closed():
        return page

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.route("**/*", _abort_heavy)

    _thread_local.playwright = playwright
    _thread_local.browser = browser
    _thread_local.context = context
    _thread_local.page = page
    return page