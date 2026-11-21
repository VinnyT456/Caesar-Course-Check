from playwright.sync_api import Page, sync_playwright
from course_details import get_course_details
import re

def reformat_course_info(course_info: str) -> dict:
    day_mapping = {
        "Mon": "Monday",
        "Tues": "Tuesday",
        "Wed": "Wednesday",
        "Thurs": "Thursday",
        "Fri": "Friday",
        "Sa": "Saturday",
        "Su": "Sunday"
    }

    course_info = " ".join(course_info.split())

    section, rest = course_info.split(": ", 1)
    course_name, *parts = rest.split(" - ")

    pattern = (
        r"(?P<days>(?:Mon|Tues|Wed|Thurs|Fri|Sa|Su)"
        r"(?:,\s*(?:Mon|Tues|Wed|Thurs|Fri|Sa|Su))*)"
        r"\s+(?P<start>\d{1,2}:\d{2}[AP]M)"
        r"\s+-\s+"
        r"(?P<end>\d{1,2}:\d{2}[AP]M)"
    )

    match = re.search(pattern, rest)

    days = None
    start_time = None
    end_time = None
    instructors = []

    if match:
        start_time = match.group("start")
        end_time = match.group("end")

        days = [
            day_mapping[day.strip()]
            for day in match.group("days").split(",")
        ]

        # Remove the schedule from the original string
        instructor_text = rest[:match.start()].strip(" -")

        # Remove the course name
        instructor_text = instructor_text[len(course_name):].strip(" -")

        instructors = [
            name.strip()
            for name in instructor_text.split(" - ")
            if name.strip()
        ]

    else:
        instructors = [
            p.strip() for p in parts if p.strip() != "TBA"
        ]

    return {
        "section": section,
        "course_name": course_name,
        "instructors": instructors,
        "days": days,
        "start_time": start_time,
        "end_time": end_time
    }

def get_course_info(course_number: str, page: Page) -> tuple[list[str], list[str]]:
    course_sections = page.locator(f'div[id="{course_number}"] ul li').all()

    course_reference_number = []
    course_info = []

    for section in course_sections:
        course_number = section.locator("a").get_attribute("href").split("/")[-1]
        course_reference_number.append(course_number)
        course_info.append(reformat_course_info(section.inner_text()))

    return course_reference_number, course_info


def fetch_courses(
    school_name: str, subject_name: str, page: Page, term_url: str
) -> list[dict]:
    url = f"{term_url}/{school_name}/{subject_name}"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    courses = page.locator(".expand-collapse h2").all_inner_texts()

    courses_list = []

    course_numbers, course_names = [], []
    for course in courses:
        course_numbers.append(course.split(" ", 1)[0])
        course_names.append(course.split(" ", 1)[1])

    for course_number, course_name in zip(course_numbers, course_names):
        course_reference_number, course_info = get_course_info(course_number, page)
        course_details = []
        for reference_number in course_reference_number:
            course_detail = get_course_details(url + f"/{reference_number}", page)
            course_details.append(course_detail)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        courses_list.append({
            "course_number": course_number,
            "course_name": course_name,
            "course_reference_number": course_reference_number,
            "course_info": course_info,
            "course_details": course_details
        })

    return courses_list


if __name__ == "__main__":
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        from quarters import fetch_latest_term_url

        term_url = fetch_latest_term_url(page)
        courses_list = fetch_courses("MEAS", "COMP_SCI", page, term_url)