from pathlib import Path
from typing import Dict
from jinja2 import Template, Environment, FileSystemLoader

class TemplateManager:
    def __init__(self):
        template_dir = Path(__file__).parent
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def load_template(self, template_name: str) -> Template:
        """Load a template by name"""
        return self.env.get_template(f"{template_name}.html")

    def render_student_profile(self, template: Template, context: dict) -> str:
        """Render student profile template"""
        return template.render(**context)

    def render_topic_analysis(self, template: Template, context: dict) -> str:
        """Render topic analysis template"""
        try:
            return template.render(**context)
        except Exception as e:
            print(f"Error rendering topic analysis: {e}")
            return f"""
                <div class="topic-analysis">
                    <h2>Topic Analysis - Error</h2>
                    <div class="error-message">
                        Error rendering topic analysis: {str(e)}
                    </div>
                </div>
            """
