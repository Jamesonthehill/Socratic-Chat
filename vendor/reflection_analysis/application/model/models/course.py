from typing import List, Optional, Dict, Any
from application.model.models.student import Student

class Course:
    def __init__(self, course_name: str):
        self.course_name = course_name
        self.students: Dict[str, Student] = {}  # Dictionary with email as key
        self.reflection_numbers: set = set()  # Track available reflection numbers
        self.filtered_total_students: int = 0  # Store filtered total student count
        self.total_reflections_submitted: int = 0  # Track total number of reflections submitted
        self.num_students_with_email_id: int = 0  # Track number of students with email-format IDs
        self.matching_students_count: int = 0  # Track students who can be matched between reflection and grade files

    def add_student(self, student: Student) -> None:
        """Add or update a student in the course"""
        self.students[student.email] = student

    def get_student_by_email(self, email: str) -> Optional[Student]:
        """Get student by email (or username part of email)"""
        # Try exact match first
        if email in self.students:
            return self.students[email]

        # Try matching username part
        username = email.split('@')[0].lower()
        for student_email, student in self.students.items():
            if student_email.split('@')[0].lower() == username:
                return student
        return None

    def add_reflection_number(self, ref_num: int) -> None:
        """Add a reflection number to the course"""
        self.reflection_numbers.add(ref_num)

    def get_all_reflection_numbers(self) -> List[int]:
        """Get all reflection numbers in sorted order"""
        return sorted(list(self.reflection_numbers))

    def set_filtered_total_students(self, count: int) -> None:
        self.filtered_total_students = count

    def set_total_reflections_submitted(self, count: int) -> None:
        self.total_reflections_submitted = count

    def get_total_reflections_submitted(self) -> int:
        return self.total_reflections_submitted

    def set_num_students_with_email_id(self, count: int) -> None:
        self.num_students_with_email_id = count

    def get_num_students_with_email_id(self) -> int:
        return self.num_students_with_email_id

    def set_matching_students_count(self, count: int) -> None:
        """Set the number of students who can be matched between reflection and grade files"""
        self.matching_students_count = count

    def get_matching_students_count(self) -> int:
        """Get the number of students who can be matched between reflection and grade files"""
        return self.matching_students_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            'course_name': self.course_name,
            'reflection_numbers': sorted(list(self.reflection_numbers)),
            'students': [student.to_dict() for student in self.students.values()],
            'filtered_total_students': self.filtered_total_students,
            'total_reflections_submitted': self.total_reflections_submitted,
            'num_students_with_email_id': self.num_students_with_email_id,
            'matching_students_count': self.matching_students_count
        }
