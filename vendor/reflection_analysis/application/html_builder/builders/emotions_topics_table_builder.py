class EmotionsTopicsTableBuilder:
    """Helper class to encapsulate the extremely large `_build_emotions_topics_table` logic.

    NOTE: For minimal-change safety, we *delegate* to the legacy implementation that still
    lives in `HTMLBuilder`.  This immediately gives us the indirection we need – the heavy
    method is now *logically* owned by this helper and can be gradually slimmed down or
    replaced without touching call-sites in `HTMLBuilder`.
    """

    def __init__(self, parent_builder):
        # We keep a reference to the parent HTMLBuilder instance so we can call the
        # existing private implementation and access any of its utility methods.
        self._parent = parent_builder

    # Keep the signature identical so existing callers don't need to change.
    def build(self, reflection_files, course, anonymized=False):
        # Delegate to the parent.  In a later refactor, the full implementation can be
        # moved here and the call below removed.
        return self._parent._build_emotions_topics_table(reflection_files, course, anonymized=anonymized)

    def build_student_lookup(self, course):
        """Return mapping that lets us resolve either full email or 4-digit SIS id to the Student object."""
        lookup = {}
        for student in course.students.values():
            lookup[student.email] = student
            prefix = student.email.split('@')[0]
            if prefix.isdigit() and len(prefix) == 4:
                lookup[prefix] = student
        return lookup
