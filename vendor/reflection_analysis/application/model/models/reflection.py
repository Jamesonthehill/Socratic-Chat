from typing import Dict, Any, Optional
import pandas as pd

class Reflection:
    def __init__(self, row: Dict[str, Any]):
        """
        Initialize a Reflection object from a row of data

        Args:
            row: A pandas Series or dictionary containing reflection data
        """
        # Preserve the original ID format (email, 2-digit, 4-digit number)
        original_id = row.get('ID', '')
        self._id = str(original_id).strip() if original_id else ''

        # Debug: Track ID processing
        print(f"DEBUG REFLECTION: Creating reflection with ID: '{self._id}' (original: '{original_id}', type: {type(original_id)})")

        self.questions: list = []
        self.reflections: list = []
        self.grades: Dict[str, Any] = {}  # Store grades specific to this reflection
        self.timestamp = row.get('StartDate', '')  # Add timestamp if available
        self.reflection_number = row.get('reflection_number')  # Use the reflection number from the row data

        # Process each column
        for col, value in row.items():
            if col in ['ID', 'StartDate', 'reflection_number'] or 'section' in col.lower():  # Skip these fields
                continue

            # Check if it's a grade column
            if 'grade' in col.lower() or 'score' in col.lower():
                if value and str(value).strip():
                    self.grades[col] = value
            # Otherwise treat as Q&A
            elif value and str(value).strip():
                self.questions.append(col)
                self.reflections.append(str(value).strip())

    def __str__(self):
        """String representation of the reflection (without ID)"""
        output = []
        for i, (q, r) in enumerate(zip(self.questions, self.reflections), 1):
            output.append(f"\nQ{i}: {q}")
            output.append(f"A{i}: {r}")
        return "\n".join(output)

    def text_only(self):
        """String representation of the reflection (without ID)"""
        return self.reflections[0] if self.reflections else ""

    def console_output(self):
        """String representation for console output (includes ID)"""
        output = [f"ID: {self._id}"]
        for i, (q, r) in enumerate(zip(self.questions, self.reflections), 1):
            output.append(f"\nQ{i}: {q}")
            output.append(f"A{i}: {r}")
        return "\n".join(output)

    def __len__(self):
        """Return the number of reflections"""
        return len(self.reflections)

    @property
    def id(self):
        """Property to access the ID when needed programmatically"""
        return self._id

    @property
    def number(self):
        """Get the reflection number"""
        return self.reflection_number

    def set_reflection_number(self, number):
        """Set the reflection number"""
        self.reflection_number = number

    def add_grade(self, assignment, score):
        """Add or update a grade for this reflection"""
        self.grades[assignment] = score

    def get_grades(self):
        """Get all grades for this reflection"""
        return self.grades

    @classmethod
    def createRefs(cls, df):
        # Add reflection numbers when creating reflections
        refs = []
        for reflection_num, (_, row) in enumerate(df.iterrows(), 1):
            reflection = cls(row)
            reflection.set_reflection_number(reflection_num)
            refs.append(reflection)
        return refs

    def to_dict(self):
        data = self.__dict__.copy()
        if 'grades' in data:
            data['grades'] = dict(data['grades'])
        return data

    @property
    def section(self):
        # Return the value of the first column containing 'section' in its name
        for attr in self.__dict__:
            if 'section' in attr.lower():
                return getattr(self, attr)
        return None
