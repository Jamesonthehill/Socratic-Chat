"""Course-scoped diagnostics and isolated instructor test requests."""
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.pipeline_logging import recent_traces, redacted_preview, redacted_prompt_text
from platform_app import engines, store
from platform_app.routes import get_assignment, professor

router = APIRouter(prefix='/api/platform', tags=['pipeline-logs'])

# No arbitrary provider payloads, user messages, credentials, or filesystem paths.
VISIBLE_FIELDS = frozenset('''provider model primary_provider primary_model error_type
status_code provider_error_code fallback message_role route dialogue_status
conversation_action assessment_candidate ready step_index questions retrieval_type
 top_k chunks sources candidates selected queries latency_ms phase mode example_type
critical_misconception response_chars prompt_chars messages message_chars questions_count
pipeline_version source valid prompt_role prompt_truncated humor_detected humor_confidence'''.split())


def safe_event(event):
    fields = {}
    for key, value in (event.get('fields') or {}).items():
        if key not in VISIBLE_FIELDS:
            continue
        if isinstance(value, str):
            fields[key] = redacted_preview(value, max_chars=160)
        elif value is None or isinstance(value, (bool, int, float)):
            fields[key] = value
    result = {
        'stage': redacted_preview(str(event.get('stage', '')), max_chars=20),
        'event': redacted_preview(str(event.get('event', '')), max_chars=100),
        'elapsed_ms': event.get('elapsed_ms', 0),
        'fields': fields,
    }
    raw = event.get('fields') or {}
    if (event.get('event') == 'model_prompt' and raw.get('prompt_role') in {'system', 'developer'}
            and isinstance(raw.get('prompt_text'), str)):
        result['prompt'] = {'role': raw['prompt_role'], 'text': redacted_prompt_text(raw['prompt_text']),
                            'truncated': bool(raw.get('prompt_truncated'))}
    return result


@router.get('/pipeline-logs')
def pipeline_logs(response: Response, assignment_id: UUID | None = None,
                  limit: int = Query(50, ge=1, le=100), account=Depends(professor)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        traces = recent_traces(100)
    except RuntimeError as error:
        raise HTTPException(503, 'Pipeline logs are unavailable. Please try again.') from error
    attempt_ids, diagnostic_ids = set(), set()
    for trace in traces:
        try:
            attempt_ids.add(UUID(str(trace.get('conversation_id'))))
        except (ValueError, TypeError):
            pass
        try:
            diagnostic_ids.add(UUID(str(trace.get('diagnostic_assignment_id'))))
        except (ValueError, TypeError):
            pass
    if not attempt_ids and not diagnostic_ids:
        return {'traces': [], 'retention_limit': 100}
    with store.connection() as conn:
        query = '''SELECT t.id AS attempt_id, a.id AS assignment_id,
                   a.title AS assignment_title, c.title AS course_title
            FROM assignment_attempts_platform t
            JOIN assignments_platform a ON a.id=t.assignment_id
            JOIN courses_platform c ON c.id=a.course_id
            JOIN course_memberships_platform m ON m.course_id=a.course_id
                AND m.user_id=%s AND m.course_role='instructor' AND m.status='approved'
            WHERE t.id=ANY(%s)'''
        params = [account['user_id'], list(attempt_ids)]
        if assignment_id is not None:
            query += ' AND a.id=%s'
            params.append(assignment_id)
        allowed = {str(row['attempt_id']): row for row in conn.execute(query, params).fetchall()}
        diagnostic_query = '''SELECT a.id AS assignment_id, a.title AS assignment_title, c.title AS course_title
            FROM assignments_platform a JOIN courses_platform c ON c.id=a.course_id
            JOIN course_memberships_platform m ON m.course_id=a.course_id
                AND m.user_id=%s AND m.course_role='instructor' AND m.status='approved'
            WHERE a.id=ANY(%s) AND a.tool='socratic' '''
        diagnostic_params = [account['user_id'], list(diagnostic_ids)]
        if assignment_id is not None:
            diagnostic_query += ' AND a.id=%s'
            diagnostic_params.append(assignment_id)
        diagnostic_allowed = {str(row['assignment_id']): row
                              for row in conn.execute(diagnostic_query, diagnostic_params).fetchall()}
    result = []
    for trace in traces:
        diagnostic_metadata = diagnostic_allowed.get(str(trace.get('diagnostic_assignment_id')))
        metadata = diagnostic_metadata or allowed.get(str(trace.get('conversation_id')))
        if metadata is None:
            continue
        events = [safe_event(event) for event in trace.get('events', [])]
        attention = any(event['event'].endswith('_failed') or event['fields'].get('error_type') for event in events)
        finished = bool(trace.get('finished_at')) or any(
            event['event'] in {'assignment_response_returned', 'assignment_summary_returned'}
            or (event['event'] == 'step_readiness_completed' and event['fields'].get('ready'))
            for event in events)
        step_index = next((event['fields']['step_index'] for event in events
                           if isinstance(event['fields'].get('step_index'), int)), None)
        result.append({
            'trace_id': trace['trace_id'], 'started_at': trace['started_at'],
            'assignment_id': str(metadata['assignment_id']),
            'assignment_title': metadata['assignment_title'], 'course_title': metadata['course_title'],
            'step_index': step_index, 'status': 'attention' if attention else 'complete' if finished else 'in_progress',
            'duration_ms': trace.get('duration_ms', max((event['elapsed_ms'] for event in events), default=0)),
            'events': events,
            'diagnostic': diagnostic_metadata is not None,
        })
        if len(result) >= limit:
            break
    return {'traces': result, 'retention_limit': 100}


class DiagnosticInput(BaseModel):
    assignment_id: UUID
    model_config = {'extra': 'forbid'}


@router.post('/pipeline-logs/test')
def generate_test_log(body: DiagnosticInput, response: Response, account=Depends(professor)):
    """Run one instructor test without creating a recipient, attempt, grade or submission."""
    response.headers['Cache-Control'] = 'no-store'
    with store.connection() as conn:
        assignment = get_assignment(conn, body.assignment_id, account, manage=True)
    if assignment['tool'] != 'socratic' or assignment['status'] != 'published':
        raise HTTPException(409, 'Choose a published Socratic assignment for the test.')
    preview_id = uuid4()
    state = engines.start(assignment, {'id': preview_id})
    attempt = {'id': preview_id, 'status': 'in_progress', 'messages': state.pop('messages', []),
               'engine_state': state, 'instructor_preview': True}
    failed = False
    try:
        engines.message(assignment, attempt,
                        'I need help understanding this learning step. Can you explain it with a short example?',
                        str(uuid4()))
    except Exception:
        failed = True
    try:
        traces = recent_traces(100)
    except RuntimeError as error:
        raise HTTPException(503, 'The test log is temporarily unavailable. Refresh logs or try again.') from error
    trace = next((trace for trace in traces
                  if str(trace.get('conversation_id')) == str(preview_id)
                  and str(trace.get('diagnostic_assignment_id')) == str(body.assignment_id)), None)
    if trace is None:
        raise HTTPException(503, 'The test log could not be loaded. Refresh logs or try again.')
    return {'trace_id': trace['trace_id'], 'failed': failed}
