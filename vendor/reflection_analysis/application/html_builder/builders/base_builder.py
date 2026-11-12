"""
Base builder class that provides common functionality for all HTML builders.
"""
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader

class BaseBuilder:
    """Base class for all HTML builders providing common functionality."""

    def __init__(self):
        """Initialize the base builder with template environment."""
        template_dir = Path(__file__).parent.parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def render_template(
        self,
        template_name: str,
        **kwargs: Any
    ) -> str:
        """
        Render a template with the given context.

        Args:
            template_name: Name of the template file
            **kwargs: Context variables for the template

        Returns:
            str: Rendered HTML
        """
        template = self.env.get_template(template_name)
        return template.render(**kwargs)

    def get_css(self) -> str:
        """
        Get the CSS styles for the builder.

        Returns:
            str: CSS styles
        """
        try:
            css_path = Path(__file__).parent.parent / "templates" / "styles.css"
            with open(css_path) as f:
                return f.read()
        except Exception as e:
            print(f"Error loading CSS: {e}")
            return ""

    def format_number(self, number: float, precision: int = 2) -> str:
        """
        Format a number with the specified precision.

        Args:
            number: Number to format
            precision: Number of decimal places

        Returns:
            str: Formatted number
        """
        return f"{number:.{precision}f}"

    def get_grade_color(self, grade: float) -> str:
        """
        Get color indicator for a grade.

        Args:
            grade: Grade value

        Returns:
            str: Color name
        """
        if grade >= 90: return "green"
        if grade >= 80: return "blue"
        if grade >= 70: return "orange"
        return "red"

    def highlight_significant(self, value: float, threshold: float = 0.05) -> str:
        """
        Get CSS style for highlighting significant values.

        Args:
            value: Value to check
            threshold: Significance threshold

        Returns:
            str: CSS style string
        """
        try:
            if float(value) < threshold:
                return 'background-color:#d4edda;font-weight:bold;'
        except:
            pass
        return ''
