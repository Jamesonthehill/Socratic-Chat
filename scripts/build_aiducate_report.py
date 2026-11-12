"""Adapt AIDucate records to the original reflection_analysis HTML builder."""
import csv
from collections import Counter
from contextlib import redirect_stdout
from html import escape
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory


def write_csv(path, rows, headers):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dict.fromkeys(headers)))
        writer.writeheader()
        writer.writerows(rows)


def safe_text(value):
    return escape(value).replace("\\", "&#92;").replace("`", "&#96;").replace("$", "&#36;")


def render(payload):
    from application.html_builder.builder import HTMLBuilder
    from application.model.models.course import Course
    from application.model.models.reflection import Reflection
    from application.model.models.student import Student
    from plotly.offline import get_plotlyjs

    course = Course("Reflection")
    course.add_reflection_number(1)
    period = Path("application/model/reflections/Reflection/ref1")
    results = period / "results"
    results.mkdir(parents=True)
    reflections, grades, annotations = [], [], []
    missing_by_email = {}
    annotation_fields = ["primary_labels_selected", "resolution_primary_labels", "urgency",
                         "reflection_summary", "instructor_suggestions"]
    width = len(str(len(payload["students"])))
    for index, row in enumerate(payload["students"], 1):
        student_id = f"student{index:0{width}d}"
        email = f"{student_id}@domain.edu"
        student = Student(name=f"Student {index}", email=email, course=course.course_name)
        course.add_student(student)
        answers = {safe_text(question): safe_text(answer) for question, answer in row["answers"].items()}
        answers.pop("ID", None)
        if answers:
            reflection = Reflection({"ID": email})
            reflection.reflection_number = 1
            reflection.questions = list(answers)
            reflection.reflections = list(answers.values())
            student.add_reflection_data(1, reflection=reflection)
            reflections.append({"ID": email, **answers})
        grade_values = {safe_text(name): value for name, value in row["grades"].items()}
        if grade_values:
            student.add_reflection_data(1, grades=grade_values)
            grades.append({**grade_values, "Student": student.name, "SIS Login ID": student_id, "ID": email})
        missing_by_email[email] = [safe_text(name) for name in row["missing_assignments"]]
        annotation = row.get("analysis")
        if annotation:
            for topic, resolution in zip(annotation["primary_labels_selected"], annotation["resolution_primary_labels"]):
                annotations.append(dict(zip(annotation_fields, [
                    topic, resolution, annotation["urgency"], safe_text(annotation["reflection_summary"]),
                    safe_text(annotation["instructor_suggestions"]),
                ]), ID=email))
    write_csv(period / "Reflection_ref1.csv", reflections, ["ID", *(key for row in reflections for key in row)])
    if grades:
        write_csv(period / "Reflection_grades_ref1.csv", grades, ["ID", "Student", "SIS Login ID", *(key for row in grades for key in row)])
    if annotations:
        write_csv(results / "Reflection_ref1_exploded.csv", annotations, ["ID", *annotation_fields])

        counts = Counter((row["primary_labels_selected"], row["resolution_primary_labels"])
                         for row in annotations)
        plot_rows = [{"Topic": topic, "Resolution Status": status, "Count": count}
                     for (topic, status), count in counts.items()]
        write_csv(results / "Reflection_ref1_plot_data.csv", plot_rows,
                  ["Topic", "Resolution Status", "Count"])

    builder = HTMLBuilder(topic_data_path=period.parent.parent)
    builder.student_profile_builder.grade_service.get_missing_assignments_by_period = (
        lambda student, _period, _students: missing_by_email.get(student.email, [])
    )
    report = builder.build_student_profiles(course, anonymized=False)
    if not report.strip():
        raise RuntimeError("Report builder returned an empty report")
    report = re.sub(r'<script[^>]+src="https://cdn\.plot\.ly/[^"]+"[^>]*></script>', "", report)
    policy = '''<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; form-action 'none'">'''
    report = report.replace("<head>", f"<head>{policy}", 1)
    return report.replace("</head>", f"<script>{get_plotlyjs()}</script></head>", 1)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
    payload = json.load(sys.stdin)
    with TemporaryDirectory(prefix="aiducate-report-") as directory:
        os.chdir(directory)
        with open(os.devnull, "w") as quiet, redirect_stdout(quiet):
            report = render(payload)
    sys.stdout.write(report)
