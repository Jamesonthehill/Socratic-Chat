from typing import Dict
from application.html_builder.services.grade_service import GradeService
from application.html_builder.templates.template_manager import TemplateManager
import pandas as pd
from pathlib import Path
import os

class StudentProfileBuilder:
    def __init__(self):
        self.grade_service = GradeService()
        self.template_manager = TemplateManager()
        self.template = self.template_manager.load_template('student_profile')

    def build_profile(self, student, course=None) -> str:
        """Build student profile HTML"""
        try:
            student_prefix = student.email.split('@')[0]
            print(f"\nBuilding profile for student: {student.name}")
            print(f"Student email prefix: '{student_prefix}'")
            print(f"Section: {getattr(student, 'section', None)}")

            # Get the most recent reflection number
            reflection_numbers = sorted(student.reflection_data.keys(), reverse=True)
            current_ref_num = reflection_numbers[0] if reflection_numbers else None
            previous_ref_num = reflection_numbers[1] if len(reflection_numbers) > 1 else None

            # Get current and previous grades
            current_grade = 0.0
            previous_grade = 0.0

            if current_ref_num and current_ref_num in student.reflection_data:
                if student.reflection_data[current_ref_num]['grades']:
                    current_grade = self.grade_service.get_current_grade(student.reflection_data[current_ref_num]['grades'])

            if previous_ref_num and previous_ref_num in student.reflection_data:
                if student.reflection_data[previous_ref_num]['grades']:
                    previous_grade = self.grade_service.get_current_grade(student.reflection_data[previous_ref_num]['grades'])

            # Calculate grade change
            grade_change = current_grade - previous_grade

            # Process each reflection period
            for ref_num, data in student.reflection_data.items():
                try:
                    # Load analysis results from the results directory
                    results_path = os.path.join(
                        "application", "model", "reflections",
                        course.course_name,
                        f"ref{ref_num}",
                        "results",
                        f"{course.course_name}_ref{ref_num}_exploded.csv"
                    )

                    if os.path.exists(results_path):
                        print(f"Loading analysis results from: {results_path}")
                        analysis_df = pd.read_csv(results_path)

                        # Find this student's analysis results by matching email prefix
                        student_analysis = analysis_df[
                            analysis_df['ID'].str.lower().str.startswith(student_prefix.lower())
                        ]

                        if not student_analysis.empty:
                            # Update reflection data with analysis results
                            data['topic_analysis'] = [{
                                'primary_topic': row['primary_labels_selected'],
                                'resolution_status': row['resolution_primary_labels'],
                                'urgency': row.get('urgency', 'medium'),
                            } for _, row in student_analysis.iterrows()]

                            data['reflection_summary'] = student_analysis.iloc[0].get('reflection_summary', '')
                            data['instructor_suggestions'] = student_analysis.iloc[0].get('instructor_suggestions', '')
                            print(f"Added analysis results for ref{ref_num}")
                        else:
                            print(f"No analysis results found for student {student_prefix}")
                    else:
                        print(f"No analysis results found at: {results_path}")

                except Exception as e:
                    print(f"Error processing ref {ref_num}: {e}")
                    continue

            all_grades = self.grade_service.calculate_all_grades(student)

            # Get all students' data from the course
            all_students_data = course.students if course else {}

            # Get status indicators
            has_latest_reflection = (current_ref_num in student.reflection_data and
                                   student.reflection_data[current_ref_num]['reflection'] is not None)

            # Get grade color
            def get_grade_color(grade):
                if grade >= 90: return "green"
                if grade >= 80: return "blue"
                if grade >= 70: return "orange"
                return "red"

            # Get grade indicators
            grade_color = get_grade_color(current_grade)
            grade_trend = "up" if grade_change > 0 else "down" if grade_change < 0 else "neutral"

            # Prepare template context
            context = {
                'student': student,
                'zip': zip,
                'ref1_grade': previous_grade,
                'ref2_grade': current_grade,
                'grade_change': grade_change,
                'get_missing_grades': lambda grades: self.grade_service.get_missing_grades(grades, all_grades),
                'all_grades': all_grades,
                'isna': pd.isna,
                'get_previous_grade': self.grade_service.get_previous_grade,
                'get_grade_change': self.grade_service.get_grade_change,
                'get_missing_assignments_by_period': lambda s, r: self.grade_service.get_missing_assignments_by_period(s, r, all_students_data),
                'status_indicators': {
                    'grade_color': grade_color,
                    'has_latest_reflection': has_latest_reflection,
                    'grade_trend': grade_trend
                }
            }

            return self.template_manager.render_student_profile(self.template, context)

        except Exception as e:
            print(f"Error building profile for {student.name}: {e}")
            return f"<div>Error building profile for {student.name}</div>"

    def build_profile_old(self, student, course=None) -> str:
        """
        Build HTML profile for a student

        Args:
            student: The student to build profile for
            course: Course object containing all students' data
        """
        try:
            # Get grades and changes
            ref1_grade = 0.0
            ref2_grade = 0.0
            if 1 in student.reflection_data and student.reflection_data[1]['grades']:
                ref1_grade = self.grade_service.get_current_grade(student.reflection_data[1]['grades'])
            if 2 in student.reflection_data and student.reflection_data[2]['grades']:
                ref2_grade = self.grade_service.get_current_grade(student.reflection_data[2]['grades'])

            grade_change = ref2_grade - ref1_grade
            all_grades = self.grade_service.calculate_all_grades(student)

            # Get all students' data from the course
            all_students_data = course.students if course else {}

            # Get status indicators
            has_latest_reflection = (2 in student.reflection_data and
                                   student.reflection_data[2]['reflection'] is not None)

            # Get grade color
            def get_grade_color(grade):
                if grade >= 90: return "green"
                if grade >= 80: return "blue"
                if grade >= 70: return "orange"
                return "red"

            # Get grade indicators
            grade_color = get_grade_color(ref2_grade)
            grade_trend = "up" if grade_change > 0 else "down" if grade_change < 0 else "neutral"

            # Prepare template context
            context = {
                'student': student,
                'zip': zip,
                'ref1_grade': ref1_grade,
                'ref2_grade': ref2_grade,
                'grade_change': grade_change,
                'get_missing_grades': lambda grades: self.grade_service.get_missing_grades(grades, all_grades),
                'all_grades': all_grades,
                'isna': pd.isna,
                'get_previous_grade': self.grade_service.get_previous_grade,
                'get_grade_change': self.grade_service.get_grade_change,
                'get_missing_assignments_by_period': lambda s, r: self.grade_service.get_missing_assignments_by_period(s, r, all_students_data),
                'status_indicators': {
                    'grade_color': grade_color,
                    'has_latest_reflection': has_latest_reflection,
                    'grade_trend': grade_trend
                }
            }

            return self.template_manager.render_student_profile(self.template, context)

        except Exception as e:
            print(f"Error building profile for {student.name}: {e}")
            return f"<div>Error building profile for {student.name}</div>"
