from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx


CANVAS_ORIGIN = "https://instructure.charlotte.edu"
CANVAS_API_BASE = f"{CANVAS_ORIGIN}/api/v1"
MAX_PAGES = 20
MAX_IMPORT_FILE_BYTES = 10 * 1024 * 1024
IMPORTABLE_SUFFIXES = {".txt", ".md", ".pdf", ".tex", ".html", ".htm"}
DOWNLOAD_HOST_SUFFIXES = (".instructure.com", ".amazonaws.com", ".cloudfront.net", ".inscloudgate.net")
INSTRUCTOR_ENROLLMENT_TYPES = {
    "TeacherEnrollment": "teacher",
    "TaEnrollment": "ta",
    "DesignerEnrollment": "designer",
}


class CanvasAPIError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _TextExtractor(HTMLParser):
    def __init__(self, *, preserve_links: bool = False) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored_depth = 0
        self.preserve_links = preserve_links
        self.links: list[tuple[int, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.ignored_depth += 1
        elif not self.ignored_depth and tag == "a" and self.preserve_links:
            href = next((value for name, value in attrs if name == "href"), None)
            self.links.append((len(self.parts), _safe_link(href)))
        elif not self.ignored_depth and tag in {"br", "li", "p", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1
        elif not self.ignored_depth and tag == "a" and self.preserve_links and self.links:
            start, href = self.links.pop()
            label = " ".join("".join(self.parts[start:]).split())
            if href and label:
                label = label.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
                self.parts[start:] = [f"[{label}]({href})"]
        elif not self.ignored_depth and tag in {"li", "p", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def _safe_link(href: str | None) -> str | None:
    if not href:
        return None
    href = href.strip()
    if not href or any(ord(char) < 32 for char in href):
        return None
    url = urljoin(CANVAS_ORIGIN, href)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return None
    # Encode Markdown delimiters so a URL cannot be cut short while rendering.
    return quote(url, safe=":/?#[]@!$&'*+,;=%-._~")


def safe_canvas_assignment_url(url: str | None) -> str | None:
    safe_url = _safe_link(url)
    if safe_url and urlparse(safe_url).netloc == urlparse(CANVAS_ORIGIN).netloc:
        return safe_url
    return None


def description_text(value: str | None, *, preserve_links: bool = False) -> str:
    if not value:
        return ""
    parser = _TextExtractor(preserve_links=preserve_links)
    parser.feed(value)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)[:10_000]


def linked_file_ids(description: str, course_id: int) -> list[int]:
    """Only return Canvas file links embedded in this course's assignment text."""
    pattern = re.compile(
        rf"https://instructure\.charlotte\.edu/(?:courses/(?P<course>\d+)/)?files/(?P<file>\d+)(?:[/?#]|$)"
    )
    found: list[int] = []
    for match in pattern.finditer(description):
        linked_course = match.group("course")
        file_id = int(match.group("file"))
        if linked_course and int(linked_course) != course_id:
            continue
        if file_id not in found:
            found.append(file_id)
    return found[:20]


def get_course_file(course_id: int, file_id: int, access_token: str, *, client: httpx.Client | None = None) -> dict[str, Any]:
    return _get_one(f"courses/{course_id}/files/{file_id}", access_token, client=client)


def file_import_reason(file: dict[str, Any]) -> str | None:
    filename = Path(str(file.get("filename") or file.get("display_name") or "")).name
    if Path(filename).suffix.lower() not in IMPORTABLE_SUFFIXES:
        return "This file type cannot be indexed. Its Canvas link remains available."
    if any(file.get(key) for key in ("hidden", "hidden_for_user", "locked", "locked_for_user")):
        return "This file is hidden or locked in Canvas."
    now = datetime.now(timezone.utc)
    for key, before in (("unlock_at", True), ("lock_at", False)):
        raw = file.get(key)
        if raw:
            try:
                limit = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if limit.tzinfo is None or (now < limit if before else now >= limit):
                    return "This file is not currently available to students in Canvas."
            except ValueError:
                return "Canvas returned an unreadable file access date."
    size = file.get("size")
    if not isinstance(size, int) or size < 1 or size > MAX_IMPORT_FILE_BYTES:
        return "Only files from 1 byte through 10 MB can be imported."
    if not file.get("url"):
        return "Canvas did not provide a download URL."
    return None


def _validate_download_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or not (host == urlparse(CANVAS_ORIGIN).hostname or host.endswith(DOWNLOAD_HOST_SUFFIXES))
    ):
        raise CanvasAPIError(502, "Canvas returned an unsupported file download host.")


def download_course_file(file: dict[str, Any], access_token: str, *, client: httpx.Client | None = None) -> bytes:
    reason = file_import_reason(file)
    if reason:
        raise CanvasAPIError(422, reason)
    url = str(file["url"])
    owned_client = client is None
    active_client = client or httpx.Client(timeout=20.0, follow_redirects=False)
    try:
        for _ in range(4):
            _validate_download_url(url)
            host = urlparse(url).hostname
            headers = {"Authorization": f"Bearer {access_token}"} if host == urlparse(CANVAS_ORIGIN).hostname else {}
            try:
                with active_client.stream("GET", url, headers=headers) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise CanvasAPIError(502, "Canvas returned a file redirect without a destination.")
                        url = urljoin(url, location)
                        continue
                    if not response.is_success:
                        raise _request_error(response)
                    content = bytearray()
                    for part in response.iter_bytes():
                        content.extend(part)
                        if len(content) > MAX_IMPORT_FILE_BYTES:
                            raise CanvasAPIError(422, "Canvas file exceeds the 10 MB import limit.")
                    if not content:
                        raise CanvasAPIError(502, "Canvas returned an empty file.")
                    return bytes(content)
            except httpx.TimeoutException as error:
                raise CanvasAPIError(504, "Canvas file download timed out.") from error
            except httpx.HTTPError as error:
                raise CanvasAPIError(502, "Canvas file could not be downloaded.") from error
        raise CanvasAPIError(502, "Canvas file redirected too many times.")
    finally:
        if owned_client:
            active_client.close()


def _next_url(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for item in link_header.split(","):
        url_part, *parameters = item.split(";")
        relations: set[str] = set()
        for parameter in parameters:
            name, separator, value = parameter.strip().partition("=")
            if name == "rel" and separator:
                relations.update(value.strip().strip('"').split())
        if "next" in relations:
            return url_part.strip().strip("<>")
    return None


def _validate_canvas_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "instructure.charlotte.edu"
        or not parsed.path.startswith("/api/v1/")
    ):
        raise CanvasAPIError(502, "Canvas returned an unsafe pagination URL.")


def _request_error(response: httpx.Response) -> CanvasAPIError:
    if response.status_code in {401, 403}:
        return CanvasAPIError(
            422,
            "Canvas rejected the access token. Create a current token in your UNC Charlotte Canvas account settings.",
        )
    if response.status_code == 404:
        return CanvasAPIError(404, "The Canvas course or assignment is not visible to this account.")
    if response.status_code == 429:
        return CanvasAPIError(503, "Canvas is rate limiting requests. Wait briefly and retry.")
    return CanvasAPIError(502, f"Canvas returned HTTP {response.status_code}.")


def _get_pages(
    path: str,
    access_token: str,
    *,
    params: dict[str, Any] | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    url = f"{CANVAS_API_BASE}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    owned_client = client is None
    active_client = client or httpx.Client(timeout=10.0, follow_redirects=False)
    items: list[dict[str, Any]] = []
    try:
        for page in range(MAX_PAGES):
            _validate_canvas_url(url)
            try:
                response = active_client.get(url, headers=headers, params=params if page == 0 else None)
            except httpx.TimeoutException as error:
                raise CanvasAPIError(504, "Canvas did not respond before the request timed out.") from error
            except httpx.HTTPError as error:
                raise CanvasAPIError(502, "Canvas could not be reached.") from error
            if not response.is_success:
                raise _request_error(response)
            try:
                payload = response.json()
            except ValueError as error:
                raise CanvasAPIError(502, "Canvas returned an unreadable response.") from error
            if not isinstance(payload, list):
                raise CanvasAPIError(502, "Canvas returned an unexpected response.")
            items.extend(item for item in payload if isinstance(item, dict))
            url = _next_url(response.headers.get("Link"))
            if not url:
                return items
        raise CanvasAPIError(502, "Canvas returned too many pages to import safely.")
    finally:
        if owned_client:
            active_client.close()


def _get_one(
    path: str,
    access_token: str,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    url = f"{CANVAS_API_BASE}/{path.lstrip('/')}"
    _validate_canvas_url(url)
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    owned_client = client is None
    active_client = client or httpx.Client(timeout=10.0, follow_redirects=False)
    try:
        try:
            response = active_client.get(url, headers=headers)
        except httpx.TimeoutException as error:
            raise CanvasAPIError(504, "Canvas did not respond before the request timed out.") from error
        except httpx.HTTPError as error:
            raise CanvasAPIError(502, "Canvas could not be reached.") from error
        if not response.is_success:
            raise _request_error(response)
        try:
            payload = response.json()
        except ValueError as error:
            raise CanvasAPIError(502, "Canvas returned an unreadable response.") from error
        if not isinstance(payload, dict):
            raise CanvasAPIError(502, "Canvas returned an unexpected response.")
        return payload
    finally:
        if owned_client:
            active_client.close()


def _active_instructor_enrollments(
    access_token: str, *, client: httpx.Client | None = None
) -> dict[str, str]:
    enrollments = _get_pages(
        "users/self/enrollments",
        access_token,
        params={
            "type[]": list(INSTRUCTOR_ENROLLMENT_TYPES),
            "state[]": "active",
            "per_page": 100,
        },
        client=client,
    )
    roles: dict[str, str] = {}
    for enrollment in enrollments:
        role = INSTRUCTOR_ENROLLMENT_TYPES.get(enrollment.get("type"))
        course_id = enrollment.get("course_id")
        if enrollment.get("enrollment_state") != "active" or not role or course_id is None:
            continue
        # Multiple sections can produce multiple enrollments for one course.
        # Prefer the teacher role if a user has more than one role there.
        key = str(course_id)
        if key not in roles or role == "teacher":
            roles[key] = role
    return roles


def require_instructor_course(
    course_id: int, access_token: str, *, client: httpx.Client | None = None
) -> str:
    role = _active_instructor_enrollments(access_token, client=client).get(str(course_id))
    if role:
        return role
    raise CanvasAPIError(403, "Your Canvas account does not have an active instructor role in this course.")


def list_courses(access_token: str, *, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    roles = _active_instructor_enrollments(access_token, client=client)
    if not roles:
        return []
    courses = _get_pages(
        "courses",
        access_token,
        params={"enrollment_state": "active", "per_page": 100},
        client=client,
    )
    return [
        {
            "id": str(course["id"]),
            "name": str(course.get("name") or course.get("course_code") or f"Course {course['id']}"),
            "course_code": str(course.get("course_code") or ""),
            "start_at": course.get("start_at"),
            "end_at": course.get("end_at"),
            "enrollment_role": roles[str(course["id"])],
        }
        for course in courses
        if course.get("id") is not None and str(course["id"]) in roles
    ]


def get_instructor_course(
    course_id: int, access_token: str, *, client: httpx.Client | None = None
) -> dict[str, Any]:
    require_instructor_course(course_id, access_token, client=client)
    course = _get_one(f"courses/{course_id}", access_token, client=client)
    if str(course.get("id")) != str(course_id):
        raise CanvasAPIError(502, "Canvas returned a different course than requested.")
    return {
        "id": str(course_id),
        "name": str(course.get("name") or course.get("course_code") or f"Course {course_id}"),
        "course_code": str(course.get("course_code") or ""),
    }


def list_assignments(
    course_id: int,
    access_token: str,
    *,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    require_instructor_course(course_id, access_token, client=client)
    assignments = _get_pages(
        f"courses/{course_id}/assignments",
        access_token,
        params={"per_page": 100},
        client=client,
    )
    return [
        {
            "id": str(assignment["id"]),
            "name": str(assignment.get("name") or f"Assignment {assignment['id']}"),
            "description": description_text(assignment.get("description")),
            "due_at": assignment.get("due_at"),
            "html_url": assignment.get("html_url"),
            "points_possible": assignment.get("points_possible"),
        }
        for assignment in assignments
        if assignment.get("id") is not None
    ]


def get_assignment(
    course_id: int,
    assignment_id: int,
    access_token: str,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    require_instructor_course(course_id, access_token, client=client)
    assignment = _get_one(
        f"courses/{course_id}/assignments/{assignment_id}",
        access_token,
        client=client,
    )
    return {
        "id": str(assignment["id"]),
        "name": str(assignment.get("name") or f"Assignment {assignment['id']}"),
        "description": description_text(assignment.get("description"), preserve_links=True),
        "due_at": assignment.get("due_at"),
        "html_url": assignment.get("html_url"),
        "points_possible": assignment.get("points_possible"),
    }
