from typing import Optional, Dict, Any
from application.model.models.reflection import Reflection

class Student:
    VALID_DOMAINS = ['charlotte.edu', 'uncc.edu', 'domain.edu']

    def __init__(self, name: str, email: str, course: str):
        self.name = name
        self.email = self._validate_and_format_email(email)
        self.course = course
        self.section = None  # Add section attribute
        # Dictionary with reflection number as key, containing both reflection and grades
        self.reflection_data: Dict[int, Dict[str, Any]] = {}  # {ref_num: {'reflection': Reflection, 'grades': dict}}

    def _validate_and_format_email(self, email: str) -> str:
        """Validate and format email to ensure it's a valid UNCC email."""
        if email == "Not Set":
            return email

        # If it's already an email, validate domain
        if "@" in email:
            username, domain = email.lower().split("@")
            if domain in self.VALID_DOMAINS:
                return f"{username}@{domain}"
            else:
                raise ValueError(f"Invalid email domain. Must be one of: {', '.join(self.VALID_DOMAINS)}")

        # If it's just an ID, append the primary domain
        return f"{email.lower()}@{self.VALID_DOMAINS[0]}"

    def is_valid_email(self, email: str) -> bool:
        """Check if email is valid."""
        try:
            self._validate_and_format_email(email)
            return True
        except ValueError:
            return False

    def add_reflection_data(self, ref_num: int, reflection: Optional[Reflection] = None, grades: Optional[dict] = None):
        """Add or update reflection data for a specific reflection number"""
        if ref_num not in self.reflection_data:
            self.reflection_data[ref_num] = {'reflection': None, 'grades': None}

        if reflection:
            self.reflection_data[ref_num]['reflection'] = reflection
        if grades:
            self.reflection_data[ref_num]['grades'] = grades

    def get_reflection_data(self, ref_num: int) -> dict:
        """Get reflection and grades for a specific reflection number"""
        return self.reflection_data.get(ref_num, {'reflection': None, 'grades': None})

    def has_reflection(self, ref_num: int) -> bool:
        """Check if student has submitted a reflection for this number"""
        data = self.reflection_data.get(ref_num)
        return data is not None and data['reflection'] is not None

    def has_grades(self, ref_num: int) -> bool:
        """Check if student has grades for this reflection number"""
        data = self.reflection_data.get(ref_num)
        return data is not None and data['grades'] is not None

    def set_section(self, section: str) -> None:
        self.section = section

    def to_dict(self):
        return {
            'name': self.name,
            'email': self.email,
            'course': self.course,
            'section': self.section,
            'reflection_data': {
                ref_num: {
                    'reflection': data['reflection'].to_dict() if data['reflection'] else None,
                    'grades': data['grades']
                }
                for ref_num, data in self.reflection_data.items()
            }
        }
