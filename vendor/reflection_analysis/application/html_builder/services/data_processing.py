"""
Data processing service for handling common data extraction and processing tasks.
"""
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
from collections import Counter
import os
from pathlib import Path

class DataProcessingService:
    """Service for handling data extraction and processing."""

    @staticmethod
    def extract_reflection_data(
        reflection_files: List[Tuple[int, str]],
        column_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Extract data from reflection files using provided column mappings.

        Args:
            reflection_files: List of (reflection_number, file_path) tuples
            column_mapping: Dictionary mapping column names to their expected values

        Returns:
            Dict containing processed reflection data
        """
        reflection_data = {
            'data_by_reflection': {},
            'student_data': {},
            'aggregate_stats': {}
        }

        for ref_num, file_path in reflection_files:
            if not os.path.exists(file_path):
                continue

            df = pd.read_csv(file_path)

            # Process each mapped column
            for col_name, expected_value in column_mapping.items():
                # Find matching column
                matching_col = None
                for col in df.columns:
                    if isinstance(col, str) and col.strip().lower().startswith(expected_value.lower()):
                        matching_col = col
                        break

                if not matching_col:
                    continue

                # Process data for this column
                reflection_values = []
                for _, row in df.iterrows():
                    student_id = row.get('ID', '')
                    if pd.isna(student_id):
                        continue

                    value = row.get(matching_col, None)
                    if pd.notna(value):
                        reflection_values.append(value)

                        # Track student-specific data
                        if student_id not in reflection_data['student_data']:
                            reflection_data['student_data'][student_id] = {}

                        if col_name not in reflection_data['student_data'][student_id]:
                            reflection_data['student_data'][student_id][col_name] = {}

                        reflection_data['student_data'][student_id][col_name][ref_num] = value

                # Store reflection data
                if reflection_values:
                    if ref_num not in reflection_data['data_by_reflection']:
                        reflection_data['data_by_reflection'][ref_num] = {}

                    reflection_data['data_by_reflection'][ref_num][col_name] = reflection_values

                    # Calculate aggregate statistics
                    if col_name not in reflection_data['aggregate_stats']:
                        reflection_data['aggregate_stats'][col_name] = {}

                    if ref_num not in reflection_data['aggregate_stats'][col_name]:
                        reflection_data['aggregate_stats'][col_name][ref_num] = {}

                    # Calculate statistics based on data type
                    if isinstance(reflection_values[0], (int, float)):
                        reflection_data['aggregate_stats'][col_name][ref_num] = {
                            'mean': pd.Series(reflection_values).mean(),
                            'median': pd.Series(reflection_values).median(),
                            'std': pd.Series(reflection_values).std(),
                            'min': min(reflection_values),
                            'max': max(reflection_values)
                        }
                    else:
                        counter = Counter(reflection_values)
                        reflection_data['aggregate_stats'][col_name][ref_num] = {
                            'counts': dict(counter),
                            'total': len(reflection_values)
                        }

        return reflection_data

    @staticmethod
    def extract_module_data(
        course_data: pd.DataFrame,
        module_columns: List[str]
    ) -> Dict[str, Any]:
        """
        Extract module completion data from course data.

        Args:
            course_data: DataFrame containing course data
            module_columns: List of module column names

        Returns:
            Dict containing processed module data
        """
        module_data = {
            'completion_by_module': {},
            'student_completion': {},
            'module_stats': {}
        }

        for module_col in module_columns:
            if module_col not in course_data.columns:
                continue

            # Extract completion data
            completion_data = course_data[module_col].fillna(0)
            module_data['completion_by_module'][module_col] = completion_data.tolist()

            # Calculate module statistics
            module_data['module_stats'][module_col] = {
                'completion_rate': (completion_data > 0).mean(),
                'total_completed': (completion_data > 0).sum(),
                'total_students': len(completion_data)
            }

            # Track student-specific completion
            for idx, row in course_data.iterrows():
                student_id = row.get('ID', '')
                if pd.isna(student_id):
                    continue

                if student_id not in module_data['student_completion']:
                    module_data['student_completion'][student_id] = {}

                module_data['student_completion'][student_id][module_col] = row[module_col]

        return module_data

    @staticmethod
    def extract_topic_data(
        course_data: pd.DataFrame,
        topic_columns: List[str]
    ) -> Dict[str, Any]:
        """
        Extract topic data from course data.

        Args:
            course_data: DataFrame containing course data
            topic_columns: List of topic column names

        Returns:
            Dict containing processed topic data
        """
        topic_data = {
            'topics_by_student': {},
            'topic_frequencies': Counter(),
            'topic_stats': {}
        }

        for topic_col in topic_columns:
            if topic_col not in course_data.columns:
                continue

            # Extract topic data
            topic_values = course_data[topic_col].fillna('')
            topic_data['topic_frequencies'].update(topic_values)

            # Track student-specific topics
            for idx, row in course_data.iterrows():
                student_id = row.get('ID', '')
                if pd.isna(student_id):
                    continue

                if student_id not in topic_data['topics_by_student']:
                    topic_data['topics_by_student'][student_id] = {}

                topic_data['topics_by_student'][student_id][topic_col] = row[topic_col]

            # Calculate topic statistics
            topic_data['topic_stats'][topic_col] = {
                'total_mentions': len(topic_values[topic_values != '']),
                'unique_topics': len(set(topic_values[topic_values != ''])),
                'most_common': dict(Counter(topic_values[topic_values != '']).most_common(5))
            }

        return topic_data
