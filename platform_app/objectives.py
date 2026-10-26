"""Instructor review of document-grounded teaching plans from local-socratic-chat."""
import asyncio
import logging
from threading import Lock
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app import db
from app.objective_extraction import extract_and_save_learning_objectives, suggest_keywords
from app.pipeline_logging import begin_trace, end_trace, log_event, log_exception
from platform_app import store
from platform_app.routes import manage_course, professor
from platform_app.schemas import LearningObjectiveUpdate, SocraticSetupInput
from platform_app.socratic_setup import generate_opening_prompt, generate_setup

router = APIRouter(prefix="/api/courses", tags=["learning objectives"])
_generation_jobs: dict[str, dict[str, object]] = {}
_generation_jobs_lock = Lock()


@router.post("/{course_id}/socratic-setup/generate")
async def generate_socratic_setup(course_id: UUID, body: SocraticSetupInput, account=Depends(professor)):
    """Suggest editable settings using only the instructor's selected indexed files."""
    manage_course(course_id, account)
    selected = list(dict.fromkeys(body.document_ids))
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT id, filename, document_id FROM documents "
            "WHERE course_id=%s AND document_id=ANY(%s::text[])",
            (course_id, selected),
        ).fetchall()
    by_document = {str(row["document_id"]): row for row in rows}
    if len(by_document) != len(selected):
        raise HTTPException(422, "Select indexed documents from this course only.")
    try:
        draft = await generate_setup(
            [by_document[document_id] for document_id in selected],
            body.title,
            body.assignment_instructions,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logging.getLogger(__name__).exception("Could not draft Socratic setup for course %s", course_id)
        raise HTTPException(503, "The AI could not generate a setup from these materials. Check the model service and retry.") from exc
    return {**draft, "source_files": [by_document[item]["filename"] for item in selected]}


@router.post("/{course_id}/socratic-opening/generate")
async def generate_socratic_opening(course_id: UUID, body: SocraticSetupInput, account=Depends(professor)):
    """Draft only the basic-conversation opening prompt from selected course files."""
    manage_course(course_id, account)
    selected = list(dict.fromkeys(body.document_ids))
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT id, filename, document_id FROM documents "
            "WHERE course_id=%s AND document_id=ANY(%s::text[])",
            (course_id, selected),
        ).fetchall()
    by_document = {str(row["document_id"]): row for row in rows}
    if len(by_document) != len(selected):
        raise HTTPException(422, "Select indexed documents from this course only.")
    try:
        prompt = await generate_opening_prompt(
            [by_document[document_id] for document_id in selected],
            body.title,
            body.assignment_instructions,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logging.getLogger(__name__).exception("Could not draft Socratic opening for course %s", course_id)
        raise HTTPException(503, "The AI could not generate an opening question. Check the model service and retry.") from exc
    return {"prompt": prompt, "source_files": [by_document[item]["filename"] for item in selected]}


@router.get("/{course_id}/learning-objectives")
def list_objectives(course_id: UUID, account=Depends(professor)):
    manage_course(course_id, account)
    return {"objectives": db.list_course_learning_objectives(str(course_id))}


@router.post("/{course_id}/documents/{file_id}/keyword-suggestions")
def keyword_suggestions(course_id: UUID, file_id: UUID, account=Depends(professor)):
    manage_course(course_id, account)
    with store.connection() as conn:
        document = conn.execute(
            "SELECT filename FROM documents WHERE id=%s AND course_id=%s",
            (file_id, course_id),
        ).fetchone()
    if not document:
        raise HTTPException(404, "Course document was not found.")
    chunks = db.get_document_chunks_for_objectives(str(file_id))
    if not chunks:
        raise HTTPException(422, "This document has no indexed text yet. Check the embedding service and upload it again.")
    keywords = suggest_keywords(chunks)
    return {
        "keywords": keywords,
        "message": f"Suggested {len(keywords)} keyword(s) from {document['filename']}.",
    }


def _set_generation_job(file_id: UUID, **updates: object) -> None:
    with _generation_jobs_lock:
        _generation_jobs.setdefault(str(file_id), {}).update(updates)


def _generate_objectives(course_id: UUID, file_id: UUID, filename: str) -> None:
    # One extraction at a time for this document, across workers. Other documents remain usable.
    with store.connection() as conn:
        locked = conn.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS acquired", (f"objective-generation:{file_id}",)).fetchone()
        if not locked["acquired"]:
            _set_generation_job(
                file_id,
                status="failed",
                message="Objectives are already being generated for this document. Refresh the list shortly.",
            )
            return
        trace = begin_trace(uuid4().hex, f"course-document:{file_id}")
        try:
            log_event(1, "objective_generation_started", course_id=course_id, file_id=file_id)
            count = asyncio.run(extract_and_save_learning_objectives(str(file_id), str(course_id)))
            log_event(12, "objective_generation_completed", objectives_drafted=count)
            message = (
                f"Generated {count} draft objective(s) from {filename}. Previously reviewed objectives were kept."
                if count
                else "No additional supported objectives were generated. Existing objectives were kept."
            )
            _set_generation_job(file_id, status="completed", message=message, objectives_drafted=count)
        except Exception as error:
            log_exception(12, "objective_generation_failed", error)
            logging.getLogger(__name__).exception("Could not generate objectives for course document %s", file_id)
            _set_generation_job(
                file_id,
                status="failed",
                message="The model could not generate objectives. Existing objectives are saved; check the model service and try again.",
            )
        finally:
            end_trace(trace)


@router.post("/{course_id}/documents/{file_id}/learning-objectives/generate", status_code=202)
def generate_objectives(
    course_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    account=Depends(professor),
):
    manage_course(course_id, account)
    with store.connection() as conn:
        document = conn.execute(
            "SELECT filename FROM documents WHERE id=%s AND course_id=%s",
            (file_id, course_id),
        ).fetchone()
    if not document:
        raise HTTPException(404, "Course document was not found.")
    if not db.get_document_chunks_for_objectives(str(file_id)):
        raise HTTPException(422, "This document has no indexed text yet. Check the embedding service and upload it again before generating objectives.")
    with _generation_jobs_lock:
        job = _generation_jobs.get(str(file_id))
        if job and job.get("status") == "running":
            raise HTTPException(409, "Objectives are already being generated for this document. Refresh the list shortly.")
        _generation_jobs[str(file_id)] = {
            "status": "running",
            "message": f"Generating keyword suggestions from {document['filename']}.",
        }
    background_tasks.add_task(_generate_objectives, course_id, file_id, document["filename"])
    return _generation_jobs[str(file_id)]


@router.get("/{course_id}/documents/{file_id}/learning-objectives/generation-status")
def objective_generation_status(course_id: UUID, file_id: UUID, account=Depends(professor)):
    manage_course(course_id, account)
    with _generation_jobs_lock:
        job = _generation_jobs.get(str(file_id))
        return dict(job) if job else {"status": "idle", "message": "No objective generation is running."}


@router.patch("/{course_id}/learning-objectives/{objective_id}")
def update_objective(course_id: UUID, objective_id: UUID, body: LearningObjectiveUpdate, account=Depends(professor)):
    manage_course(course_id, account)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "Choose a field or review status to update.")
    result = db.update_course_learning_objective(str(course_id), str(objective_id), updates)
    if result is None:
        raise HTTPException(404, "Learning objective was not found in this course.")
    return result
