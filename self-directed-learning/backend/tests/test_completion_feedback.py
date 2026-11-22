import json

import pytest

from app import completion_feedback as feedback


PLAN = {'objectives': [{'id': 'o1', 'title': 'Protect the Sprint Goal'}],
        'diagnostic_quiz': [{'id': 'q1', 'objective_id': 'o1', 'concept': 'Sprint Goal',
            'question': 'How should a team handle a change?', 'options': ['Negotiate scope', 'Add all work'],
            'correct_index': 0, 'explanation': 'Negotiate scope without endangering the Sprint Goal.'}],
        'application_rubric': [{'description': 'Justify the tradeoff'}]}


def profile(kind):
    attempts = [{'option_index': 0, 'correct': True, 'assistance': [], 'explanation': 'Protect the agreed goal.'}]
    if kind == 'improves':
        attempts = [{'option_index': 1, 'correct': False, 'assistance': []},
                    {'option_index': 0, 'correct': True, 'assistance': ['feedback_hint', 'worked_example_hint', 'reading']}]
    answer = 'I would negotiate scope to protect the goal because adding work risks the agreed outcome.'
    if kind == 'weak_application':
        answer = 'Just do it.'
    return {'quiz_attempts': {'q1': attempts}, 'assistance': {'q1': attempts[-1]['assistance']},
            'application_answers': [{'prompt': 'Handle a new request.', 'answer': answer}],
            'interview_answers': [{'question': 'What if capacity falls?', 'answer': 'Reassess the scope against the same goal.' if kind != 'weak_application' else 'I am not sure.'}],
            'reflections': [{'content': 'I learned to separate scope from the goal.'}],
            'application_assessment': {'status': 'assessed',
                'feedback': ('Your response does not connect the decision to the Sprint Goal, and the interview does not explain a change in capacity.' if kind == 'weak_application' else
                             'Your scope negotiation explains how added work could risk the agreed outcome; the interview applies that same goal when capacity changes.'),
                'next_step': {'action': ('Explain what you would defer and why if capacity fell.' if kind == 'weak_application' else
                                        'Test your scope decision against a request that would change the Sprint Goal.'),
                              'self_check': 'Which part of your decision changes, and which part stays fixed?'}}}


@pytest.mark.parametrize('kind', ['strong', 'improves', 'weak_application'])
def test_generator_receives_full_profile_and_checks_quotes(monkeypatch, kind):
    state = profile(kind)
    evidence = feedback.evidence_for(state, PLAN)
    written = next(e for e in evidence if e['kind'] == 'application')
    text = {
        'strong': 'You selected scope negotiation independently. Your explanation connects the decision to protecting the agreed outcome.',
        'improves': 'Your initial selection added all work. After the recorded hints and reading, you selected scope negotiation correctly, showing improvement with support.',
        'weak_application': 'Your quiz selection was independently correct. Your written application still needs a reason connecting the decision to the goal.',
    }[kind]
    cards = [{'key': key, 'text': text if key != 'application' else
              ('Your response says “Just do it.” It does not explain a tradeoff or what would change the decision.' if kind == 'weak_application' else
               'You propose negotiating scope to protect the goal. Your response explains why added work could threaten the agreed outcome.'),
              'evidence': [{'id': written['id'], 'quote': written['answer']}] if key == 'application' else
                          [{'id': evidence[0]['id'], 'quote': evidence[0]['answer']}]} for key, _ in feedback.CARDS]

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            payload = json.loads(kwargs['json']['messages'][1]['content'])
            assert payload['objectives'] == PLAN['objectives']
            assert {e['kind'] for e in payload['evidence']} == {'quiz', 'application', 'interview', 'reflection'}
            quiz = [e for e in payload['evidence'] if e['kind'] == 'quiz']
            assert len(quiz) == (2 if kind == 'improves' else 1)
            if kind == 'improves':
                assert quiz[0]['correct'] is False
                assert quiz[1]['assistance'] == ['feedback_hint', 'worked_example_hint', 'reading']
            return self
        def raise_for_status(self): pass
        def json(self): return {'choices': [{'message': {'content': json.dumps({'cards': cards})}}]}

    monkeypatch.setattr(feedback.ai, 'runtime_ai_mode', lambda: 'openai')
    monkeypatch.setattr(feedback.httpx, 'Client', Client)
    result = feedback.generate_cards(state, PLAN)
    assert result['source'] == 'ai'
    assert [c['title'] for c in result['cards']] == [title for _, title in feedback.CARDS]
    assert result['cards'][0]['text'] == text


def test_fallback_distinguishes_independent_from_assisted_progress(monkeypatch):
    monkeypatch.setattr(feedback.ai, 'runtime_ai_mode', lambda: 'demo')
    strong = feedback.generate_cards(profile('strong'), PLAN)['cards']
    improved = feedback.generate_cards(profile('improves'), PLAN)['cards']
    assert 'without recorded hints' in strong[0]['text']
    assert 'after support or a retry' in improved[0]['text']
    assert 'resolved during the quiz' in improved[1]['text']


def test_missing_evidence_never_becomes_an_achievement_or_weakness(monkeypatch):
    monkeypatch.setattr(feedback.ai, 'runtime_ai_mode', lambda: 'openai')
    result = feedback.generate_cards({}, PLAN)
    assert result['source'] == 'recorded_evidence'
    assert len(result['cards']) == 4
    assert all(not c['evidence'] for c in result['cards'])
    assert 'cannot be assessed' in result['cards'][2]['text']
    assert 'Missing evidence is not an incorrect answer' in result['cards'][1]['text']


def test_provider_failure_does_not_block_completion(monkeypatch):
    monkeypatch.setattr(feedback.ai, 'runtime_ai_mode', lambda: 'openai')
    def unavailable(**kwargs):
        raise feedback.httpx.ConnectError('offline')
    monkeypatch.setattr(feedback.httpx, 'Client', unavailable)
    assert feedback.generate_cards(profile('strong'), PLAN)['source'] == 'recorded_evidence'


def test_fallback_reuses_saved_reasoning_assessment_and_prioritized_action(monkeypatch):
    monkeypatch.setattr(feedback.ai, 'runtime_ai_mode', lambda: 'demo')
    state = profile('weak_application')
    state['application_assessment'] = {'status': 'assessed',
        'feedback': 'Your response does not explain how the decision protects the Sprint Goal.',
        'next_step': {'action': 'Add one tradeoff to your scope decision.', 'self_check': 'What would you defer if capacity fell?'}}
    cards = feedback.generate_cards(state, PLAN)['cards']
    assert state['application_assessment']['feedback'] in cards[2]['text']
    assert 'Just do it.' in cards[2]['text']
    assert 'What would you defer if capacity fell?' in cards[3]['text']


@pytest.mark.parametrize('invalid', ['invented_quote', 'missing_card', 'quiz_only_application'])
def test_unsupported_ai_output_uses_factual_fallback(monkeypatch, invalid):
    cards = [{'key': key, 'text': 'This is a detailed narrative tied to recorded student answers.',
              'evidence': [{'id': 'application:1', 'quote': profile('strong')['application_answers'][0]['answer']}]} for key, _ in feedback.CARDS]
    if invalid == 'invented_quote':
        cards[0]['evidence'][0]['quote'] = 'An achievement the student never described'
    elif invalid == 'missing_card':
        cards.pop()
    else:
        cards[2]['evidence'] = [{'id': 'quiz:q1:1', 'quote': 'Negotiate scope'}]

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): return self
        def raise_for_status(self): pass
        def json(self): return {'choices': [{'message': {'content': json.dumps({'cards': cards})}}]}
    monkeypatch.setattr(feedback.ai, 'runtime_ai_mode', lambda: 'openai')
    monkeypatch.setattr(feedback.httpx, 'Client', Client)
    result = feedback.generate_cards(profile('strong'), PLAN)
    assert result['source'] == 'recorded_evidence'
    assert len(result['cards']) == 4
