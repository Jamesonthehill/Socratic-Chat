"""Structural authoring checks; these do not certify semantic teaching quality."""
import re


def normalized(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))


def compose_question(scenario, question):
    """Keep scenario text once, including when a provider embeds it in the stem."""
    scenario, question = scenario.strip(), question.strip()
    if not scenario or f' {normalized(scenario)} ' in f' {normalized(question)} ':
        return question
    # Remove exact repeated setup sentences; preserve the actual question wording.
    setup = {normalized(s) for s in re.split(r'(?<=[.!?])\s+', scenario) if normalized(s)}
    remaining = [s for s in re.split(r'(?<=[.!?])\s+', question)
                 if normalized(s) not in setup]
    return scenario + '\n\n' + ' '.join(remaining) if remaining else scenario


def lesson_scope(focus, ending_point):
    """Keep explicit instructor sub-questions separate from the short topic title."""
    topic, separator, questions = focus.partition('\nInstructor sub-questions to address:\n')
    requirements = [line.strip() for line in ending_point.splitlines() if line.strip()]
    if separator:
        requirements.extend(line.strip().removeprefix('- ').strip()
                            for line in questions.splitlines() if line.strip())
    return topic.strip()[:200], list(dict.fromkeys(requirements))


def generation_issues(plan):
    if plan.get('generation_quality_version', 0) != 1:
        return []
    issues = []
    assessments = {f"quiz:{q['id']}" for q in plan.get('diagnostic_quiz', [])}
    assessments.update(f"application:{s['id']}" for s in plan.get('application_sections', []))
    if not plan.get('application_sections') and plan.get('required_task'):
        assessments.add('application:required_task')
    requirements = plan.get('coverage_requirements', [])
    ids = [item.get('id') for item in requirements]
    expected = plan.get('instructor_requirements', [])
    if (not expected or ids != [f'REQ{index + 1}' for index in range(len(expected))]
            or [item.get('description') for item in requirements] != expected):
        issues.append('Preserve every instructor coverage requirement, in order, before publishing.')
    for item in requirements:
        references = item.get('assessment_ids', [])
        if (not item.get('description', '').strip() or not references
                or len(set(references)) != len(references) or set(references) - assessments):
            issues.append(f"Coverage {item.get('id', '?')}: identify valid quiz/application tasks that assess this requirement.")

    def check_rubrics(value):
        if isinstance(value, dict):
            if 'description' in value and 'evidence_groups' in value:
                description = normalized(value['description'])
                for group in value['evidence_groups']:
                    examples = [normalized(example) for example in group]
                    if (len(set(examples)) < 2 or any(not example for example in examples)
                            or len(set(examples)) != len(examples) or description in examples):
                        issues.append('Rubric evidence groups need at least two distinct equivalent examples of student reasoning, not copies of the criterion. Leave groups empty when no useful alternatives are available.')
            for item in value.values():
                check_rubrics(item)
        elif isinstance(value, list):
            for item in value:
                check_rubrics(item)

    check_rubrics(plan)
    return list(dict.fromkeys(issues))
