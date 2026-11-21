from playwright.sync_api import Page


def fetch_schools(url: str, page: Page) -> list[dict]: 
    page.goto(url, wait_until="domcontentloaded")

    schools = page.locator(".content li").all_inner_texts()
    schools_links = [
        link.get_attribute("href")[link.get_attribute("href").index("/") + 1 :]
        for link in page.locator(".content li a").all()
        if link.get_attribute("href")[link.get_attribute("href").index("/") + 1 :]
        != "FSEMINAR"
    ]

    return {schools[i]: schools_links[i] for i in range(len(schools) - 1)}


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    from quarters import fetch_latest_term_url

    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_page()
        term_url = fetch_latest_term_url(page)
        print(fetch_schools(term_url, page))
