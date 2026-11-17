"""Versioned defaults for the short-answer SDL assessment."""

import re

from .schemas import ApplicationInterviewQuestion

ASSESSMENT_VERSION = 2
QUIZ_LEVELS = ["foundational", "understanding", "application"]
APPLICATION_COUNT = 3
INTERVIEW_COUNT = 2
GROUNDING_VERSION = 1


def structured(plan):
    return plan.get("bounded_flow") and plan.get("assessment_version", 1) == ASSESSMENT_VERSION


def normalized(text):
    return ' '.join(text.casefold().split())


def validate_interview_questions(questions, answers, application_prompts=None):
    """Check provenance and distinct purposes; this is not an AI semantic review."""
    if not isinstance(questions, list) or len(questions) != INTERVIEW_COUNT:
        return None
    if not isinstance(answers, list) or any(not isinstance(a, dict) or not isinstance(a.get('id'), str) or not a['id'].strip()
            or not isinstance(a.get('answer'), str) for a in answers):
        return None
    sources = {answer['id']: answer['answer'] for answer in answers}
    if len(sources) != len(answers):
        return None
    try:
        checked = [ApplicationInterviewQuestion.model_validate(q).model_dump() for q in questions]
    except (ValueError, TypeError):
        return None
    if [q['purpose'] for q in checked] != ['justification', 'changed_condition']:
        return None
    prompts = []
    for question in checked:
        source = sources.get(question['source_application_id'])
        quote = question['source_quote'].strip()
        prompt = question['prompt'].strip()
        if (not source or not quote or not prompt
                or len(normalized(quote)) < min(20, len(normalized(source)))
                or not re.search(r'(?<!\w)' + re.escape(quote) + r'(?!\w)', source)):
            return None
        condition = question['changed_condition'].strip()
        if (question['purpose'] == 'changed_condition') != bool(condition):
            return None
        question['source_quote'] = question['source_quote'].strip()
        question['prompt'] = prompt
        question['changed_condition'] = condition
        prompts.append(re.sub(r'[^\w\s]', '', normalized(prompt)))
    # Catch literal/near-literal repeats after punctuation and whitespace cleanup.
    if application_prompts:
        originals = [re.sub(r'[^\w\s]', '', normalized(prompt)) for prompt in application_prompts]
        if any(prompt == original for prompt in prompts for original in originals):
            return None
    if prompts[0] == prompts[1] or set(prompts[0].split()) == set(prompts[1].split()):
        return None
    return checked


def interview_prompt(question):
    """Render verified references ourselves; keep saved string questions readable."""
    if isinstance(question, str):
        return question
    reference = f"You wrote: “{question['source_quote']}”"
    condition = f"\n\nChanged condition: {question['changed_condition']}" if question['purpose'] == 'changed_condition' else ''
    return reference + condition + '\n\n' + question['prompt']
