"""Canvas setup uses authored boundaries and reports the actual timeout stage."""
import httpx
import pytest

from test_api import client, headers, lesson


def test_canvas_prepare_uses_instructor_inputs_without_document_inference(client, monkeypatch):
    from app import main
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN', 'prepare-test-token')
    def unexpected(*args):
        raise AssertionError('Complete instructor inputs must not trigger document inference')
    monkeypatch.setattr(main, 'infer_document_context', unexpected)
    monkeypatch.setattr(main, 'discover_resources', lambda *args: [])
    monkeypatch.setattr(main, 'verify_resources', lambda *args: [])
    captured = {}
    def generate(topic, course_level, *args, **kwargs):
        captured.update(topic=topic, course_level=course_level, **kwargs)
        return lesson()
    monkeypatch.setattr(main, 'generate_learning_plan', generate)
    response = client.post('/internal/platform/lessons/prepare',
        headers={'X-Platform-Service': 'prepare-test-token'}, json={
            'material': lesson()['approved_material'], 'filename': 'course.pdf',
            'focus': 'Evaluate requirements for a new system\nInstructor sub-questions to address:\nDistinguish functional and quality requirements.\nJustify measurable acceptance criteria.',
            'starting_point': 'Basic software development',
            'ending_point': 'Justify measurable requirements for a campus application',
        })
    assert response.status_code == 200, response.text
    assert captured['topic'] == 'Evaluate requirements for a new system'
    assert captured['prerequisite_knowledge'] == 'Basic software development'
    assert captured['objective_descriptions'] == ['Justify measurable requirements for a campus application']
    assert captured['required_coverage'] == [
        'Justify measurable requirements for a campus application',
        'Distinguish functional and quality requirements.',
        'Justify measurable acceptance criteria.',
    ]
    assert captured['approved_material'] == lesson()['approved_material']
    assert 'Instructor sub-questions to address:' not in captured['approved_material']
    assert response.json()['bounded_flow'] is True


@pytest.mark.parametrize('stage', ['document analysis', 'lesson generation'])
def test_timeout_reports_stage_without_provider_details(client, monkeypatch, stage):
    from app import main
    from fastapi import HTTPException
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout('private upstream connection details')
    monkeypatch.setattr(main, 'discover_resources', lambda *args: [])
    monkeypatch.setattr(main, 'verify_resources', lambda *args: [])
    kwargs = {}
    if stage == 'document analysis':
        monkeypatch.setattr(main, 'infer_document_context', timeout)
    else:
        kwargs = {'learning_focus': 'Requirements', 'starting_point': 'Programming', 'ending_point': 'Apply requirements'}
        monkeypatch.setattr(main, 'generate_learning_plan', timeout)
    with pytest.raises(HTTPException) as caught:
        main._document_plan(lesson()['approved_material'], 'course.pdf', **kwargs)
    assert caught.value.status_code == 504
    assert stage in caught.value.detail
    assert 'private upstream' not in caught.value.detail


def test_document_only_preview_still_infers_context(client, monkeypatch):
    from app import main
    calls = []
    def infer(material, filename):
        calls.append(filename)
        return {'topic': 'Requirements', 'objective_descriptions': ['Apply requirements']}
    monkeypatch.setattr(main, 'infer_document_context', infer)
    monkeypatch.setattr(main, 'discover_resources', lambda *args: [])
    monkeypatch.setattr(main, 'verify_resources', lambda *args: [])
    monkeypatch.setattr(main, 'generate_learning_plan', lambda *args, **kwargs: lesson())
    response = client.post('/api/instructor/document-draft', headers=headers('instructor-demo'),
                           json={'filename': 'course.txt', 'material': lesson()['approved_material']})
    assert response.status_code == 200
    assert calls == ['course.txt']
