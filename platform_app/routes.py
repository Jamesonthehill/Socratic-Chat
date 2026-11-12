import asyncio
import json
import hashlib
import re
import secrets
from urllib.parse import quote
from typing import Literal
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from psycopg.types.json import Jsonb

from app import auth, db, settings
from app.pipeline_logging import reset_event_sink, set_event_sink
from platform_app import canvas_lms, engines, store, evidence_diagram, step_check, step_metrics
from platform_app.schemas import (
    ActionInput,
    SelfDirectedStudyInput, SelfDirectedQuizInput, SelfDirectedMessageInput, SelfDirectedTaskInput, SelfDirectedLearningTurn,
    AssignmentInput,
    CanvasCourseRequest,
    CanvasCredentials,
    CanvasImportRequest,
    GenerateSubtopicsInput,
    GenerateTopicInput,
    MessageInput,
    SocraticReflectionInput,
    SocraticStepCheck,
)

router = APIRouter(prefix="/api/platform", tags=["platform"])


class EvidenceDiagramInput(BaseModel):
    chunk_id: str = Field(min_length=1, max_length=150)


class SocraticStepCheckInput(BaseModel):
    request_id: UUID
    action: Literal["submit", "try_another", "continue_with_support"]
    option_index: int | None = Field(default=None, ge=0, le=3)
    reason: str = Field(default="", max_length=1200)


class PublishedStepChecksInput(BaseModel):
    checks: list[list[SocraticStepCheck]] = Field(min_length=1, max_length=10)
    minimum_step_questions: int | None = Field(default=None, ge=1, le=10)


class PublishedStepSettings(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    goal: str = Field(min_length=8, max_length=500)
    scenario: str = Field(default="", max_length=700)
    question: str = Field(default="", max_length=500)


class PublishedSocraticSettingsInput(BaseModel):
    tutor_mode: Literal["jarvis", "socrates"] = "socrates"
    instructions: str = Field(max_length=10000)
    prompt: str = Field(max_length=10000)
    minimum_step_questions: int = Field(ge=1, le=10)
    learning_steps: list[PublishedStepSettings] = Field(min_length=1, max_length=10)

    @field_validator("tutor_mode", mode="before")
    @classmethod
    def normalize_legacy_tutor_name(cls, value):
        return "jarvis" if value == "javis" else value


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
    if settings.REQUIRE_GITHUB_ACCOUNT and not db.user_has_github(uid):
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
        allowed = conn.execute("SELECT 1 FROM course_memberships_platform WHERE course_id=%s AND user_id=%s AND course_role='instructor' AND status='approved'", (item["course_id"],account["user_id"])).fetchone()
        if not allowed:
            raise HTTPException(403,"You do not manage this course.")
    else:
        # Enrollment revocation takes effect immediately, even for existing attempts.
        allowed = conn.execute("""SELECT 1 FROM assignment_recipients_platform r JOIN course_memberships_platform m
            ON m.user_id=r.student_id AND m.course_id=%s
            WHERE r.assignment_id=%s AND r.student_id=%s AND m.status='approved' AND m.course_role='student'""",
            (item["course_id"], assignment_id, account["user_id"])).fetchone()
        if item["status"] != "published" or not allowed:
            raise HTTPException(404, "Assignment not found or no longer available.")
    return item


def socratic_step_source(item, step):
    """Return only the published, instructor-selected passage for a guided step."""
    snapshot = item.get("snapshot") or {}
    selected = {str(value) for value in (snapshot.get("config") or {}).get("document_ids") or []}
    chunk = next((chunk for chunk in snapshot.get("chunks") or []
                  if str(chunk.get("chunk_id")) == str(step.get("source_chunk_id"))
                  and str(chunk.get("document_id")) in selected), None)
    if not chunk:
        return None
    return {
        "document_id": str(chunk["document_id"]),
        "chunk_id": str(chunk["chunk_id"]),
        "title": chunk.get("title") or step.get("source_file") or "Course material",
        "page_number": chunk.get("page_number"),
        "text": chunk["text"],
        "evidence_quote": step.get("evidence_quote", ""),
    }


def step_question_count(messages, step_started_at_message_count):
    """Count distinct tutor questions shown in the current guided step."""
    return step_check.count_step_questions(messages, step_started_at_message_count)


def public_assignment(item, manage=False):
    result = {k: v for k, v in item.items() if k not in ("snapshot", "config")}
    if manage:
        result["config"] = {k: v for k, v in item["config"].items() if item["tool"] != "socratic" or k != "minimum_messages"}
        if item["tool"] == "socratic" and item.get("snapshot"):
            result["concept_map"] = item["snapshot"].get("concept_map") or []
        if item["tool"] == "socratic" and item["status"] != "draft":
            result["config"] = {**result["config"],
                "scope_mode": "assignment", "keywords": [],
                "learning_objective_id": None}
    else:
        cfg = (item.get("snapshot") or {}).get("config", item["config"])
        # Never send historical student data, model answers, or instructor notes to students.
        if item["tool"] == "reflections":
            result["student_config"] = {k: cfg[k] for k in ("module_type", "milestone_prompt")}
        elif item["tool"] == "debate":
            result["student_config"] = {k: cfg[k] for k in ("scenario", "minimum_messages")}
        elif item["tool"] == "socratic":
            guided = cfg.get("guidance_mode", "guided" if cfg.get("learning_steps") else "basic") == "guided"
            result["student_config"] = {
                "minimum_step_questions": cfg.get("minimum_step_questions", 1),
                "keyword_glossary": [],
                "guidance_mode": "guided" if guided else "basic",
                "learning_path_time_limit_seconds": cfg.get("learning_path_minutes", 7) * 60 if guided else None,
                "learning_steps": [
                    {
                        "title": step["title"], "goal": step["goal"],
                        "source_file": step.get("source_file", ""),
                        "source": socratic_step_source(item, step),
                    }
                    for step in (cfg.get("learning_steps") or []) if guided
                ],
            }
        elif item["tool"] == "student-agent":
            topic = cfg["topic"]
            result["student_config"] = {"topic_name": topic["name"], "resources": [topic["resource"], topic["alt_resource"]]}
    return result


def published_socratic_material(assignment_id, document_id, account):
    """Only a recipient or course instructor may read the selected published material."""
    with store.connection() as conn:
        assignment = get_assignment(conn, assignment_id, account, manage=int(account["authority_level"]) <= 1)
    if assignment["tool"] != "socratic" or assignment["status"] != "published":
        raise HTTPException(404, "Published course material was not found.")
    snapshot = assignment.get("snapshot") or {}
    selected = {str(value) for value in (snapshot.get("config") or {}).get("document_ids") or []}
    chunks = [chunk for chunk in snapshot.get("chunks") or [] if str(chunk.get("document_id")) == document_id]
    if document_id not in selected or not chunks:
        raise HTTPException(404, "This material is not in the published assignment.")
    return assignment, chunks


@router.get("/assignments/{assignment_id}/materials")
def assignment_materials(assignment_id: UUID, account=Depends(user)):
    with store.connection() as conn:
        assignment = get_assignment(conn, assignment_id, account, manage=int(account["authority_level"]) <= 1)
    if assignment["tool"] != "socratic" or assignment["status"] != "published":
        raise HTTPException(404, "Published course materials were not found.")
    snapshot = assignment.get("snapshot") or {}
    selected = {str(value) for value in (snapshot.get("config") or {}).get("document_ids") or []}
    grouped = {}
    for chunk in snapshot.get("chunks") or []:
        document_id = str(chunk.get("document_id") or "")
        if document_id in selected and document_id not in grouped:
            grouped[document_id] = {"document_id": document_id, "title": str(chunk.get("title") or "Course material"),
                                    "pages": set()}
        if document_id in grouped and chunk.get("page_number") is not None:
            grouped[document_id]["pages"].add(chunk["page_number"])
    for document_id, material in grouped.items():
        original = db.get_course_rag_file(str(assignment["course_id"]), document_id)
        if original:
            material["title"] = original["filename"]
            material["original_available"] = True
        else:
            material["original_available"] = False
        material["page_count"] = len(material.pop("pages"))
    return {"materials": list(grouped.values())}


@router.get("/assignments/{assignment_id}/materials/{document_id}/download")
def download_assignment_material(assignment_id: UUID, document_id: str, account=Depends(user)):
    assignment, _ = published_socratic_material(assignment_id, document_id, account)
    original = db.get_course_rag_file(str(assignment["course_id"]), document_id, include_content=True)
    if not original:
        raise HTTPException(404, "The original file is no longer available. Ask your instructor to upload it again.")
    return Response(
        content=original["content"], media_type=original["content_type"] or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(str(original['filename']))}",
                 "X-Content-Type-Options": "nosniff"},
    )


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
        {"id": "debate", "name": "Debate", "description": "Build and defend an argument against focused AI challenges."},
    ]


@router.post("/assignments/{assignment_id}/reflection-launch")
def reflection_launch(assignment_id: UUID, account=Depends(user)):
    # Canvas iframe storage can differ from storage in a top-level tab.
    # Exchange a short-lived, single-use code rather than putting a session in a URL.
    with store.connection() as conn:
        assignment = get_assignment(conn, assignment_id, account)
        if assignment["tool"] != "reflections":
            raise HTTPException(422, "This assignment does not use Reflections.")
        code = secrets.token_urlsafe(32)
        conn.execute(
            """INSERT INTO lti_login_codes_platform
                (code_hash, user_id, course_id, expires_at)
                VALUES (%s, %s, %s, NOW() + INTERVAL '60 seconds')""",
            (hashlib.sha256(code.encode()).hexdigest(), account["user_id"], assignment["course_id"]),
        )
    return {"code": code}


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


@router.post("/integrations/canvas/courses")
def canvas_courses(body: CanvasCredentials, _account=Depends(professor)):
    return canvas_result(lambda: canvas_lms.list_courses(body.access_token.get_secret_value()))


@router.post("/integrations/canvas/assignments")
def canvas_assignments(body: CanvasCourseRequest, _account=Depends(professor)):
    return canvas_result(
        lambda: canvas_lms.list_assignments(body.course_id, body.access_token.get_secret_value())
    )


@router.post("/integrations/canvas/import", status_code=201)
def import_canvas_assignment(body: CanvasImportRequest, account=Depends(professor)):
    manage_course(body.platform_course_id, account)
    canvas_assignment = canvas_result(
        lambda: canvas_lms.get_assignment(
            body.course_id,
            body.assignment_id,
            body.access_token.get_secret_value(),
        )
    )
    source = canvas_assignment.get("html_url")
    source_note = f"\n\nCanvas source: {source}" if source else ""
    description_limit = max(0, 10_000 - len(source_note))
    instructions = f"{canvas_assignment['description'][:description_limit]}{source_note}".strip()
    config = {}
    if body.tool == "socratic":
        config = {
            "prompt": (
                "Help the learner reason through this Canvas assignment using only the "
                f"published course materials: {canvas_assignment['name']}"
            ),
        }
    elif body.tool == "debate":
        config = {
            "scenario": (
                f"Canvas assignment: {canvas_assignment['name']}\n\n"
                f"{canvas_assignment['description']}"
            )[:10000].strip(),
            "minimum_messages": 3,
        }
    return create_assignment(
        AssignmentInput(
            course_id=body.platform_course_id,
            tool=body.tool,
            title=canvas_assignment["name"][:200],
            instructions=instructions,
            due_at=canvas_assignment.get("due_at"),
            audience="course",
            config=config,
        ),
        account,
    )


@router.get("/assignments")
def assignments(course_id: UUID | None = None, account=Depends(user)):
    is_prof = int(account["authority_level"]) <= 1
    if course_id:
        from platform_app.workspace import course_access
        course_access(course_id, account)
    with store.connection() as conn:
        if is_prof:
            rows = conn.execute("""SELECT a.*, c.title AS course_title, c.course_code,
                (SELECT count(*) FROM assignment_recipients_platform WHERE assignment_id=a.id) AS recipient_count,
                (SELECT count(*) FROM assignment_attempts_platform WHERE assignment_id=a.id AND status='completed') AS completed_count
                , EXISTS(SELECT 1 FROM course_memberships_platform m
                    WHERE m.course_id=a.course_id AND m.user_id=%s
                    AND m.course_role='instructor' AND m.status='approved') AS can_manage
                FROM assignments_platform a JOIN courses_platform c ON c.id=a.course_id
                ORDER BY a.created_at DESC""", (account["user_id"],)).fetchall()
        else:
            rows = conn.execute("""SELECT a.*, c.title AS course_title, c.course_code,
                coalesce(t.status, 'not_started') AS progress,
                (l.assignment_id IS NOT NULL) AS canvas_linked
                FROM assignments_platform a JOIN courses_platform c ON c.id=a.course_id
                JOIN assignment_recipients_platform r ON r.assignment_id=a.id AND r.student_id=%s
                JOIN course_memberships_platform m ON m.course_id=a.course_id AND m.user_id=r.student_id AND m.status='approved'
                LEFT JOIN assignment_attempts_platform t ON t.assignment_id=a.id AND t.student_id=r.student_id
                LEFT JOIN lti_assignment_links_platform l ON l.assignment_id=a.id
                WHERE a.status='published' AND m.course_role='student'
                  AND (l.assignment_id IS NOT NULL OR NOT EXISTS (
                      SELECT 1 FROM lti_course_links_platform lc WHERE lc.course_id=a.course_id
                  ))
                ORDER BY a.due_at NULLS LAST, a.created_at DESC""", (account["user_id"],)).fetchall()
        result = []
        for row in rows:
            if row["tool"] == "student-agent" or (course_id and str(row['course_id']) != str(course_id)):
                continue
            if is_prof and not row["can_manage"]:
                # The shared catalog exposes assignment metadata, not private course
                # configuration, historical responses, or individual student records.
                result.append({k: v for k, v in row.items() if k not in ("snapshot", "config")})
            else:
                result.append(public_assignment(row, is_prof))
    if not is_prof and any(item["tool"] == "self-directed-learning" for item in result):
        lessons = self_directed_assignments(account)
        by_id = {str(item["id"]): item for item in lessons}
        for item in result:
            if item["tool"] == "self-directed-learning" and str(item["id"]) in by_id:
                item["progress"] = by_id[str(item["id"])].get("attempt_status") or "not_started"
    return result


@router.get("/assignments/{assignment_id}/reflection-analysis")
def reflection_analysis(assignment_id: UUID, account=Depends(professor)):
    """A course instructor's read-only view of saved Reflection attempts."""
    with store.connection() as conn:
        assignment = get_assignment(conn, assignment_id, account, manage=True)
        if assignment["tool"] not in {"reflections", "socratic"}:
            raise HTTPException(422, "Choose a Reflection or Socratic assignment to analyze.")
        rows = conn.execute("""SELECT u.id AS student_id, u.display_name, u.username,
                t.status, t.messages, t.result, t.completed_at
            FROM assignment_recipients_platform r
            JOIN users_platform u ON u.id = r.student_id
            LEFT JOIN assignment_attempts_platform t
                ON t.assignment_id = r.assignment_id AND t.student_id = r.student_id
            WHERE r.assignment_id = %s ORDER BY u.display_name, u.username""",
            (assignment_id,)).fetchall()
    students = []
    for row in rows:
        responses = [str(message.get("content") or "").strip()
                     for message in (row["messages"] or [])
                     if message.get("role") == "user" and str(message.get("content") or "").strip()]
        students.append({
            "student_id": row["student_id"],
            "name": row["display_name"] or row["username"],
            "status": row["status"] or "not_started",
            "response_count": len(responses),
            "responses": responses,
            "completed_at": row["completed_at"],
        })
    return {
        "assignment": {"id": assignment["id"], "title": assignment["title"],
                       "course_id": assignment["course_id"]},
        "summary": {"assigned": len(students),
                    "started": sum(student["status"] != "not_started" for student in students),
                    "completed": sum(student["status"] == "completed" for student in students),
                    "responses": sum(student["response_count"] for student in students)},
        "students": students,
    }


def validate_activity_documents(body):
    selected = set(body.config.get("document_ids", []))
    if selected:
        allowed = {str(f["document_id"]) for f in db.list_rag_files(course_id=str(body.course_id)) if f.get("document_id")}
        if not selected.issubset(allowed):
            raise HTTPException(422, "Select indexed documents from this course only.")


@router.post("/assignments", status_code=201)
def create_assignment(body: AssignmentInput, account=Depends(professor)):
    manage_course(body.course_id, account)
    validate_activity_documents(body)
    assignment_id = uuid4()
    with store.connection() as conn:
        row = conn.execute("""INSERT INTO assignments_platform(id, course_id, creator_id, tool, title, instructions, due_at, audience, config)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""", (assignment_id, body.course_id, account["user_id"], body.tool,
            body.title, body.instructions, body.due_at, body.audience, Jsonb(body.config))).fetchone()
        recipients(conn, assignment_id, body)
    return public_assignment(row, True)


@router.get("/assignments/{assignment_id}/material-reference")
def assignment_material_reference(assignment_id: UUID, phrase: str, document_id: str | None = None,
                                  account=Depends(user)):
    """Resolve a tutor's document phrase against the selected published pages."""
    phrase = " ".join(phrase.split())
    if not 3 <= len(phrase) <= 80:
        raise HTTPException(422, "Enter a short document reference.")
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=int(account["authority_level"]) <= 1)
    if item["tool"] != "socratic" or item["status"] != "published":
        raise HTTPException(404, "Published Socratic materials were not found.")
    snapshot = item.get("snapshot") or {}
    selected = {str(value) for value in (snapshot.get("config") or {}).get("document_ids") or []}
    chunks = [chunk for chunk in snapshot.get("chunks") or []
              if str(chunk.get("document_id")) in selected and chunk.get("page_number")]
    preferred = [chunk for chunk in chunks if str(chunk.get("document_id")) == document_id]
    others = [chunk for chunk in chunks if str(chunk.get("document_id")) != document_id]
    page_match = re.fullmatch(r"page\s+(\d+)", phrase, re.I)
    for chunk in preferred + others:
        if page_match:
            matches = int(chunk["page_number"]) == int(page_match.group(1))
        else:
            matches = phrase.casefold() in " ".join(str(chunk.get("text") or "").split()).casefold()
        if matches:
            return {"document_id": str(chunk["document_id"]),
                    "page_number": int(chunk["page_number"]),
                    "title": chunk.get("title") or "Course material"}
    raise HTTPException(404, "That section was not found in the instructor-selected materials.")


@router.post("/assignments/{assignment_id}/evidence-diagram")
async def assignment_evidence_diagram(assignment_id: UUID, body: EvidenceDiagramInput, account=Depends(user)):
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=int(account["authority_level"]) <= 1)
    if item["tool"] != "socratic" or item["status"] != "published":
        raise HTTPException(404, "Published Socratic evidence was not found.")
    snapshot = item.get("snapshot") or {}
    selected = {str(value) for value in (snapshot.get("config") or {}).get("document_ids") or []}
    passage = next((chunk for chunk in snapshot.get("chunks") or []
                    if str(chunk.get("chunk_id")) == body.chunk_id
                    and str(chunk.get("document_id")) in selected), None)
    if passage is None:
        raise HTTPException(404, "This passage is not in the published assignment.")
    try:
        steps = await evidence_diagram.build(str(passage.get("text") or ""))
    except Exception as exc:
        raise HTTPException(503, "A verified diagram is unavailable for this passage. You can still read the original text.") from exc
    return {"steps": steps}


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
                FROM assignment_recipients_platform r JOIN users_platform u ON u.id=r.student_id
                LEFT JOIN assignment_attempts_platform t ON t.assignment_id=r.assignment_id AND t.student_id=r.student_id
                WHERE r.assignment_id=%s ORDER BY u.username""", (assignment_id,)).fetchall()
        if is_prof and item['tool'] == 'self-directed-learning' and item['status'] == 'published':
            from platform_app.shared_rag import pipeline
            try:
                result['students'] = pipeline('GET', f"/internal/platform/lessons/{assignment_id}/progress")
            except HTTPException:
                result['progress_unavailable'] = True
        return result


@router.post("/assignments/{assignment_id}/step-checks/draft")
async def draft_published_step_checks(assignment_id: UUID, account=Depends(professor)):
    """Prepare checks for a legacy published path without changing student data."""
    from platform_app.socratic_setup import generate_checks_for_step

    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=True)
    snapshot = item.get("snapshot") or {}
    steps = (snapshot.get("config") or {}).get("learning_steps") or []
    if item["status"] != "published" or item["tool"] != "socratic" or not steps:
        raise HTTPException(409, "This assignment has no published Socratic learning path.")
    config = settings.llm_client_config("generation")
    if config is None:
        raise HTTPException(503, "Configure a generation model before drafting step checks.")
    provider, api_key, base_url, model = config
    checks = []
    for step in steps:
        if step.get("checks"):
            checks.append(step["checks"][:1])
            continue
        source = socratic_step_source(item, step)
        if not source:
            raise HTTPException(422, f"The selected source for {step['title']} is unavailable.")
        try:
            checks.append(await generate_checks_for_step(step, source["text"], provider, api_key, base_url, model))
        except Exception as exc:
            raise HTTPException(503, f"Could not draft checks for {step['title']}. Try again.") from exc
    return {"steps": [{"title": step["title"], "checks": pair} for step, pair in zip(steps, checks)]}


@router.put("/assignments/{assignment_id}/step-checks")
def save_published_step_checks(assignment_id: UUID, body: PublishedStepChecksInput, account=Depends(professor)):
    """Update only instructor-reviewed checks in both published config copies."""
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=True, lock=True)
        snapshot = item.get("snapshot") or {}
        snapshot_config = snapshot.get("config") or {}
        published_steps = snapshot_config.get("learning_steps") or []
        if item["status"] != "published" or item["tool"] != "socratic" or not published_steps:
            raise HTTPException(409, "This assignment has no published Socratic learning path.")
        if len(body.checks) != len(published_steps) or any(len(pair) != 1 for pair in body.checks):
            raise HTTPException(422, "Review one check for every learning step.")
        checked_steps = [{**step, "checks": [check.model_dump() for check in pair]}
                         for step, pair in zip(published_steps, body.checks)]
        minimum_questions = body.minimum_step_questions or snapshot_config.get("minimum_step_questions", 1)
        updated_snapshot = {**snapshot, "config": {**{k: v for k, v in snapshot_config.items() if k != "minimum_messages"}, "learning_steps": checked_steps,
                                                   "minimum_step_questions": minimum_questions}}
        updated_config = {**{k: v for k, v in item["config"].items() if k != "minimum_messages"}, "learning_steps": checked_steps,
                          "minimum_step_questions": minimum_questions}
        row = conn.execute("""UPDATE assignments_platform SET config=%s, snapshot=%s, updated_at=now()
            WHERE id=%s RETURNING *""", (Jsonb(updated_config), Jsonb(updated_snapshot), assignment_id)).fetchone()
        return public_assignment(row, True)


@router.patch("/assignments/{assignment_id}/socratic-settings")
def update_published_socratic_settings(assignment_id: UUID, body: PublishedSocraticSettingsInput,
                                       account=Depends(professor)):
    """Let instructors refine a published path without replacing its cited sources or student history."""
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=True, lock=True)
        snapshot = item.get("snapshot") or {}
        snapshot_config = snapshot.get("config") or {}
        saved_steps = snapshot_config.get("learning_steps") or []
        if item["status"] != "published" or item["tool"] != "socratic" or not saved_steps:
            raise HTTPException(409, "This assignment has no published Socratic learning path.")
        if len(body.learning_steps) != len(saved_steps):
            raise HTTPException(422, "Keep the published learning path's step count and sources.")
        edited_steps = [{**saved, **edited.model_dump()} for saved, edited in zip(saved_steps, body.learning_steps)]
        updates = {"prompt": body.prompt,
                   "tutor_mode": body.tutor_mode,
                   "minimum_step_questions": body.minimum_step_questions,
                   "learning_steps": edited_steps}
        updated_snapshot = {**snapshot, "config": {**{k: v for k, v in snapshot_config.items() if k != "minimum_messages"}, **updates}}
        updated_config = {**{k: v for k, v in item["config"].items() if k != "minimum_messages"}, **updates}
        row = conn.execute("""UPDATE assignments_platform SET instructions=%s,config=%s,snapshot=%s,updated_at=now()
            WHERE id=%s RETURNING *""", (body.instructions, Jsonb(updated_config), Jsonb(updated_snapshot),
                                          assignment_id)).fetchone()
        return public_assignment(row, True)


@router.put("/assignments/{assignment_id}")
def update_assignment(assignment_id: UUID, body: AssignmentInput, account=Depends(professor)):
    manage_course(body.course_id, account)
    validate_activity_documents(body)
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=True, lock=True)
        if item["status"] != "draft":
            raise HTTPException(409, "Published assignments are frozen. Duplicate the assignment to make changes.")
        if item["tool"] != body.tool and conn.execute(
            "SELECT 1 FROM assignment_attempts_platform WHERE assignment_id=%s LIMIT 1", (assignment_id,)
        ).fetchone():
            raise HTTPException(409, "An assignment with student attempts cannot change chatbots.")
        row = conn.execute("""UPDATE assignments_platform SET course_id=%s,tool=%s,title=%s,instructions=%s,due_at=%s,audience=%s,config=%s,updated_at=now()
            WHERE id=%s RETURNING *""", (body.course_id, body.tool, body.title, body.instructions, body.due_at, body.audience, Jsonb(body.config), assignment_id)).fetchone()
        recipients(conn, assignment_id, body)
        result = public_assignment(row, True)
        return result


@router.post("/assignments/{assignment_id}/publish")
def publish(assignment_id: UUID, account=Depends(professor)):
    with store.connection() as conn:
        item = get_assignment(conn, assignment_id, account, manage=True, lock=True)
        if item["status"] == "published":
            return public_assignment(item, True)
        if item["status"] != "draft":
            raise HTTPException(409, "Archived assignments cannot be published.")
        if not item["tool"]:
            raise HTTPException(422, "Choose an assigned chatbot before publishing.")
        if item["audience"] == "course":
            conn.execute("""INSERT INTO assignment_recipients_platform SELECT %s, user_id FROM course_memberships_platform
                WHERE course_id=%s AND status='approved' AND course_role='student' ON CONFLICT DO NOTHING""", (assignment_id, item["course_id"]))
        # Recheck selected recipients in case enrollment changed after saving the draft.
        invalid = conn.execute("""SELECT 1 FROM assignment_recipients_platform r WHERE assignment_id=%s AND NOT EXISTS
            (SELECT 1 FROM course_memberships_platform m WHERE m.course_id=%s AND m.user_id=r.student_id AND m.status='approved' AND m.course_role='student')""",
            (assignment_id, item["course_id"])).fetchone()
        if invalid:
            raise HTTPException(422, "A selected student is no longer enrolled. Update the draft's recipients.")
        try:
            if item["tool"] == "self-directed-learning":
                from platform_app.workspace import publish_sdl
                publish_sdl(conn, item, account)
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
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if engines.repair_legacy_socratic_opening(assignment, attempt):
            store.save_attempt(conn, attempt)
        return public_attempt(attempt)


@router.post("/assignments/{assignment_id}/start")
def start(assignment_id: UUID, account=Depends(user)):
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if attempt:
            if engines.repair_legacy_socratic_opening(assignment, attempt):
                store.save_attempt(conn, attempt)
            return public_attempt(attempt)
        # Deterministic identity lets engine starts recover from a lost gateway response.
        aid = uuid5(NAMESPACE_URL, f"cluball:{assignment_id}:{account['user_id']}")
        attempt = conn.execute("INSERT INTO assignment_attempts_platform(id,assignment_id,student_id) VALUES (%s,%s,%s) RETURNING *", (aid, assignment_id, account["user_id"])).fetchone()
        state = engines.start(assignment, attempt)
        attempt["messages"] = state.pop("messages", [])
        if assignment["tool"] == "socratic" and attempt["messages"]:
            first_step = ((assignment.get("snapshot") or {}).get("config") or {}).get("learning_steps") or []
            if first_step and (source := socratic_step_source(assignment, first_step[0])):
                attempt["messages"][0]["step_source"] = source
            opening_question = state.get("socratic", {}).get("next_thinking_step")
            if opening_question:
                attempt["messages"][0]["next_thinking_step"] = opening_question
        if assignment["tool"] == "socratic" and state.get("socratic"):
            step_metrics.track(state["socratic"])
        attempt["engine_state"] = state
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)


@router.post("/assignments/{assignment_id}/resume-question")
def resume_socratic_question(assignment_id: UUID, account=Depends(user)):
    """Restore a paused tutor question after a student-led subtopic detour."""
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if not attempt or assignment["tool"] != "socratic" or attempt["status"] == "completed":
            raise HTTPException(409, "Start an active Socratic assignment first.")
        state = dict((attempt.get("engine_state") or {}).get("socratic") or {})
        detour = state.get("learning_detour") or {}
        question = str(detour.get("question") or "").strip()
        if not question or int(detour.get("step_index") or 0) != int(state.get("learning_step_index") or 0):
            raise HTTPException(409, "There is no paused tutor question to return to.")
        steps = ((assignment.get("snapshot") or {}).get("config") or {}).get("learning_steps") or []
        index = int(state.get("learning_step_index") or 0)
        scenario = str(detour.get("scenario") or (
            steps[index].get("scenario") if 0 <= index < len(steps) else ""
        ) or "").strip()
        scenario_reminder = " ".join(re.split(r"(?<=[.!?])\s+", scenario)[:2])
        state.pop("learning_detour", None)
        state["next_thinking_step"] = question
        for key in ("learning_topic", "stable_concept", "active_concept"):
            if detour.get(key):
                state[key] = detour[key]
            else:
                state.pop(key, None)
        attempt["engine_state"]["socratic"] = state
        attempt["messages"].append({
            "role": "assistant",
            "content": "\n\n".join(part for part in (
                "Okay, let’s apply what you just learned.", scenario_reminder, question,
            ) if part),
            "next_thinking_step": question,
        })
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)


@router.get("/assignments/{assignment_id}/learning-journey")
def learning_journey(assignment_id: UUID, account=Depends(user)):
    from platform_app.learning_journey import summarize_difficulty
    with store.connection() as conn:
        assignment = get_assignment(conn, assignment_id, account)
        if assignment["tool"] != "socratic":
            raise HTTPException(404, "Learning journey is not available for this activity.")
        own = conn.execute("SELECT engine_state FROM assignment_attempts_platform WHERE assignment_id=%s AND student_id=%s",
                           (assignment_id, account["user_id"])).fetchone()
        if not own or not ((own["engine_state"] or {}).get("socratic") or {}).get("completion_summary"):
            raise HTTPException(409, "Finish your learning summary to view the class comparison.")
        peers = conn.execute("""SELECT t.engine_state FROM assignment_attempts_platform t
            JOIN assignment_recipients_platform r ON r.assignment_id=t.assignment_id AND r.student_id=t.student_id
            JOIN course_memberships_platform m ON m.course_id=%s AND m.user_id=t.student_id
            WHERE t.assignment_id=%s AND t.student_id<>%s
              AND m.status='approved' AND m.course_role='student'""",
            (assignment["course_id"], assignment_id, account["user_id"])).fetchall()
        steps = ((assignment.get("snapshot") or {}).get("config") or {}).get("learning_steps") or []
        return summarize_difficulty(steps, peers)


class StepDifficultyInput(BaseModel):
    step_index: int = Field(ge=0)
    difficulty: Literal["easy", "moderate", "hard", "skipped"]


@router.post("/assignments/{assignment_id}/step-difficulty")
def save_step_difficulty(assignment_id: UUID, body: StepDifficultyInput, account=Depends(user)):
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if not attempt or assignment["tool"] != "socratic" or attempt["status"] == "completed":
            raise HTTPException(409, "Start an active Socratic assignment first.")
        state = dict(attempt["engine_state"].get("socratic") or {})
        steps = ((assignment.get("snapshot") or {}).get("config") or {}).get("learning_steps") or []
        if body.step_index != state.get("learning_step_index") or body.step_index >= len(steps):
            raise HTTPException(409, "This learning step is no longer active.")
        step_metrics.track(state)
        state["step_metrics"][str(body.step_index)]["difficulty"] = body.difficulty
        attempt["engine_state"]["socratic"] = state
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)


@router.post("/assignments/{assignment_id}/next-step")
def next_socratic_step(assignment_id: UUID, account=Depends(user)):
    """Advance the learner's saved path only after they have discussed this step."""
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if not attempt or assignment["tool"] != "socratic" or attempt["status"] == "completed":
            raise HTTPException(409, "Start an active Socratic assignment first.")
        config = (assignment.get("snapshot") or {}).get("config", {})
        guided = config.get("guidance_mode", "guided" if config.get("learning_steps") else "basic") == "guided"
        steps = (config.get("learning_steps") or []) if guided else []
        state = dict(attempt["engine_state"].get("socratic") or {})
        index = int(state.get("learning_step_index") or 0)
        if not steps or index >= len(steps) - 1:
            raise HTTPException(409, "There is no next learning step.")
        if state.get("pending_clarification") or state.get("concept_check") or state.get("phase") != "teaching":
            raise HTTPException(409, "Finish the current question before moving to the next step.")
        since = int(state.get("step_started_at_message_count") or 0)
        if not any(message.get("role") == "user" for message in attempt["messages"][since:]):
            raise HTTPException(409, "Discuss this step with the tutor before continuing.")
        minimum_questions = int(config.get("minimum_step_questions") or 1)
        if step_question_count(attempt["messages"], since) < minimum_questions:
            raise HTTPException(409, f"Discuss at least {minimum_questions} tutor question(s) in this step before continuing.")
        index += 1
        step = steps[index]
        previous_step_state = dict(state)
        step_metrics.track(previous_step_state)
        state.update({
            "learning_step_index": index,
            "learning_topic": step["title"],
            "step_started_at_message_count": len(attempt["messages"]) + 1,
        })
        state.pop("stable_concept", None)
        state.pop("active_concept", None)
        state.pop("step_check", None)
        state.pop("step_readiness", None)
        state.pop("learning_detour", None)
        scenario = str(step.get("scenario") or "").strip()
        question = str(step.get("question") or "").strip()
        if not scenario:
            quote = str(step.get("evidence_quote") or "").strip()
            scenario = f"From the assignment: “{quote}”" if quote else ""
        if not question:
            question = f"How would you approach {step['title'].lower()} in this assignment?"
        elif not question.endswith("?"):
            question = f"{question.rstrip('.!')}?"
        state["next_thinking_step"] = question
        step_metrics.track(state, previous=previous_step_state)
        attempt["engine_state"]["socratic"] = state
        attempt["messages"].append({
            "role": "assistant",
            "content": "\n\n".join(part for part in (f"Step {index + 1}: {step['title']}", scenario, question) if part),
            "next_thinking_step": question,
            **({"step_source": source} if (source := socratic_step_source(assignment, step)) else {}),
        })
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)


@router.post("/assignments/{assignment_id}/step-check")
def socratic_step_check(assignment_id: UUID, body: SocraticStepCheckInput, account=Depends(user)):
    """Assess the current application check without putting quiz answers into the chat."""
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if not attempt or assignment["tool"] != "socratic" or attempt["status"] == "completed":
            raise HTTPException(409, "Start an active Socratic assignment first.")
        rid = str(body.request_id)
        if rid in attempt["processed_requests"]:
            return public_attempt(attempt)
        state = dict((attempt.get("engine_state") or {}).get("socratic") or {})
        steps = ((assignment.get("snapshot") or {}).get("config") or {}).get("learning_steps") or []
        index = int(state.get("learning_step_index") or 0)
        checks = steps[index].get("checks") or [] if 0 <= index < len(steps) else []
        if not checks or state.get("phase") != "teaching" or state.get("pending_clarification") or state.get("concept_check"):
            raise HTTPException(409, "This learning step has no application check.")
        since = int(state.get("step_started_at_message_count") or 0)
        if not any(message.get("role") == "user" for message in attempt["messages"][since:]):
            raise HTTPException(409, "Discuss this step with the tutor before taking its check.")
        minimum_questions = int(((assignment.get("snapshot") or {}).get("config") or {}).get("minimum_step_questions") or 1)
        if step_question_count(attempt["messages"], since) < minimum_questions:
            raise HTTPException(409, f"Discuss at least {minimum_questions} tutor question(s) in this step before taking its check.")
        progress = dict(state.get("step_check") or {})
        if progress.get("step_index") != index:
            progress = {"step_index": index, "variant": 0, "attempts": 0, "status": "active"}
        status = progress.get("status")
        if body.action == "try_another":
            raise HTTPException(409, "This step has one quiz. Review your answer or continue with support.")
        elif body.action == "continue_with_support":
            if status not in {"choice", "continued_with_support"}:
                raise HTTPException(409, "Try both chances before continuing with support.")
            progress["status"] = "continued_with_support"
        else:
            if status in {"passed", "choice", "continued_with_support"}:
                raise HTTPException(409, "Choose one of the available step-check actions.")
            variant = min(int(progress.get("variant") or 0), len(checks) - 1)
            check = checks[variant]
            if body.option_index is None or body.option_index >= len(check["options"]):
                raise HTTPException(422, "Choose an answer option.")
            reason = body.reason.strip()
            if len(reason) < 5:
                raise HTTPException(422, "Explain why you chose that answer.")
            if progress.get("last_option_correct") is False and body.option_index == progress.get("last_option_index"):
                raise HTTPException(409, "Choose a different option for your second chance.")
            selected_correctly = body.option_index == check["incorrect_option_index"]
            progress["last_option_index"] = body.option_index
            progress["last_option_correct"] = selected_correctly
            if selected_correctly:
                try:
                    sufficient, feedback = step_check.assess_reason_sync(check, check["options"][body.option_index], reason)
                except Exception as error:
                    raise HTTPException(503, "The step check could not review your reason. Please retry.") from error
            else:
                sufficient, feedback = False, "That choice fits this situation."
            progress["attempts"] = int(progress.get("attempts") or 0) + 1
            if selected_correctly and sufficient:
                progress.update({
                    "status": "passed",
                    "feedback": feedback or "You found the mistake and explained why it matters. Ready for the next step.",
                    "correct_option_index": check["incorrect_option_index"],
                })
            elif progress["attempts"] < 2:
                progress.update({
                    "status": "active",
                    "feedback": feedback,
                })
            else:
                progress.update({
                    "status": "choice",
                    "feedback": f"{feedback} {check['expected_reason']}",
                    "correct_option_index": check["incorrect_option_index"],
                })
        state["step_check"] = progress
        if progress["status"] in {"passed", "continued_with_support"}:
            outcomes = list(state.get("step_check_results") or [])
            outcomes = [item for item in outcomes if item.get("step_index") != index]
            outcomes.append({"step_index": index, "status": progress["status"]})
            state["step_check_results"] = outcomes
        attempt["engine_state"]["socratic"] = state
        attempt["processed_requests"].append(rid)
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)


def apply_state(attempt, state, content=None):
    if state.get("socratic"):
        step_metrics.track(
            state["socratic"],
            previous=(attempt.get("engine_state") or {}).get("socratic"),
            student_message=bool(content) and state["socratic"].get("phase") == "teaching",
        )
    if "messages" in state:
        attempt["messages"] = state.pop("messages")
    else:
        if content:
            attempt["messages"].append({"role": "user", "content": content})
        if state.get("reply"):
            next_question = (state.get("socratic") or {}).get("next_thinking_step")
            attempt["messages"].append({
                "role": "assistant", "content": state["reply"],
                **({"next_thinking_step": next_question} if next_question else {}),
                **({"sources": state["sources"]} if state.get("sources") else {}),
            })
    if state.pop("completed", False) or state.get("ended"):
        attempt["status"] = "completed"
        attempt["result"] = state.get("result", {"phase": state.get("phase")})
    attempt["engine_state"].update(state)


def merge_inline_clarification(attempt, original_question: str, clarification: str) -> bool:
    """Keep a student's clarification with the question it clarifies in one chat message."""
    messages = attempt.get("messages") or []
    if not messages or messages[-1].get("role") != "user":
        return False
    original = str(messages[-1].get("content") or "")
    if original != original_question:
        return False
    messages[-1]["content"] = f"{original}\n\nClarification: {clarification.strip()}"
    return True


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
        if (body.clarification_index is not None or body.clarification_text) and assignment["tool"] != "socratic":
            raise HTTPException(422, "Clarification choices are only available in Socratic Chat.")
        if body.clarification_index is not None and body.clarification_text:
            raise HTTPException(422, "Choose an option or write a clarification, not both.")
        if body.concept_check_option is not None and assignment["tool"] != "socratic":
            raise HTTPException(422, "Concept checks are only available in Socratic Chat.")
        message_options = {}
        if body.clarification_index is not None:
            message_options["clarification_index"] = body.clarification_index
        if body.clarification_text:
            message_options["clarification_text"] = True
        if body.concept_check_option is not None:
            message_options["concept_check_option"] = body.concept_check_option
        pending_clarification = attempt.get("engine_state", {}).get("socratic", {}).get("pending_clarification") or {}
        inline_clarification_reply = bool(
            (body.clarification_index is not None or body.clarification_text)
            and pending_clarification.get("inline")
        )
        state = engines.message(
            assignment, attempt, body.message, rid, **message_options
        )
        quiz_only = state.pop("quiz_only", False)
        student_message = state.pop("student_message", body.message)
        merged_clarification = inline_clarification_reply and merge_inline_clarification(
            attempt, str(pending_clarification.get("original_question") or ""), body.message,
        )
        apply_state(attempt, state, None if quiz_only or merged_clarification or (
            inline_clarification_reply and body.clarification_index is not None
        ) else student_message)
        attempt["processed_requests"].append(rid)
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)


def _student_chat_status(event: str) -> tuple[str, str] | None:
    """Expose completed pipeline stages without revealing internal prompts or labels."""
    return {
        "assignment_chat_received": ("received", "Reading your message"),
        "classifier_llm_started": ("understanding", "Understanding your question"),
        "message_classification_completed": ("understood", "Question understood"),
        "retrieval_started": ("searching", "Finding course material"),
        "assignment_sources_merged_and_reranked": ("evidence", "Relevant passages found"),
        "answer_evaluation_started": ("checking", "Checking your reasoning"),
        "socratic_strategy_selected": ("planning", "Planning the reply"),
        "llm_request_started": ("drafting", "Writing your reply"),
        "structured_socratic_response": ("reviewing", "Checking the reply"),
    }.get(event)


@router.post("/assignments/{assignment_id}/messages/stream")
async def message_stream(assignment_id: UUID, body: MessageInput, account=Depends(user)):
    """Stream actual Socratic pipeline stages and the normal saved attempt."""

    async def events():
        queue: asyncio.Queue[dict] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        last_stage = None
        current_understanding = ""

        def on_event(event, fields):
            nonlocal last_stage, current_understanding
            if event == "message_classification_completed":
                query = fields.get("retrieval_query")
                if isinstance(query, str):
                    current_understanding = " ".join(query.split())[:180]
            status = _student_chat_status(event)
            if status and status[0] != last_stage:
                last_stage = status[0]
                update = {
                    "type": "status", "stage": status[0], "label": status[1],
                }
                if current_understanding:
                    update["understanding"] = current_understanding
                loop.call_soon_threadsafe(queue.put_nowait, update)

        def execute():
            token = set_event_sink(on_event)
            try:
                return message(assignment_id, body, account)
            finally:
                reset_event_sink(token)

        async def run():
            try:
                result = await asyncio.to_thread(execute)
                queue.put_nowait({"type": "result", "data": jsonable_encoder(result)})
            except HTTPException as error:
                queue.put_nowait({"type": "error", "message": str(error.detail)})
            except Exception:
                queue.put_nowait({"type": "error", "message": "The tutor could not complete this reply. Please retry."})

        task = asyncio.create_task(run())
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield json.dumps({"type": "heartbeat"}) + "\n"
                    continue
                yield json.dumps(item, ensure_ascii=False) + "\n"
                if item["type"] in {"result", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@router.post("/assignments/{assignment_id}/reflection")
def socratic_reflection(assignment_id: UUID, body: SocraticReflectionInput, account=Depends(user)):
    reflection = body.summary.strip()
    if not reflection:
        raise HTTPException(422, "Write your own learning summary first.")
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if not attempt or (attempt["status"] == "completed" and not body.regenerate_feedback):
            raise HTTPException(409, "Start an unfinished Socratic assignment first.")
        if assignment["tool"] != "socratic":
            raise HTTPException(422, "This assignment does not use a Socratic learning summary.")
        config = ((assignment.get("snapshot") or {}).get("config") or {})
        steps = config.get("learning_steps") or []
        state = (attempt.get("engine_state") or {}).get("socratic") or {}
        if not body.regenerate_feedback and steps and int(state.get("learning_step_index") or 0) == len(steps) - 1:
            minimum_questions = int(config.get("minimum_step_questions") or 1)
            if step_question_count(attempt["messages"], state.get("step_started_at_message_count")) < minimum_questions:
                raise HTTPException(409, f"Discuss at least {minimum_questions} tutor question(s) in the final step before summarizing.")
        rid = str(body.request_id)
        if rid in attempt["processed_requests"] or (state.get("completion_summary") and not body.regenerate_feedback):
            return public_attempt(attempt)
        target = attempt
        if body.regenerate_feedback:
            if state.get("phase") != "ready_to_submit" or not state.get("completion_summary"):
                raise HTTPException(409, "Generate your final feedback before updating it.")
            from copy import deepcopy
            target = deepcopy(attempt)
            target["engine_state"]["socratic"].pop("completion_summary", None)
            target["engine_state"]["socratic"]["phase"] = "teaching"
        try:
            state = engines.reflect(assignment, target, reflection)
        except (ValueError, RuntimeError) as error:
            raise HTTPException(503, "The final feedback could not be generated. Your learning checkpoint is saved; please retry.") from error
        if body.regenerate_feedback:
            attempt["engine_state"]["socratic"] = state["socratic"]
            if attempt["status"] == "completed":
                attempt["result"] = {**(attempt.get("result") or {}), "completion_summary": state["socratic"]["completion_summary"]}
        else:
            apply_state(attempt, state, reflection)
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


class CompletionInput(BaseModel):
    improvement_consent: bool | None = None


@router.post("/assignments/{assignment_id}/complete")
def complete(assignment_id: UUID, body: CompletionInput | None = None, account=Depends(user)):
    with store.locked_attempt(assignment_id, account["user_id"]) as (conn, attempt):
        assignment = get_assignment(conn, assignment_id, account)
        if not attempt:
            raise HTTPException(409, "Start the assignment first.")
        if attempt["status"] == "completed":
            return public_attempt(attempt)
        result = engines.complete(assignment, attempt)
        if assignment["tool"] == "socratic":
            from datetime import datetime, timezone
            attempt["engine_state"]["improvement_consent"] = {
                "allowed": body.improvement_consent is True if body else False,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "notice_version": "braintutor-improvement-v1",
                "notice": "May our team use your chat, learning summary, and step difficulty ratings to improve the Socratic tutor? Your choice won’t affect your grade or access.",
            }
        if assignment["tool"] == "student-agent":
            apply_state(attempt, result.copy())
            result = {"phase": result.get("phase"), "ended": True}
        attempt["result"] = result
        attempt["status"] = "completed"
        store.save_attempt(conn, attempt)
        return public_attempt(attempt)

def student(request: Request, account=Depends(user)):
    if int(account["authority_level"]) <= 1:
        raise HTTPException(403, "Student access is required.")
    assignment_id = request.path_params.get("assignment_id")
    if assignment_id:
        with store.connection() as conn:
            linked = conn.execute("SELECT id FROM assignments_platform WHERE id::text=%s", (assignment_id,)).fetchone()
            if linked:
                get_assignment(conn, linked["id"], account)
    return account



def self_directed_assignment_summary(item: dict) -> dict:
    return {
        "id": item["id"],
        "tool": "self-directed-learning",
        "title": item["title"],
        "instructions": item.get("instructions", ""),
        "course_code": "Self-Directed Learning",
        "course_title": "Self-Directed Learning",
        "due_at": None,
        "progress": item.get("attempt_status") or "not_started",
        "source": "self_directed_learning",
    }



def self_directed_identity(account) -> str:
    return engines.resolve_self_directed_student(account)



@router.get("/self-directed/assignments")
def self_directed_assignments(account=Depends(student)):
    student_id = self_directed_identity(account)
    lessons = engines.self_directed_call(student_id, "GET", "/api/student/assignments")
    with store.connection() as conn:
        linked = {str(r["id"]) for r in conn.execute("SELECT id FROM assignments_platform WHERE tool='self-directed-learning'").fetchall()}
        allowed = {str(r["id"]) for r in conn.execute("""SELECT a.id FROM assignments_platform a
            JOIN assignment_recipients_platform r ON r.assignment_id=a.id
            JOIN course_memberships_platform m ON m.course_id=a.course_id AND m.user_id=r.student_id
            WHERE a.tool='self-directed-learning' AND a.status='published' AND r.student_id=%s
            AND m.status='approved' AND m.course_role='student'""", (account["user_id"],)).fetchall()}
    return [lesson for lesson in lessons if str(lesson["id"]) not in linked or str(lesson["id"]) in allowed]



@router.post("/self-directed/assignments/{assignment_id}/learning-turn")
def self_directed_learning_turn(assignment_id: str, body: SelfDirectedLearningTurn, account=Depends(student)):
    student_id = self_directed_identity(account)
    return engines.self_directed_call(student_id, "POST", f"/api/student/assignments/{assignment_id}/learning-turn", json=body.model_dump())



@router.get("/self-directed/assignments/{assignment_id}")
def self_directed_assignment(assignment_id: str, account=Depends(student)):
    student_id = self_directed_identity(account)
    return engines.self_directed_call(
        student_id, "GET", f"/api/student/assignments/{assignment_id}"
    )



@router.get("/self-directed/assignments/{assignment_id}/attempt")
def self_directed_attempt(assignment_id: str, account=Depends(student)):
    student_id = self_directed_identity(account)
    return engines.self_directed_call(
        student_id, "GET", f"/api/student/assignments/{assignment_id}/attempt"
    )



@router.post("/self-directed/assignments/{assignment_id}/start")
def start_self_directed_assignment(assignment_id: str, account=Depends(student)):
    student_id = self_directed_identity(account)
    return engines.self_directed_call(
        student_id, "POST", f"/api/student/assignments/{assignment_id}/start"
    )



@router.post("/self-directed/assignments/{assignment_id}/study-complete")
def complete_self_directed_study(
    assignment_id: str, body: SelfDirectedStudyInput, account=Depends(student)
):
    student_id = self_directed_identity(account)
    return engines.self_directed_call(
        student_id,
        "POST",
        f"/api/student/assignments/{assignment_id}/study-complete",
        json=body.model_dump(),
    )



@router.post("/self-directed/assignments/{assignment_id}/quiz")
def submit_self_directed_quiz(
    assignment_id: str, body: SelfDirectedQuizInput, account=Depends(student)
):
    student_id = self_directed_identity(account)
    return engines.self_directed_call(
        student_id,
        "POST",
        f"/api/student/assignments/{assignment_id}/quiz",
        json=body.model_dump(),
    )



@router.post("/self-directed/assignments/{assignment_id}/messages")
def send_self_directed_message(
    assignment_id: str, body: SelfDirectedMessageInput, account=Depends(student)
):
    student_id = self_directed_identity(account)
    return engines.self_directed_call(
        student_id,
        "POST",
        f"/api/student/assignments/{assignment_id}/messages",
        json=body.model_dump(),
    )



@router.post("/self-directed/assignments/{assignment_id}/restart")
def restart_self_directed_assignment(assignment_id: str, account=Depends(student)):
    student_id = self_directed_identity(account)
    return engines.self_directed_call(
        student_id, "POST", f"/api/student/assignments/{assignment_id}/restart"
    )



@router.post("/self-directed/assignments/{assignment_id}/submit-task")
def submit_self_directed_task(
    assignment_id: str, body: SelfDirectedTaskInput, account=Depends(student)
):
    student_id = self_directed_identity(account)
    return engines.self_directed_call(
        student_id,
        "POST",
        f"/api/student/assignments/{assignment_id}/submit-task",
        json=body.model_dump(),
    )


# Surveys are opt-in data collection; they never alter the tutor's readiness or quiz state.
from platform_app.step_surveys import register_step_surveys
register_step_surveys(router, get_assignment, professor, user, socratic_step_source)
