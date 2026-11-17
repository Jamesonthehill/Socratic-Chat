import pandas as pd
from typing import Dict, List, Tuple, Optional

class GradeService:
    @staticmethod
    def get_current_grade(grades: Dict) -> float:
        """Extract current grade from grades dictionary"""
        # Look specifically for "Current Score" category
        for key, value in grades.items():
            if key == "Current Score":
                try:
                    return float(value) if pd.notna(value) else 0.0
                except (ValueError, TypeError):
                    return 0.0
        return 0.0

    @staticmethod
    def get_grade_change(prev_grade: float, curr_grade: float) -> Tuple[str, str]:
        """Calculate grade change and return formatted string and class"""
        if pd.isna(prev_grade) or pd.isna(curr_grade):
            return "", ""

        change = curr_grade - prev_grade
        if change == 0:
            return "0", "neutral"

        change_str = f"{'+' if change > 0 else ''}{change:.1f}"
        change_class = "positive" if change > 0 else "negative"
        return change_str, change_class

    @staticmethod
    def get_missing_grades(student_grades: Dict, all_grades: Dict) -> List[str]:
        """Find missing grades by comparing with other students"""
        missing = []
        for key, value in student_grades.items():
            try:
                if pd.isna(value):
                    continue
                student_value = float(value)
                max_value = float(all_grades.get(key, 0))
                if student_value == 0 and max_value > 1:
                    missing.append(key)
            except (ValueError, TypeError):
                continue
        return missing

    @staticmethod
    def get_previous_grade(student, current_ref: int, key: str) -> Optional[float]:
        """Get grade from previous reflection period"""
        prev_ref = current_ref - 1
        if prev_ref in student.reflection_data:
            prev_grades = student.reflection_data[prev_ref]['grades']
            if prev_grades and key in prev_grades:
                try:
                    return float(prev_grades[key]) if pd.notna(prev_grades[key]) else None
                except (ValueError, TypeError):
                    return None
        return None

    @staticmethod
    def calculate_all_grades(student) -> Dict:
        """Calculate all possible grades for comparison"""
        all_grades = {}
        for ref_data in student.reflection_data.values():
            if ref_data['grades']:
                for key, value in ref_data['grades'].items():
                    try:
                        current_max = float(all_grades.get(key, 0))
                        new_value = float(value)
                        all_grades[key] = max(current_max, new_value)
                    except (ValueError, TypeError):
                        continue
        return all_grades

    @staticmethod
    def get_missing_assignments_by_period(student, ref_num: int, all_students_data: Dict) -> List[str]:
        """
        Get missing assignments for a specific reflection period by comparing with other students

        Args:
            student: Current student being checked
            ref_num: Reflection period number
            all_students_data: Dictionary containing all students' reflection data

        Returns:
            List of missing assignment names
        """
        missing = []

        # Get current student's grades for this period
        if ref_num not in student.reflection_data or not student.reflection_data[ref_num]['grades']:
            return missing

        current_student_grades = student.reflection_data[ref_num]['grades']

        # Find maximum grades for each assignment across all students for this period
        max_grades = {}
        for other_student_data in all_students_data.values():
            if (ref_num in other_student_data.reflection_data and
                other_student_data.reflection_data[ref_num]['grades']):

                other_grades = other_student_data.reflection_data[ref_num]['grades']
                for key, value in other_grades.items():
                    try:
                        if pd.isna(value) or 'unposted' in key.lower():
                            continue
                        grade_value = float(value)
                        current_max = float(max_grades.get(key, 0))
                        max_grades[key] = max(current_max, grade_value)
                    except (ValueError, TypeError):
                        continue

        # Check which assignments are missing for current student
        for key, max_value in max_grades.items():
            try:
                student_value = float(current_student_grades.get(key, 0))
                # If others have done it (max > 0) but student hasn't (value = 0)
                if max_value > 0 and student_value == 0:
                    missing.append(key)
            except (ValueError, TypeError):
                continue

        return missing
