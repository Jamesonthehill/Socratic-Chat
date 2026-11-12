"""Check Classic Quiz report access without printing credentials or student data."""
import argparse
import getpass
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("survey_url", help="UNC Charlotte Canvas Classic Quiz URL")
    url = parser.parse_args().survey_url
    match = re.fullmatch(
        r"https://instructure\.charlotte\.edu/courses/(\d+)/quizzes/(\d+)/?(?:\?[^#]*)?(?:#.*)?",
        url,
    )
    if not match:
        parser.error("Use the survey URL from Canvas, ending in /courses/…/quizzes/…")
    course, quiz = match.groups()
    token = getpass.getpass("Canvas access token (hidden): ").strip()
    if not token:
        parser.error("Enter an instructor Canvas API token.")
    opener = build_opener(NoRedirect())
    endpoint = f"https://instructure.charlotte.edu/api/v1/courses/{course}/quizzes/{quiz}/reports"
    try:
        request = Request(endpoint, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        with opener.open(request, timeout=15) as response:
            payload = json.load(response)
    except HTTPError as error:
        parser.exit(1, f"Canvas returned HTTP {error.code}. Check the token permissions and survey URL.\n")
    except (URLError, TimeoutError, ValueError):
        parser.exit(1, "Could not read the Canvas reports API response.\n")
    reports = payload if isinstance(payload, list) else payload.get("quiz_reports", [payload])
    student_report = next((report for report in reports if report.get("report_type") == "student_analysis"), None)
    if student_report is None:
        print("Canvas returned no Student Analysis report for this survey.")
    else:
        print("Student Analysis file available:", bool(student_report.get("file")))
        print("Canvas marks report as generatable:", student_report.get("generatable", "unknown"))
        print("Canvas marks report as anonymous:", student_report.get("anonymous", "unknown"))


if __name__ == "__main__":
    main()
