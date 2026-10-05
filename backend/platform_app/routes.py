import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.types.json import Jsonb
from psycopg.errors import UniqueViolation

from app import auth, db, rag, settings
from platform_app import canvas_lms, canvas_tokens, engines, store
from platform_app.canvas_assignment_config import config_from_canvas
from platform_app.schemas import (
    ActionInput,
    AssignmentInput,
    CanvasCourseRequest,
    CanvasCredentials,
    CanvasFileImportRequest,
    CanvasImportRequest,
    CanvasLinkCourseRequest,
    CanvasTokenInput,
    GenerateSubtopicsInput,
    GenerateTopicInput,
    MessageInput,
)

router = APIRouter(prefix="/api/platform", tags=["platform"])


def user(request: Request):
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Please sign in.")
    uid = auth.verify_session(token)["sub"]
    account = db.get_user_by_id(uid)
    if not account:
        raise HTTPException(401, "Account not found.")
    if not account.get("onboarding_complete"):
        raise HTTPException(403, "Complete account setup first.")
    if (
        settings.REQUIRE_GITHUB_ACCOUNT
        and not account.get("canvas_connected")
        and not db.user_has_github(uid)
    ):
        raise HTTPException(403, "Connect your GitHub account first.")
    return account


def professor(account=Depends(user)):
    if int(account["authority_level"]) > 1:
        raise HTTPException(403, "Professor access is required.")
    return account


def manage_course(course_id, account):
    if not db.user_manages_course(str(course_id), str(account["user_id"])):
        raise HTTPException(403, "You do not manage this course.")


def get_assignment(conn, assignment_id, account, manage=False, lock=False):
    item = conn.execute("SELECT * FROM assignments_platform WHERE id=%s" + (" FOR UPDATE" if lock else ""), (assignment_id,)).fetchone()
    if not item:
        raise HTTPException(404, "Assignment not found.")
    if manage:
        manage_course(item["course_id"], account)
    else:
        # Enrollment revocation takes effect immediately, even for existing attempts.
        allowed = conn.execute("""SELECT 1 FROM course_memberships_platform m
            WHERE m.course_id=%s AND m.user_id=%s AND m.status='approved' AND m.course_role='student'
            AND (EXISTS (SELECT 1 FROM assignment_recipients_platform r
                         WHERE r.assignment_id=%s AND r.student_id=m.user_id) OR %s='course')""",
            (item["course_id"], account["user_id"], assignment_id, item["audience"])).fetchone()
        if item["status"] != "published" or not allowed:
            raise HTTPException(404, "Assignment not found or no longer available.")
    return item


def public_assignment(item, manage=False):
    result = {k: v for k, v in item.items() if k not in ("snapshot", "config")}
    if manage:
        result["config"] = item["config"]
    else:
        cfg = (item.get("snapshot") or {}).get("config", item["config"])
        # Never send historical student data, model answers, or instructor notes to students.
        if item["tool"] == "reflections":
            result["student_config"] = {k: cfg[k] for k in ("module_type", "milestone_prompt")}
        elif item["tool"] == "socratic":
            result["student_config"] = {"minimum_messages": cfg["minimum_messages"]}
        else:
            topic = cfg["topic"]
            result["student_config"] = {"topic_name": topic["name"], "resources": [topic["resource"], topic["alt_resource"]]}
    return result


def public_attempt(attempt):
    return {k: v for k, v in attempt.items() if k != "processed_requests"} if attempt else None


def recipients(conn, assignment_id, body):
    conn.execute("DELETE FROM assignment_recipients_platform WHERE assignment_id=%s", (assignment_id,))
    if body.audience == "selected":
        for sid in set(body.recipient_ids):
            if not conn.execute("SELECT 1 FROM course_memberships_platform WHERE course_id=%s AND user_id=%s AND status='approved' AND course_role='student'",
                                (body.course_id, sid)).fetchone():
                raise HTTPException(422, "Every selected student must be enrolled in this course.")
            conn.execute("INSERT INTO assignment_recipients_platform VALUES (%s, %s)", (assignment_id, sid))


@router.get("/tools")
def tools(account=Depends(user)):
    return [
        {"id": "socratic", "name": "Socratic Chat", "description": "Explore questions grounded in your course materials."},
        {"id": "reflections", "name": "Reflections", "description": "Guide students through topics or milestone reflections."},
        {"id": "student-agent", "name": "Student Agent Bot", "description": "Read, check understanding, and practice with a tutor."},
    ]


@router.get("/topic-templates")
def templates(account=Depends(professor)):
    return engines.topic_templates()


@router.post("/generate-topic")
def generate_topic(body: GenerateTopicInput, account=Depends(professor)):
    return engines.call("student-agent", "POST", "/api/topics/generate", json=body.model_dump())


@router.post("/generate-subtopics")
def generate_subtopics(body: GenerateSubtopicsInput, account=Depends(professor)):
    return engines.call("reflections", "POST", "/api/modules/subtopics/generate", json=body.model_dump())


def canvas_result(operation):
    try:
        return operation()
    except canvas_lms.CanvasAPIError as error:
        raise HTTPException(error.status_code, error.detail) from error


def canvas_access_token(body: CanvasCredentials, account) -> str:
    if body.access_token is not None:
        return body.access_token.get_secret_value()
    try:
        token = canvas_tokens.load(str(account["user_id"]))
    except canvas_tokens.CanvasTokenConfigurationError as error:
        raise HTTPException(503, str(error)) from error
    except canvas_tokens.CanvasTokenReconnectRequired as error:
        raise HTTPException(409, str(error)) from error
    if not token:
        raise HTTPException(422, "Connect your Canvas account before loading Canvas data.")
    return token


@router.get("/integrations/canvas/connection")
def canvas_connection(account=Depends(professor)):
    return canvas_tokens.status(str(account["user_id"]))


@router.post("/integrations/canvas/connection")
def connect_canvas(body: CanvasTokenInput, account=Depends(professor)):
    if not canvas_tokens.is_configured():
        raise HTTPException(503, "Canvas token storage is not configured on this server.")
    token = body.access_token.get_secret_value()
    courses = canvas_result(lambda: canvas_lms.list_courses(token))
    try:
        canvas_tokens.save(str(account["user_id"]), token)
    except canvas_tokens.CanvasTokenConfigurationError as error:
        raise HTTPException(503, str(error)) from error
    return {**canvas_tokens.status(str(account["user_id"])), "courses": courses}


@router.delete("/integrations/canvas/connection")
def disconnect_canvas(account=Depends(professor)):
    canvas_tokens.delete(str(account["user_id"]))
    return {"connected": False, "encryption_configured": canvas_tokens.is_configured()}


@router.post("/integrations/canvas/courses")
def canvas_courses(body: CanvasCredentials, account=Depends(professor)):
    courses = canvas_result(lambda: canvas_lms.list_courses(canvas_access_token(body, account)))
    if body.access_token is None:
        canvas_tokens.mark_verified(str(account["user_id"]))
    return courses


@router.post("/integrations/canvas/course", status_code=201)
def create_course_from_canvas(body: CanvasCourseRequest, account=Depends(professor)):
    source = canvas_result(
        lambda: canvas_lms.get_instructor_course(
            body.course_id, canvas_access_token(body, account)
        )
    )
    course_code = (source["course_code"] or f"CANVAS-{body.course_id}")[:40]
    title = source["name"][:160]
    try:
        course = db.create_course(
            str(account["user_id"]),
            course_code,
            title,
            f"Imported from UNC Charlotte Canvas course {body.course_id}.",
            canvas_course_id=source["id"],
        )
    except Exception as error:
        detail = str(error)
        if "courses_instructor_id_course_code_key" in detail or "duplicate key" in detail:
            raise HTTPException(409, "You already have a course with that code.") from error
        raise
    course["membership_role"] = "instructor"
    course["membership_status"] = "approved"
    return course


@router.post("/integrations/canvas/link-course")
def link_canvas_course(body: CanvasLinkCourseRequest, account=Depends(professor)):
    manage_course(body.platform_course_id, account)
    source = canvas_result(
        lambda: canvas_lms.get_instructor_course(
            body.course_id, canvas_access_token(body, account)
        )
    )
    try:
        course = db.link_course_to_canvas(
            str(body.platform_course_id), str(account["user_id"]), source["id"]
        )
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except UniqueViolation as error:
        raise HTTPException(409, "This Canvas course is already linked to another class.") from error
    course["membership_role"] = "instructor"
    course["membership_status"] = "approved"
    return course


@router.post("/integrations/canvas/assignments")
def canvas_assignments(body: CanvasCourseRequest, account=Depends(professor)):
    return canvas_result(
        lambda: canvas_lms.list_assignments(body.course_id, canvas_access_token(body, account))
    )


@router.post("/integrations/canvas/import", status_code=201)
def import_canvas_assignment(body: CanvasImportRequest, account=Depends(professor)):
    manage_course(body.platform_course_id, account)
    destination = db.get_course(str(body.platform_course_id))
    if destination and destination["canvas_course_id"] is not None and destination["canvas_course_id"] != str(body.course_id):
        raise HTTPException(422, "This class is linked to a different Canvas course.")
    canvas_assignment = canvas_result(
        lambda: canvas_lms.get_assignment(
            body.course_id,
            body.assignment_id,
            canvas_access_token(body, account),
        )
    )
    source = canvas_lms.safe_canvas_assignment_url(canvas_assignment.get("html_url"))
    source_note = f"\n\n[Open original assignment in Canvas]({source})" if source else ""
    description_limit = max(0, 10_000 - len(source_note))
    instructions = f"{canvas_assignment['description'][:description_limit]}{source_note}".strip()
    title = canvas_assignment["name"][:200]
    config = config_from_canvas(body.tool, canvas_assignment, body.course_id, body.assignment_id)
    return create_assignment(
        AssignmentInput(
            course_id=body.platform_course_id,
            tool=body.tool,
            title=title,
            instructions=instructions,
            due_at=canvas_assignment.get("due_at"),
            audience="course",
            config=config,
        ),
        account,
    )


def canvas_assignment_files_context(assignment_id: UUID, account):
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=True)
    if item["tool"] != "socratic" or item["status"] != "draft":
        raise HTTPException(409, "Canvas files can only be added to a Socratic Chat draft.")
    course = db.get_course(str(item["course_id"])) or {}
    canvas_course_id = course.get("canvas_course_id")
    if not canvas_course_id:
        raise HTTPException(422, "Link this class to its Canvas course before importing files.")
    course_id = int(canvas_course_id)
    context = str(item["config"].get("canvas_context") or "")
    if not context:
        raise HTTPException(422, "This draft was not imported from Canvas.")
    linked = canvas_lms.linked_file_ids(context, course_id)
    token = canvas_access_token(CanvasCredentials(), account)
    canvas_result(lambda: canvas_lms.require_instructor_course(course_id, token))
    return item, course_id, linked, token


@router.get("/assignments/{assignment_id}/canvas-files")
def canvas_assignment_files(assignment_id: UUID, account=Depends(professor)):
    item, course_id, linked, token = canvas_assignment_files_context(assignment_id, account)
    existing = {f["filename"] for f in db.list_rag_files(course_id=str(item["course_id"]), limit=500)}
    files = []
    for file_id in linked:
        try:
            metadata = canvas_lms.get_course_file(course_id, file_id, token)
            if str(metadata.get("id")) != str(file_id):
                raise canvas_lms.CanvasAPIError(502, "Canvas returned a different file.")
            filename = Path(str(metadata.get("filename") or metadata.get("display_name") or f"File {file_id}")).name
            stored_name = f"Canvas {file_id} - {filename}"
            reason = canvas_lms.file_import_reason(metadata)
            files.append({
                "id": file_id, "filename": filename, "size": metadata.get("size"),
                "imported": stored_name in existing, "importable": not reason,
                "reason": reason,
            })
        except canvas_lms.CanvasAPIError:
            files.append({"id": file_id, "filename": f"Canvas file {file_id}", "size": None,
                          "imported": False, "importable": False, "reason": "This file is unavailable in Canvas."})
    return {"files": files}


@router.post("/assignments/{assignment_id}/canvas-files")
def import_canvas_assignment_files(
    assignment_id: UUID, body: CanvasFileImportRequest, account=Depends(professor)
):
    item, course_id, linked, token = canvas_assignment_files_context(assignment_id, account)
    selected = list(dict.fromkeys(body.file_ids))
    if any(file_id not in linked for file_id in selected):
        raise HTTPException(422, "Choose only files linked in this Canvas assignment.")
    platform_course_id = str(item["course_id"])
    existing = {f["filename"] for f in db.list_rag_files(course_id=platform_course_id, limit=500)}
    imported = []
    skipped = []
    for file_id in selected:
        file_row_id = None
        filename = f"Canvas file {file_id}"
        try:
            metadata = canvas_lms.get_course_file(course_id, file_id, token)
            if str(metadata.get("id")) != str(file_id):
                raise canvas_lms.CanvasAPIError(502, "Canvas returned a different file.")
            filename = Path(str(metadata.get("filename") or metadata.get("display_name") or filename)).name
            stored_name = f"Canvas {file_id} - {filename}"
            if stored_name in existing:
                skipped.append({"id": file_id, "filename": filename, "reason": "Already in course materials."})
                continue
            content = canvas_lms.download_course_file(metadata, token)
            with TemporaryDirectory(prefix="canvas-material-") as directory:
                target = Path(directory) / stored_name
                target.write_bytes(content)
                file_row_id = db.save_rag_file(
                    stored_name, str(metadata.get("content-type") or "application/octet-stream"), content,
                    user_id=str(account["user_id"]), course_id=platform_course_id,
                )
                if not file_row_id:
                    raise HTTPException(503, "PostgreSQL is required to import course materials.")
                document_id, chunks = rag.ingest_file(target, course_id=platform_course_id, file_id=file_row_id)
            if not chunks:
                db.delete_course_document(file_row_id, platform_course_id)
                file_row_id = None
                skipped.append({"id": file_id, "filename": filename,
                                "reason": "No searchable text was found in this file."})
                continue
            imported.append({"id": file_id, "filename": filename, "document_id": document_id, "chunks_added": chunks})
            existing.add(stored_name)
        except canvas_lms.CanvasAPIError as error:
            skipped.append({"id": file_id, "filename": filename, "reason": error.detail})
        except HTTPException:
            if file_row_id:
                db.delete_course_document(file_row_id, platform_course_id)
            raise
        except Exception:
            if file_row_id:
                db.delete_course_document(file_row_id, platform_course_id)
            skipped.append({"id": file_id, "filename": filename, "reason": "The file could not be indexed."})
    return {"imported": imported, "skipped": skipped}


@router.get("/assignments")
def assignments(account=Depends(user)):
    is_prof = int(account["authority_level"]) <= 1
    with store.connection() as conn:
        if is_prof:
            rows = conn.execute("""SELECT a.*, c.title AS course_title, c.course_code,
                (SELECT count(*) FROM course_memberships_platform m
                 WHERE a.audience='course' AND m.course_id=a.course_id AND m.status='approved' AND m.course_role='student')
                + (SELECT count(*) FROM assignment_recipients_platform r
                   WHERE a.audience='selected' AND r.assignment_id=a.id) AS recipient_count,
                (SELECT count(*) FROM assignment_attempts_platform WHERE assignment_id=a.id AND status='completed') AS completed_count
                FROM assignments_platform a JOIN courses_platform c ON c.id=a.course_id
                WHERE c.instructor_id=%s ORDER BY a.created_at DESC""", (account["user_id"],)).fetchall()
        else:
            rows = conn.execute("""SELECT a.*, c.title AS course_title, c.course_code, coalesce(t.status, 'not_started') AS progress
                FROM assignments_platform a JOIN courses_platform c ON c.id=a.course_id
                JOIN course_memberships_platform m ON m.course_id=a.course_id AND m.user_id=%s
                    AND m.status='approved' AND m.course_role='student'
                LEFT JOIN assignment_attempts_platform t ON t.assignment_id=a.id AND t.student_id=m.user_id
                WHERE a.status='published' AND (a.audience='course' OR EXISTS
                    (SELECT 1 FROM assignment_recipients_platform r
                     WHERE r.assignment_id=a.id AND r.student_id=m.user_id))
                ORDER BY a.due_at NULLS LAST, a.created_at DESC""", (account["user_id"],)).fetchall()
        return [public_assignment(row, is_prof) for row in rows]


@router.post("/assignments", status_code=201)
def create_assignment(body: AssignmentInput, account=Depends(professor)):
    manage_course(body.course_id, account)
    assignment_id = uuid4()
    with store.connection() as conn:
        row = conn.execute("""INSERT INTO assignments_platform(id, course_id, creator_id, tool, title, instructions, due_at, audience, config)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""", (assignment_id, body.course_id, account["user_id"], body.tool,
            body.title, body.instructions, body.due_at, body.audience, Jsonb(body.config))).fetchone()
        recipients(conn, assignment_id, body)
    return public_assignment(row, True)


@router.get("/assignments/{assignment_id}")
def assignment_detail(assignment_id: UUID, account=Depends(user)):
    is_prof = int(account["authority_level"]) <= 1
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=is_prof)
        result = public_assignment(item, is_prof)
        if is_prof:
            result["recipient_ids"] = [r["student_id"] for r in conn.execute("SELECT student_id FROM assignment_recipients_platform WHERE assignment_id=%s", (assignment_id,))]
            result["students"] = conn.execute("""SELECT u.display_name, u.username, u.id AS student_id,
                coalesce(t.status, 'not_started') AS progress, t.completed_at, t.result
                FROM course_memberships_platform m JOIN users_platform u ON u.id=m.user_id
                LEFT JOIN assignment_attempts_platform t ON t.assignment_id=%s AND t.student_id=m.user_id
                WHERE m.course_id=%s AND m.status='approved' AND m.course_role='student'
                  AND (%s='course' OR EXISTS
                    (SELECT 1 FROM assignment_recipients_platform r
                     WHERE r.assignment_id=%s AND r.student_id=m.user_id))
                ORDER BY u.username""", (assignment_id, item["course_id"], item["audience"], assignment_id)).fetchall()
        return result


@router.put("/assignments/{assignment_id}")
def update_assignment(assignment_id: UUID, body: AssignmentInput, account=Depends(professor)):
    manage_course(body.course_id, account)
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=True, lock=True)
        if item["status"] != "draft":
            raise HTTPException(409, "Published assignments are frozen. Duplicate the assignment to make changes.")
        if item["tool"] != body.tool:
            raise HTTPException(422, "An assignment's tool cannot be changed.")
        row = conn.execute("""UPDATE assignments_platform SET course_id=%s,title=%s,instructions=%s,due_at=%s,audience=%s,config=%s,updated_at=now()
            WHERE id=%s RETURNING *""", (body.course_id, body.title, body.instructions, body.due_at, body.audience, Jsonb(body.config), assignment_id)).fetchone()
        recipients(conn, assignment_id, body)
        return public_assignment(row, True)


@router.post("/assignments/{assignment_id}/publish")
def publish(assignment_id: UUID, account=Depends(professor)):
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=True, lock=True)
        if item["status"] == "published":
            return public_assignment(item, True)
        if item["status"] != "draft":
            raise HTTPException(409, "Archived assignments cannot be published.")
        # Course-wide assignments are visible to approved students, including those who enroll later.
        # Recheck selected recipients in case enrollment changed after saving the draft.
        invalid = conn.execute("""SELECT 1 FROM assignment_recipients_platform r WHERE assignment_id=%s AND NOT EXISTS
            (SELECT 1 FROM course_memberships_platform m WHERE m.course_id=%s AND m.user_id=r.student_id AND m.status='approved' AND m.course_role='student')""",
            (assignment_id, item["course_id"])).fetchone()
        if invalid:
            raise HTTPException(422, "A selected student is no longer enrolled. Update the draft's recipients.")
        try:
            snapshot = engines.publish_snapshot(item)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        row = conn.execute("UPDATE assignments_platform SET status='published', snapshot=%s, published_at=now(),updated_at=now() WHERE id=%s RETURNING *",
                           (Jsonb(snapshot), assignment_id)).fetchone()
        return public_assignment(row, True)


@router.post("/assignments/{assignment_id}/archive")
def archive(assignment_id: UUID, account=Depends(professor)):
    with store.connection() as conn:
        get_assignment(conn, assignment_id, account, manage=True, lock=True)
        conn.execute("UPDATE assignments_platform SET status='archived', updated_at=now() WHERE id=%s", (assignment_id,))
    return {"status": "archived"}


@router.post("/assignments/{assignment_id}/duplicate", status_code=201)
def duplicate(assignment_id: UUID, account=Depends(professor)):
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=True)
    return create_assignment(AssignmentInput(course_id=item["course_id"], tool=item["tool"], title=item["title"][:190] + " (copy)",
                            instructions=item["instructions"], config=item["config"]), account)


@router.get("/assignments/{assignment_id}/attempt")
def attempt_detail(assignment_id: UUID, account=Depends(user)):
    with store.connection() as conn:
        get_assignment(conn, assignment_id, account)
        return public_attempt(conn.execute("SELECT * FROM assignment_attempts_platform WHERE assignment_id=%s AND student_id=%s", (assignment_id, account["user_id"])).fetchone())


@router.post("/assignments/{assignment_id}/start")
def start(assignment_id: UUID, account=Depends(user)):
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if attempt:
            return public_attempt(attempt)
        # Deterministic identity lets engine starts recover from a lost gateway response.
        aid = uuid5(NAMESPACE_URL, f"cluball:{assignment_id}:{account['user_id']}")
        attempt = conn.execute("INSERT INTO assignment_attempts_platform(id,assignment_id,student_id) VALUES (%s,%s,%s) RETURNING *", (aid, assignment_id, account["user_id"])).fetchone()
        state = engines.start(assignment, attempt)
        attempt["messages"] = state.pop("messages", [])
        attempt["engine_state"] = state
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)


def apply_state(attempt, state, content=None):
    if "messages" in state:
        attempt["messages"] = state.pop("messages")
    else:
        if content:
            attempt["messages"].append({"role": "user", "content": content})
        if state.get("reply"):
            attempt["messages"].append({"role": "assistant", "content": state["reply"]})
    if state.pop("completed", False) or state.get("ended"):
        attempt["status"] = "completed"
        attempt["result"] = state.get("result", {"phase": state.get("phase")})
    attempt["engine_state"].update(state)


@router.post("/assignments/{assignment_id}/messages")
def message(assignment_id: UUID, body: MessageInput, account=Depends(user)):
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if not attempt:
            raise HTTPException(409, "Start the assignment first.")
        rid = str(body.request_id)
        if rid in attempt["processed_requests"]:
            return public_attempt(attempt)
        if attempt["status"] == "completed":
            raise HTTPException(409, "This assignment is already completed.")
        state = engines.message(assignment, attempt, body.message, rid)
        apply_state(attempt, state, body.message)
        attempt["processed_requests"].append(rid)
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)


@router.post("/assignments/{assignment_id}/actions")
def action(assignment_id: UUID, body: ActionInput, account=Depends(user)):
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if not attempt or assignment["tool"] != "student-agent":
            raise HTTPException(409, "Start a tutor assignment first.")
        rid = str(body.request_id)
        if rid in attempt["processed_requests"]:
            return public_attempt(attempt)
        if attempt["status"] == "completed":
            raise HTTPException(409, "This assignment is already completed.")
        if body.action == "scenario" and attempt["engine_state"].get("phase") != "practice":
            raise HTTPException(422, "Reach the practice phase before choosing a scenario.")
        state = engines.call("student-agent", "POST", "/internal/platform/action", json={
            "session_id": str(attempt["id"]), "action": body.action, "value": body.value, "request_id": rid})
        apply_state(attempt, state)
        attempt["processed_requests"].append(rid)
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)


@router.post("/assignments/{assignment_id}/complete")
def complete(assignment_id: UUID, account=Depends(user)):
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if not attempt:
            raise HTTPException(409, "Start the assignment first.")
        if attempt["status"] == "completed":
            return public_attempt(attempt)
        result = engines.complete(assignment, attempt)
        if assignment["tool"] == "student-agent":
            apply_state(attempt, result.copy())
            result = {"phase": result.get("phase"), "ended": True}
        attempt["result"] = result
        attempt["status"] = "completed"
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)
