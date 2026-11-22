"""Read-only, course-scoped diagnostics for instructor assignment requests."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.pipeline_logging import recent_traces, redacted_preview, redacted_prompt_text
from platform_app import store
from platform_app.routes import professor

router = APIRouter(prefix='/api/platform', tags=['pipeline-logs'])

# No arbitrary provider payloads, user messages, credentials, or filesystem paths.
VISIBLE_FIELDS = frozenset('''provider model primary_provider primary_model error_type
status_code provider_error_code fallback message_role route dialogue_status
conversation_action assessment_candidate ready step_index questions retrieval_type
 top_k chunks sources candidates selected queries latency_ms phase mode example_type
critical_misconception response_chars prompt_chars messages message_chars questions_count
pipeline_version source valid prompt_role prompt_truncated'''.split())


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
    attempt_ids = set()
    for trace in traces:
        try:
            attempt_ids.add(UUID(str(trace.get('conversation_id'))))
        except (ValueError, TypeError):
            continue
    if not attempt_ids:
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
    result = []
    for trace in traces:
        metadata = allowed.get(str(trace.get('conversation_id')))
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
        })
        if len(result) >= limit:
            break
    return {'traces': result, 'retention_limit': 100}
