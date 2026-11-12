"""
Grade analysis builder for analyzing and visualizing student grades.
"""
from typing import Dict, List, Tuple, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import os

from .base_builder import BaseBuilder
from ..services.statistical_analysis.correlation_analyzer import CorrelationAnalyzer

class GradeAnalysisBuilder(BaseBuilder):
    """Builder for analyzing and visualizing student grades."""

    def __init__(self):
        """Initialize the grade analysis builder."""
        super().__init__()
        self.correlation_analyzer = CorrelationAnalyzer()

    def build_grade_analysis(
        self,
        course_data: pd.DataFrame,
        reflection_files: List[Tuple[int, str]]
    ) -> str:
        """
        Build grade analysis HTML.

        Args:
            course_data: DataFrame containing student data
            reflection_files: List of (reflection_number, file_path) tuples

        Returns:
            str: HTML containing grade analysis
        """
        try:
            # Extract grade data
            grade_data = self._extract_grade_data(course_data, reflection_files)

            # Create grade distribution chart
            distribution_html = self._create_grade_distribution(grade_data)

            # Create grade trends chart
            trends_html = self._create_grade_trends(grade_data)

            # Create grade summary table
            summary_html = self._create_grade_summary(grade_data)

            # Combine all components
            return self.render_template(
                'components/grade_analysis.html',
                distribution_html=distribution_html,
                trends_html=trends_html,
                summary_html=summary_html
            )

        except Exception as e:
            print(f"Error building grade analysis: {e}")
            return f"<div>Error building grade analysis: {str(e)}</div>"

    def _extract_grade_data(
        self,
        course_data: pd.DataFrame,
        reflection_files: List[Tuple[int, str]]
    ) -> Dict:
        """
        Extract grade data from course data and reflection files.

        Args:
            course_data: DataFrame containing student data
            reflection_files: List of (reflection_number, file_path) tuples

        Returns:
            Dict containing processed grade data
        """
        grade_data = {
            'grades_by_reflection': {},
            'grade_distributions': {},
            'grade_trends': {},
            'student_grades': {}
        }

        for ref_num, file_path in reflection_files:
            if not os.path.exists(file_path):
                continue

            df = pd.read_csv(file_path)

            # Extract grades for this reflection
            reflection_grades = []
            for _, row in df.iterrows():
                student_id = row.get('ID', '')
                if pd.isna(student_id):
                    continue

                grade = row.get('Current Score', None)
                if pd.notna(grade):
                    try:
                        grade = float(grade)
                        reflection_grades.append(grade)

                        if student_id not in grade_data['student_grades']:
                            grade_data['student_grades'][student_id] = {}

                        grade_data['student_grades'][student_id][ref_num] = grade
                    except (ValueError, TypeError):
                        continue

            if reflection_grades:
                grade_data['grades_by_reflection'][ref_num] = reflection_grades

                # Calculate distribution
                grade_data['grade_distributions'][ref_num] = {
                    'mean': pd.Series(reflection_grades).mean(),
                    'median': pd.Series(reflection_grades).median(),
                    'std': pd.Series(reflection_grades).std(),
                    'min': min(reflection_grades),
                    'max': max(reflection_grades)
                }

        return grade_data

    def _create_grade_distribution(self, grade_data: Dict) -> str:
        """
        Create grade distribution visualization.

        Args:
            grade_data: Dictionary containing processed grade data

        Returns:
            str: HTML containing the grade distribution
        """
        # Create histogram for each reflection
        fig = go.Figure()

        for ref_num, grades in grade_data['grades_by_reflection'].items():
            fig.add_trace(go.Histogram(
                x=grades,
                name=f'Reflection {ref_num}',
                opacity=0.7,
                nbinsx=20
            ))

        fig.update_layout(
            title='Grade Distributions Across Reflections',
            xaxis_title='Grade',
            yaxis_title='Number of Students',
            barmode='overlay',
            plot_bgcolor='#fff',
            margin=dict(t=60, b=40)
        )

        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def _create_grade_trends(self, grade_data: Dict) -> str:
        """
        Create grade trends visualization.

        Args:
            grade_data: Dictionary containing processed grade data

        Returns:
            str: HTML containing the grade trends
        """
        # Create box plot for each reflection
        fig = go.Figure()

        for ref_num, grades in grade_data['grades_by_reflection'].items():
            fig.add_trace(go.Box(
                y=grades,
                name=f'Reflection {ref_num}',
                boxpoints='all',
                jitter=0.3,
                pointpos=-1.8
            ))

        fig.update_layout(
            title='Grade Trends Across Reflections',
            yaxis_title='Grade',
            plot_bgcolor='#fff',
            margin=dict(t=60, b=40)
        )

        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def _create_grade_summary(self, grade_data: Dict) -> str:
        """
        Create grade summary table.

        Args:
            grade_data: Dictionary containing processed grade data

        Returns:
            str: HTML containing the grade summary
        """
        # Create summary DataFrame
        summary_data = []
        for ref_num, distribution in grade_data['grade_distributions'].items():
            summary_data.append({
                'Reflection': ref_num,
                'Mean': distribution['mean'],
                'Median': distribution['median'],
                'Std Dev': distribution['std'],
                'Min': distribution['min'],
                'Max': distribution['max']
            })

        df = pd.DataFrame(summary_data)

        # Create HTML table
        return df.to_html(
            index=False,
            float_format='%.1f',
            classes='grade-summary-table',
            border=0
        )
