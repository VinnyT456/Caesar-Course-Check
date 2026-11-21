import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from courses import fetch_courses
from playwright.sync_api import sync_playwright
from playwright_pool import worker_page
from quarters import fetch_latest_term_url
from schools import fetch_schools
from subjects import fetch_subjects_parallel

DEFAULT_WORKERS = 8


def fetch_and_save(
    school_name: str,
    school_link: str,
    subject_name: str,
    subject_link: str,
    term_url: str,
) -> str:
    page = worker_page()
    courses = fetch_courses(school_link, subject_link, page, term_url)

    if " - " in subject_name:
        subject_name = subject_name.split(" - ", 1)[1]

    subject_name = subject_name.replace("/", "-")

    filepath = os.path.join("data", school_name, f"{subject_name}.json")

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(courses, f, indent=4, ensure_ascii=False)

    return subject_name


def main(max_workers: int = DEFAULT_WORKERS) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        discovery_page = browser.new_page()
        discovery_page.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.resource_type in ["image", "font", "media"]
                else route.continue_()
            ),
        )
        term_url = fetch_latest_term_url(discovery_page)
        print("Term:", term_url)
        schools = fetch_schools(term_url, discovery_page)

    schools_subjects = fetch_subjects_parallel(term_url, schools, max_workers=max_workers)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [
            executor.submit(
                fetch_and_save,
                school_name,
                school_link,
                subject_name,
                subject_link,
                term_url,
            )
            for school_name, school_link in schools.items()
            for subject_name, subject_link in schools_subjects[school_name].items()
        ]

        for task in as_completed(tasks):
            try:
                print("Saved:", task.result())
            except Exception as e:
                print("Error:", e)


if __name__ == "__main__":
    main()