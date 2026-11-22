"""Optional expansion stays unapproved until instructor review; no network needed."""
import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from app import openai_client, platform_lessons

spec = importlib.util.spec_from_file_location('sdl_material', Path(__file__).resolve().parents[3] / 'platform_app/sdl_material.py')
material_rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(material_rules)


def config():
    result = {'starting_point': 'Variables and functions', 'ending_point': 'Create a class and two objects',
              'prompt': 'Python classes and objects', 'material_expansion': 'A class defines attributes and methods. Each instance has its own state.',
              'expansion_approved': True}
    result['expansion_source_hash'] = material_rules.expansion_source_hash('OOP', result)
    return result


def test_source_bound_expansion_requires_approval_and_matching_published_plan():
    settings = config()
    assert material_rules.checked_expansion('OOP', settings) == settings['material_expansion']
    assert material_rules.checked_expansion('OOP', settings, {'supplemental_material': settings['material_expansion']})
    settings['expansion_approved'] = False
    with pytest.raises(ValueError, match='approve'):
        material_rules.checked_expansion('OOP', settings)
    assert material_rules.checked_expansion('OOP', {}) == ''


@pytest.mark.parametrize('field', ['starting_point', 'ending_point', 'prompt', 'source'])
def test_changed_source_or_scope_invalidates_expansion(field):
    settings = config()
    material = 'OOP'
    if field == 'source': material = 'Changed source'
    else: settings[field] += ' changed'
    with pytest.raises(ValueError, match='scope changed'):
        material_rules.checked_expansion(material, settings)


def test_editing_additions_requires_regenerating_the_assessment_before_publish():
    settings = config()
    settings['material_expansion'] += ' Teacher edit.'
    with pytest.raises(ValueError, match='Review the activity again'):
        material_rules.checked_expansion('OOP', settings, {'supplemental_material': 'Previous version'})


def mock_provider(monkeypatch, result):
    monkeypatch.setattr(openai_client, 'runtime_ai_mode', lambda: 'openai')
    monkeypatch.setattr(openai_client, '_chat_settings', lambda: ('https://provider.invalid', 'model', {}))
    seen = {}
    class Provider:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            seen.update(kwargs['json'])
            return httpx.Response(200, request=httpx.Request('POST', 'https://provider.invalid'), json={
                'choices': [{'message': {'content': json.dumps(result)}}]})
    monkeypatch.setattr(openai_client.httpx, 'Client', Provider)
    return seen


def test_expansion_is_one_scoped_draft_call_without_assessment_generation(monkeypatch):
    seen = mock_provider(monkeypatch, {'additions': 'Classes define structure. Objects are individual instances. Example: two books have separate identifiers.', 'clarification_needed': ''})
    result = openai_client.expand_teaching_material('OOP', 'Slides', 'Python objects', 'Variables', 'Instantiate two objects')
    assert result.startswith('Classes define structure.')
    payload = json.loads(seen['messages'][1]['content'])
    assert payload['material'] == 'OOP'
    assert payload['ending_outcomes'] == 'Instantiate two objects'
    assert 'Do not generate quiz' in seen['messages'][0]['content']
    assert 'No web search is being performed' in seen['messages'][0]['content']


@pytest.mark.parametrize('result', [
    {'additions': '', 'clarification_needed': ''},
    {'additions': 'x' * 12001, 'clarification_needed': ''},
    {'additions': 'Draft', 'clarification_needed': 'Specify the programming language.'},
    {'additions': ['bad shape'], 'clarification_needed': ''},
    {'unexpected': True},
])
def test_invalid_or_ambiguous_expansion_does_not_silently_generate_content(monkeypatch, result):
    mock_provider(monkeypatch, result)
    with pytest.raises(ValueError):
        openai_client.expand_teaching_material('OOP', 'Slides', 'Objects', 'Variables', 'Instantiate objects')


def test_approved_additions_feed_preparation_and_are_saved_for_students(monkeypatch):
    from app import main
    seen = {}
    def prepare(material, filename, **kwargs):
        seen.update(material=material, **kwargs)
        return {'approved_material': material}
    monkeypatch.setattr(main, '_document_plan', prepare)
    additions = 'Explain how each instance has separate state.\n\nExample: two Book instances have separate IDs.'
    body = platform_lessons.PrepareInput(material='OOP', filename='Slides', focus='Python objects', starting_point='Variables', ending_point='Create two instances', supplemental_material=additions)
    plan = platform_lessons.prepare(body)
    assert additions in seen['material']
    assert plan['supplemental_material'] == additions
    assert additions in plan['approved_material']
    body.material = 'x' * 30000
    body.focus = 'Focus ' * 1500
    plan = platform_lessons.prepare(body)
    assert len(plan['approved_material']) <= 30000
    assert plan['approved_material'].endswith(additions)


def test_sparse_material_without_expansion_and_unspecified_scope_are_rejected():
    with pytest.raises(HTTPException):
        platform_lessons.prepare(platform_lessons.PrepareInput(material='OOP', filename='Slides', starting_point='Variables', ending_point='Create instances'))
    with pytest.raises(ValueError, match='starting point'):
        # Scope check occurs before any provider request.
        openai_client.expand_teaching_material('OOP', 'Slides', 'Objects', '', '')
