from playwright.sync_api import Page

ROOT_URL = "https://class-descriptions.northwestern.edu"


def fetch_latest_term_url(page: Page) -> str:
    page.goto(ROOT_URL, wait_until="domcontentloaded", timeout=60000)

    href = page.locator(".content li a").first.get_attribute("href")
    if not href:
        raise RuntimeError("No term found in .content")

    if href.startswith("http"):
        return href.rstrip("/")

    if not href.startswith("/"):
        href = f"/{href}"
    return f"{ROOT_URL}{href}".rstrip("/")