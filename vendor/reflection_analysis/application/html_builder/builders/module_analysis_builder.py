"""
Module analysis builder for analyzing and visualizing module completion patterns.
"""
from typing import Dict, List, Tuple, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import os

from .base_builder import BaseBuilder
from ..services.data_processing import DataProcessingService
from ..services.statistical_analysis.correlation_analyzer import CorrelationAnalyzer

class ModuleAnalysisBuilder(BaseBuilder):
    """Builder for analyzing and visualizing module completion patterns."""

    def __init__(self):
        """Initialize the module analysis builder."""
        super().__init__()
        self.data_processor = DataProcessingService()
        self.correlation_analyzer = CorrelationAnalyzer()

    def build_module_analysis(
        self,
        course_data: pd.DataFrame,
        module_columns: List[str],
        reflection_files: List[Tuple[int, str]]
    ) -> str:
        """
        Build module analysis HTML.

        Args:
            course_data: DataFrame containing student data
            module_columns: List of module column names
            reflection_files: List of (reflection_number, file_path) tuples

        Returns:
            str: HTML containing module analysis
        """
        try:
            # Extract module data
            module_data = self.data_processor.extract_module_data(course_data, module_columns)

            # Create completion rate visualization
            completion_html = self._create_completion_rates(module_data)

            # Create grade correlation analysis
            grade_correlation_html = self._create_grade_correlations(course_data, module_data)

            # Create module progression analysis
            progression_html = self._create_module_progression(module_data)

            # Create module summary table
            summary_html = self._create_module_summary(module_data)

            # Combine all components
            return self.render_template(
                'components/module_analysis.html',
                completion_html=completion_html,
                grade_correlation_html=grade_correlation_html,
                progression_html=progression_html,
                summary_html=summary_html
            )

        except Exception as e:
            print(f"Error building module analysis: {e}")
            return f"<div>Error building module analysis: {str(e)}</div>"

    def _create_completion_rates(self, module_data: Dict) -> str:
        """
        Create visualization of module completion rates.

        Args:
            module_data: Dictionary containing processed module data

        Returns:
            str: HTML containing the completion rates visualization
        """
        # Prepare data for plotting
        completion_data = []
        for module, stats in module_data['module_stats'].items():
            completion_data.append({
                'Module': module,
                'Completion Rate': stats['completion_rate'] * 100,
                'Completed': stats['total_completed'],
                'Total': stats['total_students']
            })

        df = pd.DataFrame(completion_data)

        # Create bar chart
        fig = px.bar(
            df,
            x='Module',
            y='Completion Rate',
            title='Module Completion Rates',
            labels={'Completion Rate': 'Completion Rate (%)', 'Module': 'Module'},
            color='Completion Rate',
            color_continuous_scale='Viridis',
            text='Completed'
        )

        fig.update_layout(
            xaxis_tickangle=-45,
            plot_bgcolor='#fff',
            margin=dict(t=60, b=100)
        )

        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def _create_grade_correlations(
        self,
        course_data: pd.DataFrame,
        module_data: Dict
    ) -> str:
        """
        Create visualization of grade correlations with module completion.

        Args:
            course_data: DataFrame containing student data
            module_data: Dictionary containing processed module data

        Returns:
            str: HTML containing the grade correlations visualization
        """
        # Create box plots for each module
        fig = go.Figure()

        for module in module_data['completion_by_module'].keys():
            # Get grades for students who completed/didn't complete the module
            completed_grades = course_data[
                course_data[module] > 0
            ]['Current Score'].dropna()

            not_completed_grades = course_data[
                course_data[module] == 0
            ]['Current Score'].dropna()

            if not completed_grades.empty:
                fig.add_trace(go.Box(
                    y=completed_grades,
                    name=f'{module} (Completed)',
                    boxpoints='all',
                    jitter=0.3,
                    pointpos=-1.8
                ))

            if not not_completed_grades.empty:
                fig.add_trace(go.Box(
                    y=not_completed_grades,
                    name=f'{module} (Not Completed)',
                    boxpoints='all',
                    jitter=0.3,
                    pointpos=-1.8
                ))

        fig.update_layout(
            title='Grade Distributions by Module Completion',
            yaxis_title='Grade',
            plot_bgcolor='#fff',
            margin=dict(t=60, b=40)
        )

        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def _create_module_progression(self, module_data: Dict) -> str:
        """
        Create visualization of module progression patterns.

        Args:
            module_data: Dictionary containing processed module data

        Returns:
            str: HTML containing the module progression visualization
        """
        # Create heatmap of module completion patterns
        modules = list(module_data['completion_by_module'].keys())
        completion_matrix = pd.DataFrame(0, index=modules, columns=modules)

        for student_data in module_data['student_completion'].values():
            completed_modules = [
                module for module, value in student_data.items()
                if value > 0
            ]

            for i, module1 in enumerate(completed_modules):
                for module2 in completed_modules[i+1:]:
                    completion_matrix.loc[module1, module2] += 1
                    completion_matrix.loc[module2, module1] += 1

        fig = go.Figure(data=go.Heatmap(
            z=completion_matrix.values,
            x=completion_matrix.columns,
            y=completion_matrix.index,
            colorscale='Viridis'
        ))

        fig.update_layout(
            title='Module Completion Patterns',
            xaxis_title='Module',
            yaxis_title='Module',
            plot_bgcolor='#fff',
            margin=dict(t=60, b=40)
        )

        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def _create_module_summary(self, module_data: Dict) -> str:
        """
        Create summary table of module statistics.

        Args:
            module_data: Dictionary containing processed module data

        Returns:
            str: HTML containing the module summary table
        """
        # Create summary DataFrame
        summary_data = []
        for module, stats in module_data['module_stats'].items():
            summary_data.append({
                'Module': module,
                'Completion Rate': f"{stats['completion_rate']*100:.1f}%",
                'Completed': stats['total_completed'],
                'Total Students': stats['total_students']
            })

        df = pd.DataFrame(summary_data)

        # Create HTML table
        return df.to_html(
            index=False,
            classes='module-summary-table',
            border=0
        )
