"""
Emotions analysis builder for analyzing and visualizing student emotions.
"""
from typing import Dict, List, Tuple, Optional
import pandas as pd
import plotly.express as px
from collections import Counter
from pathlib import Path
import os

from .base_builder import BaseBuilder
from ..services.statistical_analysis.correlation_analyzer import CorrelationAnalyzer

class EmotionsAnalysisBuilder(BaseBuilder):
    """Builder for analyzing and visualizing student emotions."""

    def __init__(self):
        """Initialize the emotions analysis builder."""
        super().__init__()
        self.correlation_analyzer = CorrelationAnalyzer()

    def build_emotions_analysis(
        self,
        course_data: pd.DataFrame,
        reflection_files: List[Tuple[int, str]]
    ) -> str:
        """
        Build emotions analysis HTML.

        Args:
            course_data: DataFrame containing student data
            reflection_files: List of (reflection_number, file_path) tuples

        Returns:
            str: HTML containing emotions analysis
        """
        try:
            # Extract emotions data
            emotions_data = self._extract_emotions_data(course_data, reflection_files)

            # Create emotions bar chart
            bar_chart_html = self._create_emotions_bar_chart(emotions_data)

            # Create emotions table
            table_html = self._create_emotions_table(emotions_data)

            # Create emotions trend analysis
            trend_html = self._create_emotions_trend_analysis(emotions_data)

            # Combine all components
            return self.render_template(
                'components/emotions_analysis.html',
                bar_chart_html=bar_chart_html,
                table_html=table_html,
                trend_html=trend_html
            )

        except Exception as e:
            print(f"Error building emotions analysis: {e}")
            return f"<div>Error building emotions analysis: {str(e)}</div>"

    def _extract_emotions_data(
        self,
        course_data: pd.DataFrame,
        reflection_files: List[Tuple[int, str]]
    ) -> Dict:
        """
        Extract emotions data from course data and reflection files.

        Args:
            course_data: DataFrame containing student data
            reflection_files: List of (reflection_number, file_path) tuples

        Returns:
            Dict containing processed emotions data
        """
        emotions_data = {
            'emotions_by_reflection': {},
            'emotion_counts': Counter(),
            'emotion_trends': {},
            'student_emotions': {}
        }

        for ref_num, file_path in reflection_files:
            if not os.path.exists(file_path):
                continue

            df = pd.read_csv(file_path)

            # Find emotion column
            emotion_col = None
            for col in df.columns:
                if isinstance(col, str) and col.strip().lower().startswith("how do you feel about the course so far?"):
                    emotion_col = col
                    break

            if not emotion_col:
                continue

            # Process emotions for this reflection
            reflection_emotions = []
            for _, row in df.iterrows():
                emotions = str(row.get(emotion_col, '')).split(',')
                emotions = [e.strip() for e in emotions if e.strip()]
                reflection_emotions.extend(emotions)
                emotions_data['emotion_counts'].update(emotions)

            emotions_data['emotions_by_reflection'][ref_num] = reflection_emotions

            # Track emotions by student
            for _, row in df.iterrows():
                student_id = row.get('ID', '')
                if pd.isna(student_id):
                    continue

                emotions = str(row.get(emotion_col, '')).split(',')
                emotions = [e.strip() for e in emotions if e.strip()]

                if student_id not in emotions_data['student_emotions']:
                    emotions_data['student_emotions'][student_id] = {}

                emotions_data['student_emotions'][student_id][ref_num] = emotions

        return emotions_data

    def _create_emotions_bar_chart(self, emotions_data: Dict) -> str:
        """
        Create bar chart of emotion frequencies.

        Args:
            emotions_data: Dictionary containing processed emotions data

        Returns:
            str: HTML containing the bar chart
        """
        # Get top emotions
        top_emotions = emotions_data['emotion_counts'].most_common(10)

        # Create DataFrame for plotting
        df = pd.DataFrame(top_emotions, columns=['Emotion', 'Count'])

        # Create bar chart
        fig = px.bar(
            df,
            x='Emotion',
            y='Count',
            title='Top 10 Emotions Expressed by Students',
            labels={'Count': 'Number of Students', 'Emotion': 'Emotion'},
            color='Count',
            color_continuous_scale='Viridis'
        )

        fig.update_layout(
            xaxis_tickangle=-45,
            plot_bgcolor='#fff',
            margin=dict(t=60, b=100)
        )

        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def _create_emotions_table(self, emotions_data: Dict) -> str:
        """
        Create table of emotion frequencies.

        Args:
            emotions_data: Dictionary containing processed emotions data

        Returns:
            str: HTML containing the table
        """
        # Create DataFrame for all emotions
        df = pd.DataFrame(
            emotions_data['emotion_counts'].most_common(),
            columns=['Emotion', 'Count']
        )

        # Add percentage column
        total = df['Count'].sum()
        df['Percentage'] = (df['Count'] / total * 100).round(1)

        # Create HTML table
        return df.to_html(
            index=False,
            float_format='%.1f',
            classes='emotions-table',
            border=0
        )

    def _create_emotions_trend_analysis(self, emotions_data: Dict) -> str:
        """
        Create trend analysis of emotions across reflections.

        Args:
            emotions_data: Dictionary containing processed emotions data

        Returns:
            str: HTML containing the trend analysis
        """
        # Create DataFrame for trends
        trend_data = []
        for ref_num, emotions in emotions_data['emotions_by_reflection'].items():
            counter = Counter(emotions)
            for emotion, count in counter.items():
                trend_data.append({
                    'Reflection': ref_num,
                    'Emotion': emotion,
                    'Count': count
                })

        df = pd.DataFrame(trend_data)

        # Create line plot
        fig = px.line(
            df,
            x='Reflection',
            y='Count',
            color='Emotion',
            title='Emotion Trends Across Reflections',
            labels={'Count': 'Number of Students', 'Reflection': 'Reflection Number'},
            markers=True
        )

        fig.update_layout(
            plot_bgcolor='#fff',
            margin=dict(t=60, b=40)
        )

        return fig.to_html(full_html=False, include_plotlyjs='cdn')
