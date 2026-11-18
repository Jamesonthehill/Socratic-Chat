"""Trusted bridge for common-platform course lessons; no demo identity headers."""
import json
import httpx
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .common_rag_api import service_access
from .db import connection, now
from .lesson_content import configuration_issues
from .schemas import LearningPlan

router = APIRouter(prefix="/internal/platform/lessons", dependencies=[Depends(service_access)])


class PrepareInput(BaseModel):
    instructional_quality: bool = False
    additional_instructions: str = Field(default="", max_length=10000)
    starting_point: str = Field(default="", max_length=2000)
    ending_point: str = Field(default="", max_length=4000)
    material: str = Field(min_length=3, max_length=30000)
    filename: str = Field(min_length=1, max_length=300)
    focus: str = Field(default="", max_length=10000)
    supplemental_material: str = Field(default="", max_length=12000)


class BoundarySuggestionInput(PrepareInput):
    concepts: list[str] = Field(default_factory=list, max_length=50)


@router.post('/suggest-boundaries')
def suggest_boundaries(body: BoundarySuggestionInput):
    from .openai_client import suggest_learning_boundaries
    import httpx
    try:
        return suggest_learning_boundaries(body.model_dump())
    except httpx.TimeoutException as exc:
        raise HTTPException(504, 'Suggesting lesson details timed out. Your lesson is unchanged; try again.') from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, 'AI suggestions are temporarily unavailable. Enter the details yourself or try again.') from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/expand')
def expand(body: PrepareInput):
    from .openai_client import expand_teaching_material
    import httpx
    try:
        additions = expand_teaching_material(body.material, body.filename, body.focus, body.starting_point, body.ending_point)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, 'Material expansion is temporarily unavailable. Your existing material is unchanged.') from exc
    return {'material_expansion': additions}


class Identity(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)


class PublishInput(BaseModel):
    id: str
    title: str
    instructions: str = ""
    instructor: Identity
    students: list[Identity]
    learning_plan: LearningPlan
    chunks: list[dict] = Field(default_factory=list)


@router.get('/{assignment_id}/application-interviews')
def application_interviews(assignment_id: str):
    # The platform verifies course-management permission before this trusted call.
    with connection() as conn:
        if not conn.execute('SELECT id FROM assignments WHERE id=?', (assignment_id,)).fetchone():
            raise HTTPException(404, 'Lesson not found.')
        rows = conn.execute('''SELECT u.id,u.display_name,t.learning_state FROM recipients r
            JOIN users u ON u.id=r.student_id
            LEFT JOIN attempts t ON t.assignment_id=r.assignment_id AND t.student_id=r.student_id
            WHERE r.assignment_id=? ORDER BY u.display_name''', (assignment_id,)).fetchall()
    return [{'student_id': row['id'], 'display_name': row['display_name'],
             'interview': json.loads(row['learning_state'] or '{}').get('application_interview')}
            for row in rows]


@router.post("/prepare")
def prepare(body: PrepareInput):
    from .main import _document_plan
    material = body.material
    if body.supplemental_material.strip():
        additions = '\n\nInstructor-reviewed additions (drafted using model knowledge):\n' + body.supplemental_material.strip()
        material = material[:30000 - len(additions)] + additions
    if len(material.strip()) < 30:
        raise HTTPException(422, 'Select readable material or approve an expansion before preparing the lesson.')
    if body.instructional_quality and (not body.starting_point.strip() or not body.ending_point.strip()):
        raise HTTPException(422, 'Review and confirm prior knowledge and the end goal before generating the lesson.')
    if bool(body.starting_point.strip()) != bool(body.ending_point.strip()):
        raise HTTPException(422, "Define the starting point and ending outcomes before preparing SDL.")
    plan = _document_plan(material, body.filename, starting_point=body.starting_point,
                          ending_point=body.ending_point, allow_course_material_fallback=True, learning_focus=body.focus,
                          additional_instructions=body.additional_instructions, instructional_quality=body.instructional_quality)
    plan["supplemental_material"] = body.supplemental_material.strip()
    if body.instructional_quality:
        from .instructional_quality import review_and_repair, fingerprint
        notes=plan.get('instructional_review',{}).get('notes',[])
        issues=configuration_issues({**plan,'content_approved':True})
        if issues:
            plan['instructional_review']={'passed':False,'fingerprint':fingerprint(plan),'issues':issues,'notes':notes}
            return plan
        try:
            plan = review_and_repair(plan)
            if notes:plan['instructional_review']['notes']=notes
        except (ValueError, httpx.HTTPError) as exc:
            from .instructional_quality import fingerprint
            issue = str(exc) if isinstance(exc, ValueError) else 'Instructional review is temporarily unavailable. Publishing will retry the review; no lesson has been approved.'
            # Keep the draft editable; failed or unavailable review never permits publication.
            plan['instructional_review'] = {'passed':False,'fingerprint':fingerprint(plan),'issues':[issue],'notes':notes}
    return plan


def identity(conn, person, role):
    existing = conn.execute("SELECT id,role FROM users WHERE email=?", (person.email.strip().lower(),)).fetchone()
    if existing and (existing["role"] != role or existing['id'] != person.id):
        raise HTTPException(409, "This email already belongs to a different SDL identity. Ask an administrator to review the mapping.")
    row = conn.execute("""INSERT INTO users(id,email,display_name,role) VALUES (?,?,?,?)
        ON CONFLICT(email) DO UPDATE SET display_name=excluded.display_name RETURNING id""",
        (person.id, person.email.strip().lower(), person.display_name, role)).fetchone()
    if row['id'] != person.id:
        raise HTTPException(409, 'This SDL email is linked to a different identity. Ask an administrator to review the mapping.')
    return row["id"]


@router.post("/publish")
def publish(body: PublishInput):
    plan = body.learning_plan.model_dump()
    plan["content_approved"] = True
    if plan.get('instructional_quality_version') == 1:
        from .instructional_quality import review_plan
        try:
            plan = review_plan(plan, force=True)
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(422, 'Instructional review must pass before publishing. ' + (str(exc) if isinstance(exc,ValueError) else 'The review provider is unavailable; retry.')) from exc
    issues = configuration_issues(plan)
    if plan.get("flow_version") != 2 or issues:
        raise HTTPException(422, {"message": "Prepare and review a complete SDL lesson before publishing.", "issues": issues})
    with connection() as conn:
        owner = identity(conn, body.instructor, "instructor")
        existing = conn.execute("SELECT instructor_id,status FROM assignments WHERE id=?", (body.id,)).fetchone()
        if existing and existing["instructor_id"] != owner:
            raise HTTPException(409, "The lesson belongs to another instructor.")
        student_ids = [identity(conn, person, "student") for person in body.students]
        if not existing:
            conn.execute("""INSERT INTO assignments(id,instructor_id,title,instructions,status,learning_plan,created_at,published_at)
                VALUES (?,?,?,?,'published',?,?,?)""", (body.id, owner, body.title, body.instructions, json.dumps(plan), now(), now()))
            documents = {}
            for i, chunk in enumerate(body.chunks):
                source = chunk["document_id"]
                if source not in documents:
                    document_id = str(uuid4())
                    documents[source] = document_id
                    conn.execute("INSERT INTO documents(id,assignment_id,filename,content_type,path,created_at) VALUES (?,?,?,?,?,?)",
                                 (document_id, body.id, chunk["title"], "application/octet-stream", "", now()))
                metadata = {**chunk.get("metadata", {}), "source_document_id": source, "page_number": chunk.get("page_number")}
                conn.execute("INSERT INTO chunks(id,document_id,position,content,embedding,metadata) VALUES (?,?,?,?,?,?)",
                             (str(uuid4()), documents[source], i, chunk["text"], json.dumps(chunk["embedding"]), json.dumps(metadata)))
        # Idempotent retries grant only the platform's current course recipients.
        conn.execute("DELETE FROM recipients WHERE assignment_id=?", (body.id,))
        conn.executemany("INSERT INTO recipients(assignment_id,student_id) VALUES (?,?)", [(body.id, sid) for sid in set(student_ids)])
    return {"id": body.id, "status": "published"}


@router.post("/{assignment_id}/enroll")
def enroll(assignment_id: str, body: Identity):
    """The authenticated platform has already checked course and recipient access."""
    with connection() as conn:
        lesson = conn.execute("SELECT id FROM assignments WHERE id=? AND status='published'", (assignment_id,)).fetchone()
        if lesson is None:
            raise HTTPException(404, "Assignment not found.")
        student_id = identity(conn, body, "student")
        conn.execute("INSERT INTO recipients(assignment_id,student_id) VALUES (?,?) ON CONFLICT DO NOTHING",
                     (assignment_id, student_id))
    return {"id": assignment_id, "student_id": student_id}


@router.get("/{assignment_id}/progress")
def progress(assignment_id: str):
    with connection() as conn:
        rows = conn.execute("""SELECT u.id AS student_id,u.display_name,u.email,
            coalesce(t.status,'not_started') AS progress,t.completed_at
            FROM recipients r JOIN users u ON u.id=r.student_id
            LEFT JOIN attempts t ON t.assignment_id=r.assignment_id AND t.student_id=r.student_id
            WHERE r.assignment_id=? ORDER BY u.display_name""", (assignment_id,)).fetchall()
    return [dict(row) for row in rows]
