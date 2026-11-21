"""Build caesar_checker/catalog.json for the app dropdowns.

Re-fetches only the cheap lists (terms, schools, subjects) to recover the
subject codes the saved data/ files dropped, then joins them with the course
numbers/names already in data/<school>/<subject>.json. No per-course crawling.

Run from the project root:  uv run python scraper/build_catalog.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from playwright.sync_api import sync_playwright  # noqa: E402
from quarters import ROOT_URL, fetch_latest_term_url  # noqa: E402
from schools import fetch_schools  # noqa: E402
from subjects import fetch_subjects  # noqa: E402

DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "caesar_checker", "catalog.json")


def file_stem(subject_label: str) -> str:
    # Mirror scraper/main.py: drop "CODE - " prefix, "/" -> "-".
    if " - " in subject_label:
        subject_label = subject_label.split(" - ", 1)[1]
    return subject_label.replace("/", "-")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        term_url = fetch_latest_term_url(page)
        term_code = term_url.rsplit("/", 1)[1]
        page.goto(ROOT_URL, wait_until="domcontentloaded")
        # Terms are listed newest first; the first one is what term_url points at.
        term_name = page.locator(".content li").first.inner_text().strip()
        schools = fetch_schools(term_url, page)
        subjects = fetch_subjects(term_url, schools, page)
        browser.close()

    out_schools = []
    missing = 0
    for school in schools:
        subs = []
        for label, code in subjects[school].items():
            name = label.split(" - ", 1)[1] if " - " in label else label
            path = os.path.join(DATA, school, file_stem(label) + ".json")
            courses = []
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    for c in json.load(f):
                        courses.append(
                            {"nbr": c["course_number"], "name": c["course_name"]}
                        )
            else:
                missing += 1
            subs.append({"code": code, "name": name, "courses": courses})
        subs.sort(key=lambda s: s["name"].lower())
        out_schools.append({"name": school, "subjects": subs})

    out_schools.sort(key=lambda s: s["name"].lower())
    catalog = {"term": {"code": term_code, "name": term_name}, "schools": out_schools}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, separators=(",", ":"))
    n = sum(len(s["subjects"]) for s in out_schools)
    print(f"Wrote {OUT}: {term_name} ({term_code}), {n} subjects, {missing} without data file")


if __name__ == "__main__":
    main()
