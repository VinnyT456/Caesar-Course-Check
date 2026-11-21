from playwright.sync_api import Page, sync_playwright

def get_course_details(url: str, page: Page) -> dict: 
    page.goto(url, wait_until="domcontentloaded")

    course_content = page.locator(".content h2").all()

    course_details = {}
    for content in course_content:
        key = content.inner_text().strip()
        value = content.locator(
            "xpath=following-sibling::*[1]"
        ).inner_text().strip()

        course_details[key] = value

    return course_details

if __name__ == "__main__":
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        print(get_course_details("24942", "https://class-descriptions.northwestern.edu/5050/MEAS/COMP_SCI", page))