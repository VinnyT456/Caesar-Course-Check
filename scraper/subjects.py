from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import Page

from playwright_pool import worker_page


def _collect_subjects(url: str, school: str, link: str, page: Page) -> tuple[str, dict]:
    page.goto(f"{url}/{link}", wait_until="domcontentloaded")

    subjects_list = {}
    for subject in page.locator(".content li a").all():
        href = subject.get_attribute("href")
        if not href:
            continue
        slug = href[href.index("/") + 1 :]
        subjects_list[subject.inner_text()] = slug

    return school, subjects_list


def _subjects_for_school(url: str, school: str, link: str) -> tuple[str, dict]:
    return _collect_subjects(url, school, link, worker_page())


def fetch_subjects(url: str, schools: dict, page: Page) -> dict:
    schools_subjects = {}
    for school, link in schools.items():
        _, subjects_list = _collect_subjects(url, school, link, page)
        schools_subjects[school] = subjects_list
    return schools_subjects


def fetch_subjects_parallel(url: str, schools: dict, max_workers: int = 8) -> dict:
    schools_subjects = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_subjects_for_school, url, school, link)
            for school, link in schools.items()
        ]
        for future in as_completed(futures):
            school, subjects_list = future.result()
            schools_subjects[school] = subjects_list

    return schools_subjects


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    from schools import fetch_schools

    from quarters import fetch_latest_term_url

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        term_url = fetch_latest_term_url(page)
        schools = fetch_schools(term_url, page)
        print(fetch_subjects(term_url, schools, page))