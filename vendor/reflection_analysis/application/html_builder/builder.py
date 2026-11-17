from pathlib import Path
from typing import List, Dict, Tuple
from jinja2 import Environment, FileSystemLoader
from application.model.models.course import Course
from application.model.models.student import Student
from application.html_builder.components.student_profile import StudentProfileBuilder
from application.html_builder.components.topic_analysis import TopicAnalysisBuilder
import os
import pandas as pd
import plotly.express as px
import plotly.colors
import random
from collections import Counter
import plotly.graph_objects as go
import urllib.parse
from urllib.parse import parse_qs, urlparse
import json
import re
# scipy import removed (research mode functionality)
# Chi-square helper removed (research mode functionality)
# Grade module correlation helper removed (research mode functionality)
from application.html_builder.builders.emotions_analysis_builder import EmotionsAnalysisBuilder
# SSM before/after builder removed (research mode functionality)
import collections
import csv
from application.html_builder.builders.emotions_topics_table_builder import EmotionsTopicsTableBuilder

class HTMLBuilder:
    def __init__(self, topic_data_path=None):
        self.topic_data_path = topic_data_path
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.student_profile_builder = StudentProfileBuilder()
        self.emotions_analysis_builder = EmotionsAnalysisBuilder()
        # SSM before/after builder removed (research mode functionality)
        # NEW helper class for the very large emotions/topics table logic
        self.emotions_topics_table_builder = EmotionsTopicsTableBuilder(self)

    def get_student_indicators(self, student, course):
        """Get status indicators for a student"""
        # Find the most recent reflection number
        reflection_numbers = sorted(student.reflection_data.keys(), reverse=True)
        if not reflection_numbers:
            return {
                'grade_color': 'red',
                'current_grade': None,
                'has_latest_reflection': False,
                'grade_trend': 'neutral',
                'urgency': 'none',
                'resolution': 'no_challenge'
            }

        latest_ref = reflection_numbers[0]
        previous_ref = reflection_numbers[1] if len(reflection_numbers) > 1 else None

        # Get grades
        latest_grade = 0.0
        previous_grade = 0.0
        if latest_ref in student.reflection_data and student.reflection_data[latest_ref]['grades']:
            latest_grade = self.student_profile_builder.grade_service.get_current_grade(
                student.reflection_data[latest_ref]['grades']
            )
        if previous_ref and previous_ref in student.reflection_data and student.reflection_data[previous_ref]['grades']:
            previous_grade = self.student_profile_builder.grade_service.get_current_grade(
                student.reflection_data[previous_ref]['grades']
            )

        grade_change = latest_grade - previous_grade if previous_ref else 0

        # Get student email prefix
        student_prefix = student.email.split('@')[0].lower()

        # Get urgency and resolution from latest reflection's exploded CSV
        urgency = "none"
        resolution = "no_challenge"
        negative_emotion = False
        positive_emotion = False

        try:
            # Load exploded CSV for latest reflection
            csv_path = os.path.join(
                "application", "model", "reflections",
                course.course_name,
                f"ref{latest_ref}",
                "results",
                f"{course.course_name}_ref{latest_ref}_exploded.csv"
            )

            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)

                # Find matching student row by email prefix
                student_row = df[df['ID'].str.lower().str.startswith(student_prefix)]
                if not student_row.empty:
                    # Get resolution and urgency
                    if 'resolution_primary_labels' in student_row.columns:
                        resolution_value = student_row['resolution_primary_labels'].iloc[0]
                        if pd.notna(resolution_value):
                            resolution = str(resolution_value).lower()

                    if 'urgency' in student_row.columns:
                        urgency_value = student_row['urgency'].iloc[0]
                        if pd.notna(urgency_value):
                            urgency = str(urgency_value).lower()
            # Load reflection CSV to detect negative emotion selection
            try:
                ref_csv_path = os.path.join(
                    "application", "model", "reflections",
                    course.course_name,
                    f"ref{latest_ref}",
                    f"{course.course_name}_ref{latest_ref}.csv"
                )
                if os.path.exists(ref_csv_path):
                    rdf = pd.read_csv(ref_csv_path)
                    # Identify emotion column (prefix match, case-insensitive)
                    emotion_col = None
                    for col in rdf.columns:
                        if isinstance(col, str) and col.strip().lower().startswith("how do you feel about the course so far?"):
                            emotion_col = col
                            break
                    if emotion_col is not None and 'ID' in rdf.columns:
                        ridx = rdf['ID'].astype(str).str.strip().str.lower() == student.email.lower()
                        if not ridx.any():
                            # Fallback: match by email prefix
                            ridx = rdf['ID'].astype(str).str.strip().str.lower().str.startswith(student_prefix)
                        if ridx.any():
                            emo_val = str(rdf.loc[ridx, emotion_col].iloc[0])
                            emo_low = emo_val.lower()
                            neg_keywords = [
                                'anxious','frustrated','confused','sad','angry','upset','stressed','overwhelmed','worried'
                            ]
                            neg_emojis = ['😰','😟','😢','😭','😞','😕','😫','😡','🙁','☹️']
                            negative_emotion = any(k in emo_low for k in neg_keywords) or any(e in emo_val for e in neg_emojis)
                            # Detect positive emotions as a counter-signal
                            pos_keywords = [
                                'excited','satisfied','happy','confident','optimistic','proud','motivated','calm','relieved'
                            ]
                            pos_emojis = ['😊','🙂','😄','😁','😃','😍','😌','🤩']
                            positive_emotion = any(k in emo_low for k in pos_keywords) or any(e in emo_val for e in pos_emojis)
            except Exception as _:
                pass
        except Exception as e:
            print(f"Error reading exploded CSV for {student.email}: {e}")

        return {
            'grade_color': self.get_grade_color(latest_grade),
            'current_grade': latest_grade if student.reflection_data[latest_ref]['grades'] else None,
            'has_latest_reflection': bool(latest_reflection := student.reflection_data.get(latest_ref))
                               and bool(latest_reflection.get('reflection')),
            'grade_trend': "up" if grade_change > 0 else "down" if grade_change < 0 else "neutral",
            'urgency': urgency,
            'resolution': resolution,
            'negative_emotion': negative_emotion,
            'positive_emotion': positive_emotion
        }

    def get_grade_color(self, grade):
        """Get color indicator for grade"""
        if grade >= 90: return "green"
        if grade >= 80: return "blue"
        if grade >= 70: return "orange"
        return "red"

    def build_student_profiles(self, course: Course, mode: str = "instructor", anonymized: bool = False) -> str:
        """
        Build HTML for all student profiles in a course

        Args:
            course: Course object containing student data
            mode: Report mode - always "instructor" (simplified)
            anonymized: Whether to anonymize student information (names, emails, sections)
        """
        # Set anonymized attribute for downstream logic
        course.anonymized = anonymized

        # Find the latest reflection number by checking directories
        reflection_dirs = [d for d in os.listdir(os.path.join("application", "model", "reflections", course.course_name))
                          if d.startswith('ref')]
        ref_numbers = [int(d.replace('ref', '')) for d in reflection_dirs]
        latest_ref = max(ref_numbers) if ref_numbers else 1

        # Add check for results directory
        results_path = os.path.join(
            "application", "model", "reflections",
            course.course_name,
            f"ref{latest_ref}",
            "results"
        )

        if not os.path.exists(results_path):
            print(f"Warning: No analysis results found at {results_path}")
            print("Please run topic analysis first through the Streamlit interface")

        template = self.env.get_template("base.html")
        topic_builder = TopicAnalysisBuilder(self.topic_data_path)

        # Debug information
        student_count = len(course.students)
        print(f"Building profiles for {student_count} students")

        # Get CSS
        try:
            with open(Path(__file__).parent / "templates" / "styles.css") as f:
                css = f.read()
                print("CSS loaded successfully")
        except Exception as e:
            print(f"Error loading CSS: {e}")
            css = ""  # Fallback to empty CSS

        # Debug student data
        students = list(course.students.values())
        print(f"First student name: {students[0].name if students else 'No students'}")
        print(f"First student email: {students[0].email if students else 'No students'}")

        # --- Aggregates Tab: Emotions Bar Chart and Table ---
        ai_email_data = {}
        aggregates_html = ""
        emotions_analysis_html = ""
        # Ensure all template variables are initialized to avoid UnboundLocalError
        topic_quiz_chi_square_html = ""
        statistical_comparison_html = ""
        support_quiz_completion_table_html = ""
        quiz_completion_rate_chart_html = ""
        try:
            # Find all available reflection CSVs for the course (look in ref* subdirectories)
            reflection_dir = os.path.join("application", "model", "reflections", course.course_name)
            reflection_subdirs = [d for d in os.listdir(reflection_dir) if d.startswith('ref') and os.path.isdir(os.path.join(reflection_dir, d))]
            reflection_files = []
            ref_nums = []
            for subdir in reflection_subdirs:
                try:
                    ref_num = int(subdir.replace('ref', ''))
                    candidate_csv = os.path.join(reflection_dir, subdir, f"{course.course_name}_ref{ref_num}.csv")
                    if os.path.exists(candidate_csv):
                        reflection_files.append((ref_num, candidate_csv))
                        ref_nums.append(ref_num)
                except Exception:
                    continue
            ref_nums = sorted(ref_nums)
            reflection_files = sorted(reflection_files, key=lambda x: x[0])

            # Calculate and set the matching students count
            matching_students_count = self.calculate_matching_students_count(course, reflection_files)
            course.set_matching_students_count(matching_students_count)

            # FIX: Ensure total students count is set correctly from the most recent reflection's grade file
            self._ensure_correct_total_students_count(course, reflection_files)

            # NEW: Use EmotionsAnalysisBuilder to generate emotions analysis HTML
            # Build a DataFrame for course_data (merge all reflections)
            course_data = pd.concat([pd.read_csv(f) for _, f in reflection_files if os.path.exists(f)], ignore_index=True) if reflection_files else pd.DataFrame()
            emotions_analysis_html = self.emotions_analysis_builder.build_emotions_analysis(course_data, reflection_files)
            # Chi-square explanation removed (research mode functionality)

            # Default to latest reflection
            selected_ref = ref_nums[-1] if ref_nums else 1
            # Precompute all summary HTMLs for each reflection
            summary_htmls = {}
            for ref, path in reflection_files:
                if os.path.exists(path):
                    df = pd.read_csv(path)
                    grades_path = os.path.join(os.path.dirname(path), 'results', f'{course.course_name}_grades_ref{ref}.csv')
                    if not os.path.exists(grades_path):
                        grades_path = os.path.join(os.path.dirname(path), f'{course.course_name}_grades_ref{ref}.csv')
                    if os.path.exists(grades_path):
                        grades_df = pd.read_csv(grades_path)
                        if 'ID' in grades_df.columns:
                            # Remove rows with empty IDs
                            grades_df = grades_df[grades_df['ID'].notna() & (grades_df['ID'].astype(str).str.strip() != '')]
                            # Filter out 'Student, Test' from ID or Student columns
                            mask = ~grades_df['ID'].astype(str).str.strip().str.lower().eq('student, test')
                            if 'Student' in grades_df.columns:
                                mask &= ~grades_df['Student'].astype(str).str.strip().str.lower().eq('student, test')
                            grades_df = grades_df[mask]
                            grades_df = grades_df.drop_duplicates(subset=['ID'])
                            # FIX: Total students in course should be the number of students in the grade sheet
                            total_students_in_course = grades_df['ID'].nunique()
                            # Set section for each student using SIS Login ID and Section columns
                            if 'SIS Login ID' in grades_df.columns and 'Section' in grades_df.columns:
                                sis_section_map = dict(zip(grades_df['SIS Login ID'].astype(str).str.strip().str.lower(), grades_df['Section']))
                                for student in course.students.values():
                                    email_prefix = student.email.split('@')[0].strip().lower()
                                    if email_prefix in sis_section_map:
                                        student.set_section(sis_section_map[email_prefix])
                                        print(f"Student: {student.name}, Email: {student.email}, Section: {student.section}")
                        else:
                            total_students_in_course = len(grades_df)
                    else:
                        total_students_in_course = 'N/A'
                    # FIX: Total students submitted should be the number of reflection submissions
                    total_students_submitted = df['ID'].nunique() if 'ID' in df.columns else len(df)
                    summary_htmls[ref] = f'''<div id="summary-div-{ref}" style="background:#f8f9fa;padding:10px 18px;margin-bottom:12px;border-radius:6px;font-size:1.1em;{'display:none;' if ref != selected_ref else ''}"><b>Summary for Reflection {ref}:</b> <span style='margin-left:18px;'>Total students in course: <b>{total_students_in_course}</b></span> <span style='margin-left:18px;'>Total students submitted: <b>{total_students_submitted}</b></span><br><small style="color:#666;margin-top:5px;display:block;"><em>Note: "Total students in course" represents unique students with valid grade data across all reflection periods. Individual reflection counts may vary due to enrollment changes or missing data.</em></small></div>'''
                else:
                    summary_htmls[ref] = f'<div id="summary-div-{ref}" style="background:#f8f9fa;padding:10px 18px;margin-bottom:12px;border-radius:6px;font-size:1.1em;display:none;"><b>Summary for Reflection {ref}:</b> <span style="margin-left:18px;">Data not available</span><br><small style="color:#666;margin-top:5px;display:block;"><em>Note: "Total students in course" represents unique students with valid grade data across all reflection periods. Individual reflection counts may vary due to enrollment changes or missing data.</em></small></div>'
            # Render all summaries at the top
            for ref in ref_nums:
                aggregates_html += summary_htmls[ref]
            # Add dropdown for user to select reflection (JS only, no reload)
            aggregates_html += '<div style="margin-bottom:16px;">'
            aggregates_html += '<label for="reflection-select"><b>Select Reflection:</b></label> '
            aggregates_html += '<select id="reflection-select" onchange="showReflectionDiv()">'
            for ref in ref_nums:
                selected = 'selected' if ref == selected_ref else ''
                aggregates_html += f'<option value="{ref}" {selected}>Reflection {ref}</option>'
            aggregates_html += '</select>'
            aggregates_html += '</div>'
            # Remove duplicate Module Availability & Pre/Post Topic Analysis block from here
            # Delegate the heavy lifting to the helper (encapsulation step)
            emotions_topics_html, student_topics, student_quizzes, summary_topics, all_quizzes, student_topics_by_reflection, student_quizzes_by_reflection, statistical_comparison_html, support_quiz_completion_table_html, quiz_completion_rate_chart_html, csv_path = self.emotions_topics_table_builder.build(reflection_files, course, anonymized=anonymized)
            # NOTE: emotions_topics_html will be added at the bottom

            # Generate Average Grade Over Time chart from CSV data
            if csv_path:
                grade_chart_html = self._build_grade_chart_from_csv(course, csv_path)
                aggregates_html += grade_chart_html

                # Read the CSV export to get the actual total students count used in the chart
                try:
                    csv_df = pd.read_csv(csv_path)
                    # Count unique students who have any valid grade data across all reflections
                    grade_columns = [col for col in csv_df.columns if col.startswith('Ref') and col.endswith('_Grade')]
                    students_with_grades = set()
                    for grade_col in grade_columns:
                        # Count students with valid grades in this reflection
                        valid_grades = csv_df[grade_col].replace(['-', '', 'N/A', 'n/a'], pd.NA)
                        valid_students = csv_df[valid_grades.notna()]['Student_ID'].tolist()
                        students_with_grades.update(valid_students)

                    # Update the course object with the correct total count
                    actual_total_students = len(students_with_grades)
                    course.set_filtered_total_students(actual_total_students)

                    # Update the summary HTML to reflect the correct count
                    for ref in ref_nums:
                        if ref in summary_htmls:
                            # Extract the existing summary and update the total students count
                            summary_html = summary_htmls[ref]
                            # Replace the total students count with the corrected value
                            summary_html = summary_html.replace(
                                f'Total students in course: <b>{total_students_in_course}</b>',
                                f'Total students in course: <b>{actual_total_students}</b>'
                            )
                            summary_htmls[ref] = summary_html

                    print(f"DEBUG: Updated total students count from {total_students_in_course} to {actual_total_students}")
                    print(f"DEBUG: This count represents students with valid grade data across all reflections")

                except Exception as e:
                    print(f"Warning: Could not update total students count: {e}")
                    # Keep the original count if there's an error
            # Removed "No grade data available" message

            # Module Availability & Pre/Post Topic Analysis removed (research mode functionality)

            # Pre-render all reflection charts/tables as hidden divs
            for ref, path in reflection_files:
                display_style = '' if ref == selected_ref else 'display:none;'
                aggregates_html += f'<div id="reflection-div-{ref}" style="{display_style}">'  # Start div
                if os.path.exists(path):
                    df = pd.read_csv(path)
                    # Find the column for emotions (case-insensitive match)
                    emotion_col = None
                    for col in df.columns:
                        if isinstance(col, str) and col.strip().lower().startswith("how do you feel about the course so far?"):
                            emotion_col = col
                            break
                    if emotion_col:
                        # Extract and count emotions
                        emotion_counts = {}
                        student_emotions = []
                        for idx, row in df.iterrows():
                            student_id = row.get('ID', f'Row {idx+1}')
                            emotions_raw = row.get(emotion_col, '')
                            if pd.isna(emotions_raw):
                                continue
                            emotions = [e.strip() for e in str(emotions_raw).split(',') if e.strip()]
                            for emotion in emotions:
                                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
                            student_emotions.append({'Student': student_id, 'Emotions': ', '.join(emotions)})
                        # Remove '6' from emotion_counts if present
                        if '6' in emotion_counts:
                            del emotion_counts['6']
                        emotion_df = pd.DataFrame(list(emotion_counts.items()), columns=['Emotion', 'Count'])
                        total_students = len(df)
                        emotion_df['Percentage'] = (emotion_df['Count'] / total_students * 100).round(1)
                        emotion_df['Text'] = emotion_df.apply(lambda row: f"{row['Count']} ({row['Percentage']}%)", axis=1)
                        # Define a color palette for common emotions (psychologically associated colors)
                        base_palette = {
                            'Excited': '#FF6B9D',      # Bright pink/magenta (more vibrant)
                            'Satisfied': '#4CAF50',    # Green (satisfaction)
                            'Neutral': '#BDBDBD',      # Light gray (neutral)
                            'Confused': '#7E57C2',     # Purple (confusion)
                            'Frustrated': '#FF5722',   # Bright orange-red (more distinct from pink)
                            'Angry': '#E53935',        # Red (anger)
                            'Afraid': '#1976D2',       # Blue (fear)
                            'Surprised': '#FFB300',    # Orange (surprise)
                            'Excited': '#E75480',      # Pink (excitement)
                            'Satisfied': '#4CAF50',    # Green (satisfaction)
                            'Confused': '#7E57C2',     # Purple (confusion)
                            'Frustrated': '#D84315',   # Deep orange (frustration)
                            'Anxious': '#00ACC1',      # Teal (anxiety)
                            'Nervous': '#B0B0B0',      # Gray (nervousness)
                            'Neutral': '#BDBDBD',      # Light gray (neutral)
                            'Disappointed': '#6D4C41', # Brown (disappointment)
                            'Motivated': '#388E3C',    # Dark green (motivation)
                            'Hopeful': '#81C784',      # Light green (hope)
                            'Bored': '#A1887F',        # Taupe (boredom)
                        }
                        # Generate a pastel palette for unknown emotions
                        pastel_palette = plotly.colors.qualitative.Pastel
                        unique_emotions = emotion_df['Emotion'].tolist()
                        color_map = {}
                        pastel_idx = 0
                        for emotion in unique_emotions:
                            # Case-insensitive match for palette
                            found = False
                            for key in base_palette:
                                if emotion.strip().lower() == key.lower():
                                    color_map[emotion] = base_palette[key]
                                    found = True
                                    break
                            if not found:
                                # Assign a pastel color, cycle if needed
                                color_map[emotion] = pastel_palette[pastel_idx % len(pastel_palette)]
                                pastel_idx += 1
                        emotion_df['Color'] = emotion_df['Emotion'].map(color_map)
                        fig = px.bar(
                            emotion_df,
                            x='Emotion',
                            y='Count',
                            color='Emotion',
                            color_discrete_map=color_map,
                            text='Text',
                            title='Emotions Reported by Students',
                        )
                        fig.update_traces(
                            textposition='auto',
                            hovertemplate="<b>%{x}</b><br>Count: %{y}<br>Percentage: %{customdata[0]}%<br>Count & Percent: %{text}<extra></extra>",
                            customdata=emotion_df[['Percentage']].values
                        )
                        fig.update_layout(showlegend=False)
                        single_emotion_chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
                        # Add a legend for emotion colors (dynamically)
                        legend_html = '<div style="margin:10px 0;"><b>Emotion Colors:</b> '
                        for emotion in unique_emotions:
                            color = color_map[emotion]
                            legend_html += f'<span style="display:inline-block;width:16px;height:16px;background:{color};margin-right:4px;border-radius:3px;"></span> {emotion} '
                        legend_html += '</div>'
                        single_emotion_chart_html = legend_html + single_emotion_chart_html
                    else:
                        single_emotion_chart_html = '<div>No emotions data found to display.</div>'

                    # --- Emotion Pairs Table and Stacked Bar Chart ---
                    pair_counter = Counter()
                    emotion_col_actual = None
                    for col in df.columns:
                        if isinstance(col, str) and col.strip().lower().startswith("how do you feel about the course so far?"):
                            emotion_col_actual = col
                            break
                    if not emotion_col_actual:
                        aggregates_html += '<div><b>DEBUG:</b> Could not find the emotions column for pairs extraction.</div>'
                        emotion_col_actual = df.columns[0]  # fallback to first column to avoid crash
                    # Build counts for pure and mixed
                    emotion_set = set()
                    pure_counts = Counter()
                    mixed_counts = Counter()
                    for idx, row in df.iterrows():
                        emotions_raw = row.get(emotion_col_actual, '')
                        if pd.isna(emotions_raw):
                            continue
                        emotions = [e.strip().title() for e in str(emotions_raw).split(',') if e.strip()]
                        unique_emotions = sorted(set(emotions), key=lambda x: x.lower())
                        for e in unique_emotions:
                            emotion_set.add(e)
                        if len(unique_emotions) == 1:
                            pure_counts[unique_emotions[0]] += 1
                        elif len(unique_emotions) > 1:
                            for e in unique_emotions:
                                for other in unique_emotions:
                                    if e != other:
                                        mixed_counts[(e, other)] += 1
                    # Prepare table of most common pairs (unchanged)
                    pair_table_html = '<h3>Most Common Emotion Pairs</h3>'
                    pair_table_html += '<table id="emotion-pairs-table" border="1" style="border-collapse:collapse;display:none;"><tr><th>Emotion Pair</th><th>Count</th><th>Percent</th></tr>'
                    if mixed_counts:
                        total_students = len(df)
                        shown_pairs = set()
                        for (a, b), count in mixed_counts.items():
                            if (b, a) in shown_pairs or a == b:
                                continue
                            percent = round(count / total_students * 100, 1)
                            pair_table_html += f'<tr><td>{a} / {b}</td><td>{count}</td><td>{percent}%</td></tr>'
                            shown_pairs.add((a, b))
                        pair_table_html += '</table>'
                    else:
                        pair_table_html += '<tr><td colspan="3">No common emotion pairs found.</td></tr></table>'
                        pair_table_html += '<div><b>DEBUG:</b> No emotion pairs found in the data or all students reported only one emotion.</div>'
                    # --- End Emotion Pairs Table ---

                    # Table of student emotions (toggleable)
                    student_table_html = ''

                    # --- Build Stacked Bar Chart for Pure and Mixed (by Pair) ---
                    emotion_list = sorted(emotion_set)
                    # Remove '6' (custom placeholder) from emotion list if present
                    emotion_list = [e for e in emotion_list if str(e) != '6']
                    # Build a DataFrame: rows=emotions, columns=Pure + each other emotion
                    data = {e: [] for e in emotion_list}
                    for emotion in emotion_list:
                        # Pure count
                        data[emotion].append(pure_counts.get(emotion, 0))
                        # For each other emotion, count how often (other, emotion) appears in mixed_counts
                        for other in emotion_list:
                            if other == emotion:
                                continue
                            data[emotion].append(mixed_counts.get((other, emotion), 0))
                    # Build columns: 'Pure', then each other emotion
                    columns = ['Pure'] + [f"{other}+{emotion}" for emotion in emotion_list for other in emotion_list if other != emotion]
                    # But for each emotion, only keep 'Pure' and the other emotions (not all combinations)
                    stacked_rows = []
                    for idx, emotion in enumerate(emotion_list):
                        row = {'Emotion': emotion, 'Pure': pure_counts.get(emotion, 0)}
                        for other in emotion_list:
                            if other == emotion:
                                continue
                            row[f'{other}+{emotion}'] = mixed_counts.get((other, emotion), 0)
                        stacked_rows.append(row)
                    stacked_df = pd.DataFrame(stacked_rows)
                    # Melt for Plotly
                    melted = pd.melt(stacked_df, id_vars=['Emotion'], var_name='Type', value_name='Count')
                    # Remove zero counts for clarity
                    melted = melted[melted['Count'] > 0]
                    # Color palette for emotions (same as single-emotion chart)
                    base_palette = {
                        'Excited': '#FF6B9D',      # Bright pink/magenta (more vibrant)
                        'Satisfied': '#4CAF50',    # Green (satisfaction)
                        'Neutral': '#BDBDBD',      # Light gray (neutral)
                        'Confused': '#7E57C2',     # Purple (confusion)
                        'Frustrated': '#FF5722',   # Bright orange-red (more distinct from pink)
                    }
                    pastel_palette = plotly.colors.qualitative.Pastel
                    color_map_emotion = {}
                    pastel_idx = 0
                    for emotion in emotion_list:
                        found = False
                        for key in base_palette:
                            if emotion.strip().lower() == key.lower():
                                color_map_emotion[emotion] = base_palette[key]
                                found = True
                                break
                        if not found:
                            color_map_emotion[emotion] = pastel_palette[pastel_idx % len(pastel_palette)]
                            pastel_idx += 1
                    # Build traces for each (emotion, type) pair for perfect color control
                    bar_traces = []
                    for emotion in emotion_list:
                        # Pure bar for this emotion
                        pure_count = pure_counts.get(emotion, 0)
                        pure_percent = round((pure_count / total_students * 100), 1) if total_students > 0 else 0
                        pure_text = f"{pure_count} ({pure_percent}%)"
                        if pure_count > 0:
                            bar_traces.append(go.Bar(
                                x=[emotion],
                                y=[pure_count],
                                name=f'Pure {emotion}',
                                marker_color=color_map_emotion[emotion],
                                text=[pure_text],
                                textposition='auto',
                                hovertemplate=f"<b>{emotion}</b><br>Pure Count: %{{y}}<br>Percentage: {pure_percent}%<br>Count & Percent: {pure_text}<extra></extra>",
                                showlegend=False
                            ))
                        # Mixed bars for this emotion (as 2nd)
                        for other in emotion_list:
                            if other == emotion:
                                continue
                            mixed_count = mixed_counts.get((other, emotion), 0)
                            mixed_percent = round((mixed_count / total_students * 100), 1) if total_students > 0 else 0
                            mixed_text = f"{mixed_count} ({mixed_percent}%)"
                            if mixed_count > 0:
                                bar_traces.append(go.Bar(
                                    x=[emotion],
                                    y=[mixed_count],
                                    name=f'{other}+{emotion}',
                                    marker_color=color_map_emotion[other],
                                    text=[mixed_text],
                                    textposition='auto',
                                    hovertemplate=f"<b>{emotion}</b><br>Mixed with {other}: %{{y}}<br>Percentage: {mixed_percent}%<br>Count & Percent: {mixed_text}<extra></extra>",
                                    showlegend=False
                                ))
                    fig_stacked = go.Figure(data=bar_traces)
                    fig_stacked.update_layout(
                        barmode='stack',
                        title='Pure and Nuanced Mixed Emotion Pairs (as 2nd) by Students',
                        xaxis_title='Emotion',
                        yaxis_title='Number of Students',
                        bargap=0.3
                    )
                    # Add a color swatch legend above the chart
                    legend_html = '<div style="margin:10px 0;"><b>Emotion Colors:</b> '
                    for emotion in emotion_list:
                        color = color_map_emotion[emotion]
                        legend_html += f'<span style="display:inline-block;width:16px;height:16px;background:{color};margin-right:4px;border-radius:3px;"></span> {emotion} '
                    legend_html += '</div>'
                    stacked_chart_html = legend_html + fig_stacked.to_html(full_html=False, include_plotlyjs='cdn')

                    # Toggle buttons (script moved to end)
                    toggle_html = f'''
                    <div style="margin: 16px 0;">
                        <button id="show-single-emotion-{ref}" onclick="showChart{ref}('single')">Show Single Emotion Chart</button>
                        <button id="show-stacked-emotion-{ref}" onclick="showChart{ref}('stacked')">Show Pure/Mixed Stacked Chart</button>
                    </div>
                    <div id="single-emotion-chart-div-{ref}">{single_emotion_chart_html}</div>
                    <div id="stacked-emotion-chart-div-{ref}" style="display:none;">{stacked_chart_html}</div>
                    <script>
                        function showChart{ref}(which) {{
                            var singleChart = document.getElementById('single-emotion-chart-div-{ref}');
                            var stackedChart = document.getElementById('stacked-emotion-chart-div-{ref}');
                            if (singleChart) singleChart.style.display = (which === 'single') ? '' : 'none';
                            if (stackedChart) stackedChart.style.display = (which === 'stacked') ? '' : 'none';
                        }}
                        // Show single emotion chart by default
                        document.addEventListener('DOMContentLoaded', function() {{
                            showChart{ref}('single');
                        }});
                    </script>
                    '''
                    # Only show the toggle and charts, do not append pair_table_html
                    aggregates_html += toggle_html + student_table_html
                else:
                    aggregates_html += f'<div>Reflection CSV not found at: {path}</div>'
                aggregates_html += '</div>'  # End div
            # Add JS to show/hide the correct div
            aggregates_html += '''
            <script>
            function showReflectionDiv() {
                var sel = document.getElementById('reflection-select');
                var val = sel.value;
                var allDivs = document.querySelectorAll('[id^="reflection-div-"]');
                allDivs.forEach(function(div) { div.style.display = 'none'; });
                var showDiv = document.getElementById('reflection-div-' + val);
                if (showDiv) showDiv.style.display = '';
                // Toggle summary divs
                var allSummaryDivs = document.querySelectorAll('[id^="summary-div-"]');
                allSummaryDivs.forEach(function(div) { div.style.display = 'none'; });
                var showSummaryDiv = document.getElementById('summary-div-' + val);
                if (showSummaryDiv) showSummaryDiv.style.display = '';
            }
            // Show latest reflection by default
            document.addEventListener('DOMContentLoaded', function() { showReflectionDiv(); });
            </script>
            '''

            # If there are multiple reflections, show a line chart for emotion changes by percent
            if len(ref_nums) > 1:
                # Build a DataFrame: rows=reflection, columns=emotions, values=percent and count
                emotion_percent_data = []
                print(f"\n=== FOCUSED DEBUG: Emotion Analysis ===")
                all_student_emotions = {}  # Track emotions by student across reflections

                for ref, path in reflection_files:
                    print(f"Processing Reflection {ref}")
                    if os.path.exists(path):
                        df = pd.read_csv(path)
                        # Find the column for emotions (case-insensitive match)
                        emotion_col = None
                        for col in df.columns:
                            if isinstance(col, str) and col.strip().lower().startswith("how do you feel about the course so far?"):
                                emotion_col = col
                                break
                        if not emotion_col:
                            continue

                        emotion_counts = {}
                        total_students = df['ID'].nunique() if 'ID' in df.columns else len(df)
                        student_emotions_this_ref = {}

                        for idx, row in df.iterrows():
                            emotions_raw = row.get(emotion_col, '')
                            if pd.isna(emotions_raw):
                                continue
                            student_id = row.get('ID', f'unknown_{idx}')
                            emotions = [str(e).strip() for e in str(emotions_raw).split(',') if str(e).strip()]
                            # Filter out placeholder values
                            emotions = [e for e in emotions if str(e) != '6']
                            student_emotions_this_ref[student_id] = emotions

                            for emotion in emotions:
                                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

                        # Store student emotions for cross-reflection comparison
                        all_student_emotions[ref] = student_emotions_this_ref

                        print(f"  R{ref}: {total_students} students, emotions: {emotion_counts}")

                        for emotion in emotion_counts:
                            count = emotion_counts[emotion]
                            percent = (count / total_students * 100) if total_students > 0 else 0
                            emotion_percent_data.append({'Reflection': ref, 'Emotion': emotion, 'Percent': percent, 'Count': count, 'Text': f"{count} ({percent:.1f}%)"})

                # Check for identical student responses across reflections
                if len(all_student_emotions) > 1:
                    print("\n--- Checking for identical student responses ---")
                    ref_nums_sorted = sorted(all_student_emotions.keys())
                    for i in range(len(ref_nums_sorted) - 1):
                        ref1, ref2 = ref_nums_sorted[i], ref_nums_sorted[i + 1]
                        common_students = set(all_student_emotions[ref1].keys()) & set(all_student_emotions[ref2].keys())
                        identical_count = 0
                        for student in common_students:
                            if all_student_emotions[ref1][student] == all_student_emotions[ref2][student]:
                                identical_count += 1
                                print(f"  Student {student}: R{ref1} and R{ref2} have identical emotions: {all_student_emotions[ref1][student]}")
                        print(f"  R{ref1} vs R{ref2}: {identical_count}/{len(common_students)} students have identical emotions")

                print(f"=== END FOCUSED DEBUG ===\n")

                if emotion_percent_data:
                    percent_df = pd.DataFrame(emotion_percent_data)
                    # Use the same color map as the bar charts
                    color_map = {}
                    for emotion in percent_df['Emotion'].unique():
                        color_map[emotion] = color_map_emotion.get(emotion, '#888888')

                    # Wrap long emotion names for better legend display
                    def wrap_emotion_name(name, max_length=30):
                        """Wrap long emotion names for better display"""
                        if len(name) <= max_length:
                            return name
                        # Try to break at natural points
                        words = name.split()
                        if len(words) == 1:
                            # Single long word, break at max_length
                            return name[:max_length] + '<br>' + name[max_length:]
                        else:
                            # Multiple words, try to break at word boundaries
                            result = []
                            current_line = ""
                            for word in words:
                                if len(current_line + word) <= max_length:
                                    current_line += (word + " ")
                                else:
                                    if current_line:
                                        result.append(current_line.strip())
                                    current_line = word + " "
                            if current_line:
                                result.append(current_line.strip())
                            return '<br>'.join(result)

                    # Create wrapped emotion names for legend
                    wrapped_emotions = {emotion: wrap_emotion_name(emotion) for emotion in percent_df['Emotion'].unique()}
                    percent_df['Emotion_Wrapped'] = percent_df['Emotion'].map(wrapped_emotions)

                    fig_line = px.line(
                        percent_df,
                        x='Reflection',
                        y='Percent',
                        color='Emotion_Wrapped',  # Use wrapped names for legend
                        markers=True,
                        color_discrete_map=color_map,
                        title='Percent of Students Reporting Each Emotion by Reflection',
                        text='Text'
                    )

                    # Reduce text overlap by using different positions for different emotions
                    # Get unique emotions to assign different positions
                    unique_emotions = percent_df['Emotion'].unique()

                    # Improved position assignment to reduce overlap near the bottom
                    # Assign positions based on typical emotion values to minimize overlap
                    emotion_positions = {}

                    # Define positions that work well for different value ranges
                    high_positions = ['top center', 'top right', 'top left']  # For high percentages
                    mid_positions = ['middle left', 'middle right']           # For medium percentages
                    low_positions = ['bottom center', 'bottom right', 'bottom left']  # For low percentages

                    # Assign positions based on typical emotion values
                    for emotion in unique_emotions:
                        # Get average percentage for this emotion to determine position strategy
                        emotion_data = percent_df[percent_df['Emotion'] == emotion]
                        avg_percent = emotion_data['Percent'].mean()

                        if avg_percent > 20:  # High percentage emotions
                            emotion_positions[emotion] = high_positions[len(emotion_positions) % len(high_positions)]
                        elif avg_percent > 5:  # Medium percentage emotions
                            emotion_positions[emotion] = mid_positions[len(emotion_positions) % len(mid_positions)]
                        else:  # Low percentage emotions (like "freaky", "existential suffering")
                            emotion_positions[emotion] = low_positions[len(emotion_positions) % len(low_positions)]

                    # Update traces with different text positions and larger font
                    for i, trace in enumerate(fig_line.data):
                        emotion_name = trace.name
                        # Find the original emotion name (before wrapping)
                        original_emotion = None
                        for orig, wrapped in wrapped_emotions.items():
                            if wrapped == emotion_name:
                                original_emotion = orig
                                break

                        if original_emotion and original_emotion in emotion_positions:
                            position = emotion_positions[original_emotion]
                        else:
                            position = 'top center'  # Default position

                        fig_line.data[i].update(
                            texttemplate='%{text}',
                            textposition=position,
                            textfont_size=16,  # Further increased from 14
                            hovertemplate='<b>%{fullData.name}</b><br>Reflection: %{x}<br>Count: %{customdata[0]}<br>Percent: %{y:.1f}%<br>Count & Percent: %{text}<extra></extra>',
                            customdata=percent_df[percent_df['Emotion_Wrapped'] == emotion_name][['Count']].values
                        )

                    fig_line.update_layout(
                        title={
                            'text': 'Percent of Students Reporting Each Emotion by Reflection',
                            'font': {'size': 20}  # Further increased from 18
                        },
                        xaxis_title='Reflection',
                        yaxis_title='Percent of Students',
                        legend_title_text='Emotion',
                        yaxis_tickformat='.1f',
                        margin=dict(t=100, b=120, l=100, r=100),  # Reduced right margin, increased bottom margin for legend
                        height=800,  # Increased height from 700 to 800 for more vertical space
                        width=1400,  # Increased width from 1200 to 1400 for more horizontal space
                        xaxis=dict(
                            tickmode='linear',
                            dtick=1,
                            title_font={'size': 16},  # Further increased from 14
                            tickfont={'size': 14}     # Further increased from 12
                        ),
                        yaxis=dict(
                            title_font={'size': 16},  # Further increased from 14
                            tickfont={'size': 14}     # Further increased from 12
                        ),
                        legend=dict(
                            title_font={'size': 16},  # Further increased from 14
                            font={'size': 14},        # Further increased from 12
                            yanchor="bottom",
                            y=-0.15,  # Position legend below the chart
                            xanchor="center",
                            x=0.5,    # Center the legend horizontally
                            orientation="h"  # Make legend horizontal to save vertical space
                        )
                    )
                    aggregates_html += fig_line.to_html(full_html=False, include_plotlyjs='cdn')

            # --- Topic over-time chart with resolution status filter ---
            topic_percent_data = []
            topic_color_map = {}
            topic_palette = plotly.colors.qualitative.Set2 + plotly.colors.qualitative.Plotly
            topic_palette_idx = 0
            all_resolution_statuses = set()
            for ref, path in reflection_files:
                # Look for topic analysis exploded CSV in results dir
                topic_csv = os.path.join(os.path.dirname(path), 'results', f'{course.course_name}_ref{ref}_exploded.csv')
                if os.path.exists(topic_csv):
                    topic_df = pd.read_csv(topic_csv)
                    if 'primary_labels_selected' not in topic_df.columns or 'resolution_primary_labels' not in topic_df.columns:
                        continue
                    total_students = topic_df['ID'].nunique() if 'ID' in topic_df.columns else len(topic_df)
                    for (topic, res_status), group in topic_df.groupby(['primary_labels_selected', 'resolution_primary_labels']):
                        count = group['ID'].nunique() if 'ID' in group.columns else len(group)
                        percent = (count / total_students * 100) if total_students > 0 else 0
                        text = f"{count} ({percent:.1f}%)"
                        topic_percent_data.append({'Reflection': ref, 'Topic': topic, 'ResolutionStatus': res_status, 'Percent': percent, 'Count': count, 'Text': text})
                        all_resolution_statuses.add(res_status)
                        if topic not in topic_color_map:
                            topic_color_map[topic] = topic_palette[topic_palette_idx % len(topic_palette)]
                            topic_palette_idx += 1
            # Prepare JSON for frontend
            topic_percent_json = json.dumps(topic_percent_data)
            # Add dropdown and chart container
            if topic_percent_data:
                # Dropdown for resolution status
                unique_statuses = sorted([s for s in all_resolution_statuses if pd.notna(s)])
                dropdown_html = '<div style="margin-bottom:12px;"><label for="topic-resolution-select"><b>Filter by Resolution Status:</b></label> '
                dropdown_html += '<select id="topic-resolution-select" onchange="updateTopicLineChart()">'
                dropdown_html += '<option value="All">All</option>'
                for status in unique_statuses:
                    dropdown_html += f'<option value="{status}">{status.title()}</option>'
                dropdown_html += '</select></div>'
                # Chart container and hidden data
                chart_html = '<div id="topic-line-chart-container"></div>'
                chart_html += f'<div id="topic-line-data" style="display:none;">{topic_percent_json}</div>'
                aggregates_html += dropdown_html + chart_html
                # Add JS to render and update the chart
                aggregates_html += '''
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                <script>
                function updateTopicLineChart() {
                    var data = JSON.parse(document.getElementById('topic-line-data').textContent);
                    var selected = document.getElementById('topic-resolution-select').value;
                    var filtered;
                    if (selected === 'All') {
                        // Aggregate counts and recompute percent for all statuses
                        // Group by Reflection+Topic
                        var groupMap = {};
                        data.forEach(function(d) {
                            var key = d.Reflection + '||' + d.Topic;
                            if (!groupMap[key]) {
                                groupMap[key] = {Reflection: d.Reflection, Topic: d.Topic, Count: 0, Total: 0};
                            }
                            groupMap[key].Count += d.Count;
                            // Use the max total students for this reflection (should be the same for all rows with same Reflection)
                            groupMap[key].Total = Math.max(groupMap[key].Total, d.Count / (d.Percent / 100 || 1));
                        });
                        // Build aggregated array
                        filtered = Object.values(groupMap).map(function(g) {
                            var percent = (g.Total > 0) ? (g.Count / g.Total * 100) : 0;
                            return {
                                Reflection: g.Reflection,
                                Topic: g.Topic,
                                Percent: percent,
                                Count: g.Count,
                                Text: `${g.Count} (${percent.toFixed(1)}%)`
                            };
                        });
                    } else {
                        filtered = data.filter(d => d.ResolutionStatus === selected);
                    }
                    // Group by Topic for lines
                    var topics = [...new Set(filtered.map(d => d.Topic))];
                    var reflections = [...new Set(filtered.map(d => d.Reflection))].sort((a,b)=>a-b);
                    var traces = topics.map(topic => {
                        var topicData = filtered.filter(d => d.Topic === topic);
                        // Sort by reflection
                        topicData.sort((a,b)=>a.Reflection-b.Reflection);
                        return {
                            x: topicData.map(d => d.Reflection),
                            y: topicData.map(d => d.Percent),
                            text: topicData.map(d => d.Text),
                            customdata: topicData.map(d => d.Count),
                            mode: 'lines+markers+text',
                            name: topic,
                            textposition: 'bottom right',
                            textfont: {size: 10},
                            marker: {size: 8},
                            line: {width: 2},
                            hovertemplate: '<b>%{fullData.name}</b><br>Reflection: %{x}<br>Count: %{customdata}<br>Percent: %{y:.1f}%<br>Count & Percent: %{text}<extra></extra>'
                        };
                    });
                    var layout = {
                        title: 'Percent of Students Reporting Each Topic by Reflection',
                        xaxis: {title: 'Reflection', tickmode: 'linear', dtick: 1},
                        yaxis: {title: 'Percent of Students', tickformat: '.1f'},
                        legend: {title: {text: 'Topic'}},
                        margin: {t: 60, b: 40}
                    };
                    Plotly.newPlot('topic-line-chart-container', traces, layout, {responsive: true});
                }
                // Initial render
                document.addEventListener('DOMContentLoaded', updateTopicLineChart);
                </script>
                '''

            # --- Average Grade Over Time Chart ---
            avg_grade_data = []
            for ref, path in reflection_files:
                grades_path = os.path.join(os.path.dirname(path), 'results', f'{course.course_name}_grades_ref{ref}.csv')
                if not os.path.exists(grades_path):
                    grades_path = os.path.join(os.path.dirname(path), f'{course.course_name}_grades_ref{ref}.csv')
                if os.path.exists(grades_path):
                    grades_df = pd.read_csv(grades_path)
                    if 'Current Score' in grades_df.columns and 'ID' in grades_df.columns:
                        # Remove rows with empty IDs
                        grades_df = grades_df[grades_df['ID'].notna() & (grades_df['ID'].astype(str).str.strip() != '')]
                        # Filter out 'Student, Test' from ID or Student columns
                        mask = ~grades_df['ID'].astype(str).str.strip().str.lower().eq('student, test')
                        if 'Student' in grades_df.columns:
                            mask &= ~grades_df['Student'].astype(str).str.strip().str.lower().eq('student, test')
                        grades_df = grades_df[mask]
                        # Use only unique, non-empty IDs
                        grades_df = grades_df.drop_duplicates(subset=['ID'])
                        all_grades = pd.to_numeric(grades_df['Current Score'], errors='coerce').fillna(0)
                        avg_grade = all_grades.mean() if not all_grades.empty else 0.0
                        count = grades_df['ID'].nunique()
                        avg_grade_data.append({'Reflection': ref, 'AverageGrade': round(avg_grade, 2), 'Count': int(count)})

            # --- Average Grade for Reflection Submitters Only ---
            reflection_submitters_grade_data = []
            reflection_submitters = set([sid for sid in course.students if '@' in sid])
            for ref, path in reflection_files:
                grades_path = os.path.join(os.path.dirname(path), 'results', f'{course.course_name}_grades_ref{ref}.csv')
                if not os.path.exists(grades_path):
                    grades_path = os.path.join(os.path.dirname(path), f'{course.course_name}_grades_ref{ref}.csv')
                avg_grade = 0.0
                count = 0
                if os.path.exists(grades_path):
                    grades_df = pd.read_csv(grades_path)
                    if 'ID' in grades_df.columns and 'Current Score' in grades_df.columns:
                        grades_df['ID_norm'] = grades_df['ID'].astype(str).str.strip().str.lower()
                        filtered = grades_df[grades_df['ID_norm'].isin([sid.lower() for sid in reflection_submitters])]
                        all_grades = pd.to_numeric(filtered['Current Score'], errors='coerce').fillna(0)
                        avg_grade = all_grades.mean() if not all_grades.empty else 0.0
                        count = filtered['ID'].nunique()
                reflection_submitters_grade_data.append({'Reflection': ref, 'AverageGrade': round(avg_grade, 2), 'Count': int(count)})
            reflection_submitters_grade_json = json.dumps(reflection_submitters_grade_data)

            # --- Topic-Specific Average Grade Over Time Data ---
            # Use the helper for topic extraction for the chart
            student_topics_by_reflection = self.extract_student_topics_by_reflection(reflection_files, course)
            print('DEBUG: student_topics_by_reflection:', student_topics_by_reflection)
            topic_grade_data = collections.defaultdict(list)  # {topic: [{'Reflection': ref, 'AverageGrade': ..., 'Count': ...}, ...]}
            all_topics_set = set()
            for student_id, ref_topics in student_topics_by_reflection.items():
                for ref, topics in ref_topics.items():
                    for topic in topics:
                        all_topics_set.add(topic)
            print('DEBUG: all_topics_set:', all_topics_set)
            for topic in sorted(all_topics_set):
                for ref, path in reflection_files:
                    # Find all students who mentioned this topic in this reflection, and have an email ID and are in course.students
                    students_with_topic = [
                        sid for sid, ref_topics in student_topics_by_reflection.items()
                        if topic in ref_topics.get(ref, set()) and '@' in sid and sid in course.students
                    ]
                    print(f'DEBUG: Reflection {ref}, Topic "{topic}", students_with_topic:', students_with_topic)
                    grades_path = os.path.join(os.path.dirname(path), 'results', f'{course.course_name}_grades_ref{ref}.csv')
                    if not os.path.exists(grades_path):
                        grades_path = os.path.join(os.path.dirname(path), f'{course.course_name}_grades_ref{ref}.csv')
                    avg_grade = 0.0
                    count = 0
                    if os.path.exists(grades_path) and students_with_topic:
                        grades_df = pd.read_csv(grades_path)
                        print(f'DEBUG: grades_df["ID"] for Reflection {ref}:', grades_df['ID'].tolist())
                        if 'ID' in grades_df.columns and 'Current Score' in grades_df.columns:
                            grades_df['ID_norm'] = grades_df['ID'].astype(str).str.strip().str.lower()
                            students_with_topic_norm = set(sid.strip().lower() for sid in students_with_topic)
                            filtered = grades_df[grades_df['ID_norm'].isin(students_with_topic_norm)]
                            if filtered.empty:
                                students_4digit = set(sid[:4] for sid in students_with_topic if len(sid) >= 4 and sid[:4].isdigit())
                                filtered = grades_df[grades_df['ID_norm'].str[:4].isin(students_4digit)]
                            print(f'DEBUG: Matched grades for topic "{topic}" in Reflection {ref}:', filtered['ID'].tolist())
                            all_grades = pd.to_numeric(filtered['Current Score'], errors='coerce').fillna(0)
                            avg_grade = all_grades.mean() if not all_grades.empty else 0.0
                            count = filtered['ID'].nunique()
                    print(f'DEBUG: Topic "{topic}", Reflection {ref}, avg_grade: {avg_grade}, count: {count}')
                    topic_grade_data[topic].append({'Reflection': ref, 'AverageGrade': round(avg_grade, 2), 'Count': int(count)})
            topic_grade_data_json = json.dumps(topic_grade_data)

            if avg_grade_data:
                avg_grade_json = json.dumps(avg_grade_data)
                chart_html = '''<div id="avg-grade-line-chart-container" style="margin-bottom:32px;"></div>
                <div id="avg-grade-line-data" style="display:none;">''' + avg_grade_json + '''</div>'''
                chart_html += '''<div id="reflection-submitters-grade-line-data" style="display:none;">''' + reflection_submitters_grade_json + '''</div>'''
                chart_html += '''<div id="topic-grade-line-data" style="display:none;">''' + topic_grade_data_json + '''</div>'''
                chart_html += '''
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                <script>
                function renderAvgGradeLineChart() {
                    var mainData = JSON.parse(document.getElementById('avg-grade-line-data').textContent);
                    var reflectionSubmittersData = JSON.parse(document.getElementById('reflection-submitters-grade-line-data').textContent);
                    var topicData = JSON.parse(document.getElementById('topic-grade-line-data').textContent);
                    // Main average grade trace
                    var x = mainData.map(d => d.Reflection);
                    var y = mainData.map(d => d.AverageGrade);
                    var count = mainData.map(d => d.Count);
                    var text = mainData.map((d, i) => `Avg: ${d.AverageGrade} (n=${d.Count})`);
                    var traces = [{
                        x: x,
                        y: y,
                        text: text,
                        customdata: count,
                        mode: 'lines+markers+text',
                        name: 'Average Grade (All Students)',
                        textposition: 'top right',
                        textfont: {size: 11},
                        marker: {size: 8},
                        line: {width: 2},
                        hovertemplate: 'Reflection: %{x}<br>Average Grade: %{y:.2f}<br>Number of Students: %{customdata}<extra></extra>'
                    }];
                    // Add reflection submitters only line
                    var x2 = reflectionSubmittersData.map(d => d.Reflection);
                    var y2 = reflectionSubmittersData.map(d => d.AverageGrade);
                    var count2 = reflectionSubmittersData.map(d => d.Count);
                    var text2 = reflectionSubmittersData.map((d, i) => `Avg: ${d.AverageGrade} (n=${d.Count})`);
                    traces.push({
                        x: x2,
                        y: y2,
                        text: text2,
                        customdata: count2,
                        mode: 'lines+markers+text',
                        name: 'Average Grade (Reflection Submitters Only)',
                        textposition: 'top right',
                        textfont: {size: 11},
                        marker: {size: 8},
                        line: {width: 2, dash: 'dash', color: '#ff9800'},
                        hovertemplate: 'Reflection: %{x}<br>Average Grade: %{y:.2f}<br>Number of Students: %{customdata}<extra></extra>'
                    });
                    // Color palette for topics
                    var palette = [
                        '#1976d2', '#388e3c', '#fbc02d', '#d32f2f', '#7b1fa2', '#0288d1', '#c2185b', '#ff9800', '#009688', '#e91e63',
                        '#8bc34a', '#ffc107', '#00bcd4', '#9c27b0', '#ff5722', '#607d8b'
                    ];
                    var colorIdx = 0;
                    // Add a trace for each topic
                    for (var topic in topicData) {
                        var topicArr = topicData[topic];
                        var tx = topicArr.map(d => d.Reflection);
                        var ty = topicArr.map(d => d.AverageGrade);
                        var tcount = topicArr.map(d => d.Count);
                        var ttext = topicArr.map((d, i) => `${topic}: ${d.AverageGrade} (n=${d.Count})`);
                        traces.push({
                            x: tx,
                            y: ty,
                            text: ttext,
                            customdata: tcount,
                            mode: 'lines+markers+text',
                            name: topic.charAt(0).toUpperCase() + topic.slice(1),
                            textposition: 'top right',
                            textfont: {size: 10},
                            marker: {size: 7},
                            line: {width: 2, dash: 'dot', color: palette[colorIdx % palette.length]},
                            hovertemplate: 'Reflection: %{x}<br>Average Grade: %{y:.2f}<br>Number of Students: %{customdata}<extra></extra>'
                        });
                        colorIdx++;
                    }
                    var layout = {
                        title: 'Average Grade Over Time (All Students & By Topic Challenge)',
                        xaxis: {title: 'Reflection', tickmode: 'linear', dtick: 1},
                        yaxis: {
                            title: 'Average Grade',
                            // Dynamic range based on data with padding for better visibility
                            autorange: false,
                            range: function() {
                                var allGrades = [];
                                // Collect all grade values from all traces
                                allGrades = allGrades.concat(y);
                                allGrades = allGrades.concat(y2);
                                for (var topic in topicData) {
                                    var topicArr = topicData[topic];
                                    allGrades = allGrades.concat(topicArr.map(d => d.AverageGrade));
                                }
                                if (allGrades.length > 0) {
                                    var minGrade = Math.min(...allGrades);
                                    var maxGrade = Math.max(...allGrades);
                                    var padding = (maxGrade - minGrade) * 0.1; // 10% padding
                                    return [Math.max(0, minGrade - padding), Math.min(100, maxGrade + padding)];
                                }
                                return [0, 100];
                            }()
                        },
                        margin: {t: 60, b: 40}
                    };
                    Plotly.newPlot('avg-grade-line-chart-container', traces, layout, {responsive: true});
                }
                document.addEventListener('DOMContentLoaded', renderAvgGradeLineChart);
                </script>
                '''
                # OLD CHART DISABLED: Using new CSV-based chart instead

                # aggregates_html += chart_html

            # --- Original Average Grade Over Time Chart has been replaced by CSV-based version ---
            # The chart is now generated using _build_grade_chart_from_csv method above

            # Aggregate all unique student IDs across all reflection files
            all_student_ids = set()
            for ref_num, csv_path in reflection_files:
                if os.path.exists(csv_path):
                    df = pd.read_csv(csv_path)
                    if 'ID' in df.columns:
                        ids = df['ID'].dropna().astype(str).str.strip()
                        ids = ids[ids != '']
                        ids = ids[~ids.str.lower().eq('student, test')]
                        all_student_ids.update(ids)
            num_students_with_email_id = sum(1 for sid in all_student_ids if '@' in sid)
            course.set_num_students_with_email_id(num_students_with_email_id)
            # Chi-square analysis generation removed (research mode functionality)

            # Reverse chi-square analysis removed (research mode functionality)

            # Calculation exports directory removed (research mode functionality)

            # All research mode statistical analysis removed (correlation, grade distribution, module completion, Mann-Whitney U)

            # SSM Before/After Analysis removed (research mode functionality)

            # After we collect reflection files, precompute missing assignments per student for selected_ref
            try:
                missing_map = {}
                for student in students:
                    try:
                        miss = self.student_profile_builder.grade_service.get_missing_assignments_by_period(student, selected_ref, course.students)
                        missing_map[student.email] = miss or []
                    except Exception:
                        missing_map[student.email] = []
                # Attach as a simple pipe-delimited string for client-side access in the template
                for student in students:
                    setattr(student, 'missing_assignments_str', '|'.join(missing_map.get(student.email, [])))
            except Exception as _:
                pass

            # Precompute AI email drafts per student (gated by global AI disable)
            try:
                from application.model.services.summarization_service import SummarizationService
                svc = SummarizationService(base_path=os.path.join("application","model","reflections"))
                # Use the service-level gate to decide whether to generate emails
                if not getattr(svc, "_ai_disabled", None):
                    # access via module-level function
                    from application.model.services.summarization_service import _ai_disabled as _svc_ai_disabled
                    do_ai = not _svc_ai_disabled()
                else:
                    do_ai = False  # DISABLED: Email generation takes too long
                if do_ai:
                    for student in students:
                        try:
                            subj, body = svc.generate_ai_email(
                                course.course_name,
                                f"ref{selected_ref}",
                                student_email=student.email,
                                student_name=student.name,
                                missing_assignments=missing_map.get(student.email, []),
                            )
                            ai_email_data[student.email] = {"subject": subj, "body": body}
                        except Exception:
                            ai_email_data[student.email] = {"subject": "", "body": ""}
            except Exception:
                pass

            # --- Student Emotions and Topics Over Time (moved to bottom) ---
            aggregates_html += emotions_topics_html

            # Module Availability & Pre/Post Topic Analysis removed (research mode functionality)

        except Exception as e:
            aggregates_html += f'<div>Error generating class aggregates: {str(e)}</div>'
        # --- End Aggregates Tab ---

        # FIX: Set total students count from most recent reflection's grade file
        self._set_total_students_from_latest_grade_file(course, reflection_files)

        # Create anonymized students if requested
        if anonymized:
            students = self._create_anonymized_students(course.students)
        else:
            students = list(course.students.values())

        # Build performance map for filters (quiz vs assignment normalized by cohort max)
        performance_map = {}
        try:
            grades_csv = os.path.join(
                "application", "model", "reflections", course.course_name,
                f"ref{latest_ref}", f"{course.course_name}_grades_ref{latest_ref}.csv"
            )
            if os.path.exists(grades_csv):
                gdf = pd.read_csv(grades_csv)
                quiz_keywords = ["quiz", "test", "exam"]
                assign_keywords = ["assignment", "hw", "homework", "project", "lab"]
                def _is(cols, keys):
                    out = []
                    for c in cols:
                        cl = str(c).lower().strip()
                        if cl in {"id","sis user id","section","student","sis login id","current score","current grade"}:
                            continue
                        if any(k in cl for k in keys):
                            out.append(c)
                    return out
                quiz_cols = _is(gdf.columns, quiz_keywords)
                assign_cols = _is(gdf.columns, assign_keywords)
                def _norm(df, col):
                    s = pd.to_numeric(df[col], errors='coerce')
                    m = s.max(skipna=True)
                    return (s / m * 100.0) if pd.notna(m) and m else pd.Series([None]*len(df))
                quiz_pct = pd.concat([_norm(gdf, c) for c in quiz_cols], axis=1) if quiz_cols else pd.DataFrame()
                assign_pct = pd.concat([_norm(gdf, c) for c in assign_cols], axis=1) if assign_cols else pd.DataFrame()
                def _email(row):
                    try:
                        if 'ID' in row and isinstance(row['ID'], str) and '@' in row['ID']:
                            return row['ID'].strip().lower()
                        if 'SIS Login ID' in row and pd.notna(row['SIS Login ID']):
                            return f"{str(row['SIS Login ID']).strip().lower()}@charlotte.edu"
                    except Exception:
                        return None
                    return None
                emails = gdf.apply(_email, axis=1)
                quiz_avg = quiz_pct.mean(axis=1, skipna=True) if not quiz_pct.empty else pd.Series([None]*len(gdf))
                assign_avg = assign_pct.mean(axis=1, skipna=True) if not assign_pct.empty else pd.Series([None]*len(gdf))
                # exact columns for Assignments/Activities current/final scores
                lower_cols = {str(c).strip().lower(): c for c in gdf.columns}
                assign_key = None
                for name in [
                    'assignments current score',
                    'assignment current score'
                ]:
                    if name in lower_cols:
                        assign_key = lower_cols[name]
                        break
                activities_key = None
                for name in [
                    'activities current score',
                    'activities final score'
                ]:
                    if name in lower_cols:
                        activities_key = lower_cols[name]
                        break
                for i in range(len(gdf)):
                    email = emails.iloc[i]
                    if not email: continue
                    qa = quiz_avg.iloc[i] if i < len(quiz_avg) else None
                    aa = assign_avg.iloc[i] if i < len(assign_avg) else None
                    gqwaf = (qa is not None and aa is not None and qa >= 80 and aa < 80)
                    wqgaf = (qa is not None and aa is not None and aa >= 80 and qa < 80)
                    # Store rounded averages for display
                    qa_out = float(round(float(qa), 1)) if qa is not None and pd.notna(qa) else None
                    aa_out = float(round(float(aa), 1)) if aa is not None and pd.notna(aa) else None
                    # pull assignments/activities from exact columns if available
                    assign_val = None
                    activities_val = None
                    try:
                        if assign_key is not None:
                            assign_val = pd.to_numeric(gdf.iloc[i][assign_key], errors='coerce')
                            assign_val = float(assign_val) if pd.notna(assign_val) else None
                    except Exception:
                        assign_val = None
                    try:
                        if activities_key is not None:
                            activities_val = pd.to_numeric(gdf.iloc[i][activities_key], errors='coerce')
                            activities_val = float(activities_val) if pd.notna(activities_val) else None
                    except Exception:
                        activities_val = None
                    performance_map[email] = {
                        'gqwaf': gqwaf,
                        'wqgaf': wqgaf,
                        'qa': qa_out,
                        'aa': aa_out,
                        'assign_val': float(round(assign_val, 1)) if assign_val is not None else None,
                        'assign_lt80': (assign_val is not None and assign_val < 80),
                        'activities_val': float(round(activities_val, 1)) if activities_val is not None else None,
                        'activities_lt80': (activities_val is not None and activities_val < 80)
                    }
        except Exception as _:
            performance_map = {}

        # Render template
        try:
            # Build summarization HTML for the selected reflection using the new service
            try:
                print(f"DEBUG: Starting summarization for {course.course_name}/ref{selected_ref}")
                from application.model.services.summarization_service import SummarizationService
                summarization_service = SummarizationService(base_path=os.path.join("application", "model", "reflections"))
                summarization_html = summarization_service.build_report_html(course.course_name, f"ref{selected_ref}")
                print(f"DEBUG: Summarization HTML length: {len(summarization_html)}")
            except Exception as e:
                print(f"DEBUG: Summarization failed with error: {e}")
                import traceback
                traceback.print_exc()
                summarization_html = "<div>Summarization unavailable.</div>"

            # Expose an AI email generator hook by embedding a small script that calls the summarization service
            def ai_email_hook_payload(name: str, email: str, missing: list[str]) -> str:
                try:
                    # DISABLED: Email generation - just return empty
                    subject, body = "", ""
                    import json as _json
                    return _json.dumps({"subject": subject, "body": body})
                except Exception:
                    return '{}'

            ai_email_js = f"""
            <script>
            window._generateAIEmail = async function(args) {{
                try {{
                    const name = (args && args.name) || '';
                    const email = (args && args.email) || '';
                    const missing = (args && args.missing) || [];
                    const payload = {ai_email_hook_payload('NAME','EMAIL', [])};
                    // Backend cannot be called dynamically from this static HTML; the payload is built during render.
                    // Replace placeholders if we can (no-op for now) and return the static payload.
                    return payload;
                }} catch(e) {{ return null; }}
            }}
            </script>
            """

            import json as _json
            html_content = template.render(
                course=course,
                students=students,
                css=css,
                mode=mode,  # Pass mode to template
                anonymized=anonymized,  # Pass anonymized flag to template
                latest_ref=latest_ref,  # Add latest reflection number
                ref_numbers=ref_numbers,  # Add all reflection numbers
                selected_ref=selected_ref,
                student_profile=lambda student: self.student_profile_builder.build_profile(student, course),
                get_student_indicators=lambda student: self.get_student_indicators(student, course),
                missing_assignments=lambda student: self.student_profile_builder.grade_service.get_missing_assignments_by_period(student, selected_ref, course.students),
                topic_analysis=topic_builder.build_analysis(course, selected_ref),
                aggregates_html=aggregates_html,
                summarization_html=summarization_html,
                performance_map=performance_map,
                ai_email_json=_json.dumps(ai_email_data),
                ai_email_js=ai_email_js,
                # Template variables for instructor mode only
                topic_quiz_chi_square_html="",
                emotions_analysis_html=emotions_analysis_html,
                chi_square_explanation_html="",
                statistical_comparison_html="",
                support_quiz_completion_table_html="",
                quiz_completion_rate_chart_html=""
            )
            print("Template rendered successfully")

            # Debug rendered content
            print(f"HTML length: {len(html_content)}")
            print("Profile count in HTML:", html_content.count('class="student-profile"'))

            return html_content

        except Exception as e:
            print(f"Error rendering template: {e}")
            raise

    def _build_emotions_topics_table(self, reflection_files, course, anonymized=False):
        """Build a table showing emotions and topics for students with valid IDs across all reflections, and return per-student, per-reflection topic/quiz mappings."""
        print(f"DEBUG TABLE: Building emotions table with {len(reflection_files)} reflection files")
        print(f"DEBUG TABLE: Reflection files: {[(ref, os.path.basename(path)) for ref, path in reflection_files]}")

        html = '''
        <div class="emotions-topics-table-container">
            <div class="section-header" onclick="toggleEmotionsTable()">
                <span class="toggle-icon">▼</span>
                <h2>**Student Emotions and Topics Over Time</h2>
            </div>
            <div class="section-content" id="emotions-table-content">
        '''

        # Use the helper for topic extraction
        student_topics_by_reflection = self.extract_student_topics_by_reflection(reflection_files, course)

        # Create a dictionary to store student data
        student_data = {}
        # New: per-student, per-reflection topic/quiz mappings
        student_quizzes_by_reflection = {}

        # Build a mapping from student_id to Student object (email and 4-digit ID)
        student_lookup = self.emotions_topics_table_builder.build_student_lookup(course)

        # Cache for grades DataFrames per reflection
        grades_cache = {}

        # Process each reflection file
        for ref_num, csv_path in reflection_files:
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)

                # Find emotion and topic columns
                emotion_col = None
                topic_col = None
                for col in df.columns:
                    if isinstance(col, str):
                        col_lower = col.strip().lower()
                        if col_lower.startswith("how do you feel about the course so far?"):
                            emotion_col = col
                        elif col_lower.startswith("what topics would you like to discuss?"):
                            topic_col = col

                if emotion_col or topic_col:
                    for _, row in df.iterrows():
                        student_id = row.get('ID', '')
                        if pd.isna(student_id):
                            continue

                        # Convert to string and clean up
                        student_id = str(student_id).strip()

                        # Check if it's a valid ID (either email or 4-digit number)
                        is_valid_id = (
                            '@' in student_id or  # Email ID
                            (student_id.isdigit() and len(student_id) == 4)  # 4-digit ID
                        )

                        if is_valid_id:
                            if student_id not in student_data:
                                student_data[student_id] = {}

                            student_data[student_id][f'ref{ref_num}'] = {
                                'emotions': row.get(emotion_col, '') if emotion_col else '',
                                'topics': row.get(topic_col, '') if topic_col else ''
                            }
                            # New: initialize per-reflection dicts
                            if student_id not in student_topics_by_reflection:
                                student_topics_by_reflection[student_id] = {}
                            if student_id not in student_quizzes_by_reflection:
                                student_quizzes_by_reflection[student_id] = {}
                            # Extract topics from exploded topic analysis file (as in existing code)
                            topic_csv = os.path.join(os.path.dirname(csv_path), 'results', f'{course.course_name}_ref{ref_num}_exploded.csv')
                            topics_found = set()
                            if os.path.exists(topic_csv):
                                try:
                                    topic_df = pd.read_csv(topic_csv)
                                    topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                                    if topic_rows.empty and student_id.isdigit() and len(student_id) == 4:
                                        topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.startswith(student_id)]
                                    if not topic_rows.empty:
                                        topic_col = None
                                        for col in topic_rows.columns:
                                            if 'primary_labels_selected' in col or 'topic' in col.lower():
                                                topic_col = col
                                                break
                                        if topic_col and topic_col in topic_rows.columns:
                                            vals = topic_rows[topic_col].dropna().tolist()
                                            for val in vals:
                                                val_str = str(val)
                                                if ';' in val_str:
                                                    topics_found.update([v.strip().lower() for v in val_str.split(';') if v.strip()])
                                                elif ',' in val_str:
                                                    topics_found.update([v.strip().lower() for v in val_str.split(',') if v.strip()])
                                                else:
                                                    topics_found.add(val_str.strip().lower())
                                except Exception:
                                    pass
                            student_topics_by_reflection[student_id][ref_num] = topics_found
                            # Extract quizzes completed in this reflection (from grades_dict or grades_df)
                            quizzes_found = set()
                            # Try to get from Student object or grades file
                            student_obj = None
                            if hasattr(course, 'students'):
                                student_obj = course.students.get(student_id)
                            grades_dict = None
                            grades_df = None
                            row_match = None
                            if student_obj and ref_num in student_obj.reflection_data:
                                grades_dict = student_obj.reflection_data[ref_num].get('grades')
                            else:
                                grades_file = None
                                dir_path = os.path.dirname(csv_path)
                                for fname in os.listdir(dir_path):
                                    if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                                        grades_file = os.path.join(dir_path, fname)
                                        break
                                if not grades_file:
                                    results_dir = os.path.join(dir_path, 'results')
                                    if os.path.exists(results_dir):
                                        for fname in os.listdir(results_dir):
                                            if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                                                grades_file = os.path.join(results_dir, fname)
                                                break
                                if grades_file:
                                    if grades_file not in grades_cache:
                                        try:
                                            grades_cache[grades_file] = pd.read_csv(grades_file)
                                        except Exception:
                                            grades_cache[grades_file] = None
                                    grades_df = grades_cache[grades_file]
                                    if grades_df is not None and 'ID' in grades_df.columns:
                                        row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                                        if row_match.empty and student_id.isdigit() and len(student_id) == 4:
                                            row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.startswith(student_id)]
                            if grades_dict:
                                for col in grades_dict:
                                    if isinstance(col, str) and 'feedback quiz' in col.lower():
                                        try:
                                            score = float(grades_dict[col])
                                            if score > 0:
                                                quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(col)).strip()
                                                if any(c.isalpha() for c in quiz_clean):
                                                    quizzes_found.add(quiz_clean)
                                        except Exception:
                                            continue
                            elif grades_df is not None and row_match is not None and not row_match.empty:
                                for col in grades_df.columns:
                                    if isinstance(col, str) and 'feedback quiz' in col.lower():
                                        try:
                                            score = float(row_match.iloc[0][col])
                                            if score > 0:
                                                quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(col)).strip()
                                                if any(c.isalpha() for c in quiz_clean):
                                                    quizzes_found.add(quiz_clean)
                                        except Exception:
                                            continue
                            student_quizzes_by_reflection[student_id][ref_num] = quizzes_found

        # Define emotion to numeric mapping for change calculation
        emotion_value_map = {
            'excited': 6,
            'satisfied': 5,
            'neutral': 4,
            'confused': 2,
            'frustrated': 1
        }
        # Define value to sentiment mapping
        value_to_sentiment = {
            6: 'Positive',
            5: 'Positive',
            4: 'Neutral',
            2: 'Negative',
            1: 'Negative'
        }
        # Define color maps
        sentiment_bg = {
            'Positive': '#d4edda',
            'Neutral': '#f5f5f5',
            'Negative': '#f8d7da'
        }
        change_color = {
            'Increasing': '#007bff',
            'Decreasing': '#fd7e14',
            'Constant': '#333',
            'N/A': '#888'
        }

        # Create the table
        html += '<div class="table-responsive">'
        html += '<table class="emotions-topics-table">'

        # Table header
        html += '<thead><tr>'
        if not anonymized:
            html += '<th>Student ID</th>'
        expected_columns = 0 if anonymized else 1  # Start with Student ID column (if not anonymized)
        reflection_numbers = []  # Track reflection numbers for exact matching
        for ref_num, _ in reflection_files:
            html += f'<th>Reflection {ref_num}</th>'
            reflection_numbers.append(ref_num)
            expected_columns += 1
        html += '</tr></thead>'

        print(f"DEBUG TABLE: Generated {expected_columns} table headers for reflections: {reflection_numbers}")
        print(f"DEBUG TABLE: Header structure: {'Student ID + ' if not anonymized else ''}{len(reflection_numbers)} reflection columns")

        # Table body
        html += '<tbody>'
        # Collect emotion change counts for all and per reflection
        change_types = ['Increasing', 'Decreasing', 'Constant', 'N/A']
        change_counts_all = {k: 0 for k in change_types}
        change_counts_by_ref = {}
        for ref_num in reflection_numbers:
            change_counts_by_ref[ref_num] = {k: 0 for k in change_types}
        for student_id, data in sorted(student_data.items()):
            html += '<tr>'
            actual_columns = 0

            # Student ID column (only if not anonymized)
            if not anonymized:
                id_display = student_id
                if student_id.isdigit() and len(student_id) == 4:
                    id_display = f'<span class="four-digit-id">{student_id}</span>'
                html += f'<td>{id_display}</td>'
                actual_columns += 1

            prev_val = None
            prev_grade_val = None
            quizzes_shown = set()
            quiz_palette = ['#ffd6e0', '#d6eaff', '#e0ffd6', '#fff5d6', '#e0d6ff', '#d6fff5', '#ffe0d6', '#f5e1ff', '#e1f5ff', '#fffbe1']
            quiz_color_map = {}
            quiz_palette_idx = 0

            # Data columns - use EXACT same reflection numbers as headers
            for ref_num in reflection_numbers:
                # Find the matching reflection file path
                ref_path = None
                for r_num, r_path in reflection_files:
                    if r_num == ref_num:
                        ref_path = r_path
                        break

                if ref_path is None:
                    # This shouldn't happen, but handle it gracefully
                    html += '<td>-</td>'
                    actual_columns += 1
                    continue

                ref_data = data.get(f'ref{ref_num}', {})
                emotions = ref_data.get('emotions', '')
                topics = ref_data.get('topics', '')
                cell_content = []
                # --- GRADE LINE ---
                grade = "-"
                grade_color = None
                grade_val_float = None
                student_obj = student_lookup.get(student_id)
                grades_dict = None
                grades_df = None
                # Try to get from Student object
                if student_obj and ref_num in student_obj.reflection_data:
                    grades_dict = student_obj.reflection_data[ref_num].get('grades')
                    if grades_dict and 'Current Score' in grades_dict:
                        grade = grades_dict['Current Score']
                # If not found, try to load grades file for this reflection
                if grade == "-":
                    grades_file = None
                    dir_path = os.path.dirname(ref_path)
                    for fname in os.listdir(dir_path):
                        if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                            grades_file = os.path.join(dir_path, fname)
                            break
                    if not grades_file:
                        results_dir = os.path.join(dir_path, 'results')
                        if os.path.exists(results_dir):
                            for fname in os.listdir(results_dir):
                                if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                                    grades_file = os.path.join(results_dir, fname)
                                    break
                    if grades_file:
                        if grades_file not in grades_cache:
                            try:
                                grades_cache[grades_file] = pd.read_csv(grades_file)
                            except Exception:
                                grades_cache[grades_file] = None
                        grades_df = grades_cache[grades_file]
                        if grades_df is not None and 'ID' in grades_df.columns and 'Current Score' in grades_df.columns:
                            row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                            if row_match.empty and student_id.isdigit() and len(student_id) == 4:
                                row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.startswith(student_id)]
                            if not row_match.empty:
                                grade_val = row_match.iloc[0]['Current Score']
                                if pd.notna(grade_val):
                                    grade = grade_val
                # Color code the grade and determine trend/passing
                grade_trend = ''
                passing_status = ''
                try:
                    grade_val_float = float(grade)
                    if grade_val_float >= 90:
                        grade_color = '#d4edda'  # green
                    elif grade_val_float >= 80:
                        grade_color = '#fff3cd'  # yellow
                    elif grade_val_float >= 70:
                        grade_color = '#ffe5b4'  # orange
                    else:
                        grade_color = '#f8d7da'  # red
                    # Determine trend and passing/fail
                    if 'prev_grade_val' in locals() and prev_grade_val is not None:
                        if grade_val_float > prev_grade_val:
                            grade_trend = 'Increasing'
                        elif grade_val_float < prev_grade_val:
                            grade_trend = 'Decreasing'
                        else:
                            grade_trend = 'Constant'
                    if grade_val_float >= 70:
                        passing_status = 'Passing'
                    else:
                        passing_status = 'Fail'
                except Exception:
                    grade_color = None
                    grade_val_float = None
                # Build grade HTML
                if grade_color:
                    grade_display = f'{grade}'
                    if grade_trend:
                        grade_display += f', {grade_trend}'
                        if passing_status:
                            grade_display += f' ({passing_status})'
                    else:
                        grade_display += ', - (-)'
                    cell_content.append(f'<strong>Grade:</strong> <span style="background:{grade_color};border-radius:4px;padding:2px 6px;">{grade_display}</span>')
                else:
                    cell_content.append(f'<strong>Grade:</strong> {grade}')
                prev_grade_val = grade_val_float if grade_val_float is not None else prev_grade_val
                # --- FEEDBACK QUIZ COMPLETION LINE ---
                completed_quizzes = []
                row_match = pd.DataFrame()  # Initialize to avoid scope issues

                if grades_dict:
                    for col in grades_dict:
                        if isinstance(col, str) and 'feedback quiz' in col.lower():
                            try:
                                score = float(grades_dict[col])
                                if score > 0:
                                    quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(col)).strip()
                                    if any(c.isalpha() for c in quiz_clean):
                                        completed_quizzes.append(quiz_clean)
                            except Exception:
                                continue
                elif grades_df is not None:
                    # Re-find the row match for quiz processing
                    row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                    if row_match.empty and student_id.isdigit() and len(student_id) == 4:
                        row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.startswith(student_id)]

                    if not row_match.empty:
                        for col in grades_df.columns:
                            if isinstance(col, str) and 'feedback quiz' in col.lower():
                                try:
                                    score = float(row_match.iloc[0][col])
                                    if score > 0:
                                        quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(col)).strip()
                                        if any(c.isalpha() for c in quiz_clean):
                                            completed_quizzes.append(quiz_clean)
                                except Exception:
                                    continue
                # Only show quizzes not already shown for this student
                new_quizzes = []
                for quiz in completed_quizzes:
                    quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(quiz)).strip()
                    if not any(c.isalpha() for c in quiz_clean):
                        continue
                    if quiz_clean not in quizzes_shown:
                        new_quizzes.append(quiz)
                        quizzes_shown.add(quiz_clean)
                    # Assign a color if not already assigned
                    if quiz_clean not in quiz_color_map:
                        quiz_color_map[quiz_clean] = quiz_palette[quiz_palette_idx % len(quiz_palette)]
                        quiz_palette_idx += 1
                if new_quizzes:
                    colored_quizzes = []
                    for quiz in new_quizzes:
                        quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(quiz)).strip()
                        color = quiz_color_map.get(quiz_clean, '#ffd6e0')
                        text_color = '#333'
                        colored_quizzes.append(f'<span style="background:{color};color:{text_color};border-radius:4px;padding:2px 6px;margin-right:4px;">{quiz_clean}</span>')
                    quiz_html = ' '.join(colored_quizzes)
                    cell_content.append(f'<strong>Completed Feedback Quizzes:</strong> {quiz_html}')
                # Emotions line
                if emotions:
                    cell_content.append(f'<strong>Emotions:</strong> {emotions}')
                # Calculate change in emotion
                emotion_label = str(emotions).split(',')[0].strip().lower() if emotions else ''
                curr_val = emotion_value_map.get(emotion_label, 0) if emotion_label else 0
                sentiment = value_to_sentiment.get(curr_val, '') if curr_val else ''
                if prev_val is not None and curr_val != 0:
                    if curr_val > prev_val:
                        change = 'Increasing'
                    elif curr_val < prev_val:
                        change = 'Decreasing'
                    else:
                        change = 'Constant'
                elif prev_val is None and curr_val != 0:
                    change = 'N/A'
                else:
                    change = ''
                if change in change_counts_all:
                    change_counts_all[change] += 1
                    change_counts_by_ref[ref_num][change] += 1
                if emotions:
                    bg = sentiment_bg.get(sentiment, '#fff')
                    fg = change_color.get(change, '#333')
                    change_line = f'<strong>Change:</strong> '
                    change_line += f'<span style="background:{bg};color:{fg};border-radius:4px;padding:2px 6px;">'
                    if sentiment:
                        change_line += sentiment
                        if change:
                            change_line += f', {change}'
                    elif change:
                        change_line += change
                    change_line += '</span>'
                    cell_content.append(change_line)
                prev_val = curr_val if curr_val != 0 else prev_val
                if topics:
                    cell_content.append(f'<strong>Topics:</strong> {topics}')
                # Add extracted topics from exploded topic analysis file if available
                # Try to find the exploded topic analysis file for this reflection
                extracted_topics = ''
                topic_csv = os.path.join(os.path.dirname(ref_path), 'results', f'{course.course_name}_ref{ref_num}_exploded.csv')
                if os.path.exists(topic_csv):
                    try:
                        topic_df = pd.read_csv(topic_csv)
                        # Try to match by ID
                        topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                        if topic_rows.empty and student_id.isdigit() and len(student_id) == 4:
                            topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.startswith(student_id)]
                        if not topic_rows.empty:
                            # Look for a topic column (primary_labels_selected or similar)
                            topic_col = None
                            for col in topic_rows.columns:
                                if 'primary_labels_selected' in col or 'topic' in col.lower():
                                    topic_col = col
                                    break
                            if topic_col and topic_col in topic_rows.columns:
                                vals = topic_rows[topic_col].dropna().tolist()
                                all_topics = []
                                for val in vals:
                                    if isinstance(val, list):
                                        all_topics.extend(val)
                                    else:
                                        val_str = str(val)
                                        if ';' in val_str:
                                            all_topics.extend([v.strip() for v in val_str.split(';') if v.strip()])
                                        elif ',' in val_str:
                                            all_topics.extend([v.strip() for v in val_str.split(',') if v.strip()])
                                        else:
                                            all_topics.append(val_str.strip())
                                # Remove duplicates and empty strings
                                all_topics = [t for t in dict.fromkeys(all_topics) if t]
                                if all_topics:
                                    # Color map for topics
                                    topic_color_map = {
                                        'python_and_coding': '#3572A5',
                                        'github': '#24292e',
                                        'time_management_and_motivation': '#f39c12',
                                        'mysql': '#00758f',
                                        'api': '#16a085',
                                        'ide_package_software_installation': '#8e44ad',
                                        'html': '#e34c26',
                                        'group_work': '#27ae60',
                                        'sdlc': '#2c3e50',
                                        'sway': '#e91e63',
                                        'other_primary': '#607d8b',
                                        'other_secondary': '#78909c',
                                        'other': '#95a5a6',
                                        'none': '#bdbdbd'
                                    }
                                    pastel_palette = ['#ffd6e0', '#d6eaff', '#e0ffd6', '#fff5d6', '#e0d6ff', '#d6fff5', '#ffe0d6']
                                    pastel_idx = 0
                                    topic_color_assign = {}
                                    colored_topics = []
                                    for topic in all_topics:
                                        key = topic.lower().replace(' ', '_')
                                        color = topic_color_map.get(key)
                                        if not color:
                                            if key not in topic_color_assign:
                                                topic_color_assign[key] = pastel_palette[pastel_idx % len(pastel_palette)]
                                                pastel_idx += 1
                                            color = topic_color_assign[key]
                                        text_color = '#fff' if color not in ['#fff5d6', '#ffd6e0', '#e0ffd6', '#fff3cd', '#ffe5b4', '#e0d6ff', '#d6fff5', '#ffe0d6', '#f39c12', '#bdbdbd', '#95a5a6'] else '#333'
                                        colored_topics.append(
                                            f'<span style="background:{color};color:{text_color};border-radius:4px;padding:2px 6px;margin-right:4px;">{topic}</span>'
                                        )
                                    extracted_topics = ' '.join(colored_topics)
                    except Exception:
                        pass
                if extracted_topics:
                    cell_content.append(f'<strong>Extracted Topics:</strong> {extracted_topics}')
                html += f'<td>{"<br>".join(cell_content) if cell_content else "-"}</td>'
                actual_columns += 1

            # Validate column count matches expected
            if actual_columns != expected_columns:
                print(f"WARNING: Column mismatch for student {student_id}: expected {expected_columns}, got {actual_columns}")
                # Add empty cells if needed to maintain alignment
                while actual_columns < expected_columns:
                    html += '<td>-</td>'
                    actual_columns += 1

            html += '</tr>'
        html += '</tbody></table></div>'
        # Add dropdown and chart container for emotion change bar chart
        chart_data = {'All Reflections': change_counts_all}
        for ref_num, counts in change_counts_by_ref.items():
            chart_data[f'Ref {ref_num}'] = counts
        chart_data_json = json.dumps(chart_data)
        html += '''<div style="margin:18px 0 8px 0;">
            <label for="emotion-change-select"><b>Show Emotion Change Counts for:</b></label>
            <select id="emotion-change-select" style="margin-left:8px;">
                <option value="All Reflections">All Reflections</option>'''
        for ref_num in reflection_numbers:
            html += f'<option value="Ref {ref_num}">Ref {ref_num}</option>'
        html += '''</select></div>
        <div id="emotion-change-bar-chart"></div>
        <div id="emotion-change-bar-data" style="display:none;">''' + chart_data_json + '''</div>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script>
        function renderEmotionChangeBarChart(which) {
            var data = JSON.parse(document.getElementById('emotion-change-bar-data').textContent);
            var counts = data[which];
            var labels = ['Increasing', 'Decreasing', 'Constant', 'N/A'];
            var values = labels.map(l => counts[l] || 0);
            var colors = ['#007bff', '#fd7e14', '#333', '#888'];
            var trace = {
                x: labels,
                y: values,
                marker: {color: colors},
                text: values,
                textposition: 'auto',
                type: 'bar'
            };
            var layout = {
                title: 'Counts of Emotion Changes (' + which + ')',
                xaxis: {title: 'Emotion Change'},
                yaxis: {title: 'Count'},
                margin: {t: 40, b: 40},
                plot_bgcolor: '#fff'
            };
            Plotly.newPlot('emotion-change-bar-chart', [trace], layout, {responsive: true});
        }
        document.getElementById('emotion-change-select').addEventListener('change', function() {
            renderEmotionChangeBarChart(this.value);
        });
        // Initial render
        renderEmotionChangeBarChart('All Reflections');
        </script>
        '''
        html += '''
            </div>
        </div>
        <script>
            function toggleEmotionsTable() {
                const content = document.getElementById('emotions-table-content');
                const header = document.querySelector('.emotions-topics-table-container .section-header');
                const icon = header.querySelector('.toggle-icon');

                if (content.style.display === 'none') {
                    content.style.display = 'block';
                    icon.textContent = '▼';
                    header.classList.remove('collapsed');
                } else {
                    content.style.display = 'none';
                    icon.textContent = '▶';
                    header.classList.add('collapsed');
                }
            }

            // Initialize the table as collapsed
            document.addEventListener('DOMContentLoaded', function() {
                const content = document.getElementById('emotions-table-content');
                const header = document.querySelector('.emotions-topics-table-container .section-header');
                const icon = header.querySelector('.toggle-icon');
                content.style.display = 'none';
                icon.textContent = '▶';
                header.classList.add('collapsed');
            });
        </script>
        '''

        # --- Add summary table for topics and support quizzes ---
        summary_topics = [
            'python_and_coding', 'github', 'time_management_and_motivation',
            'mysql', 'api', 'ide_package_software_installation', 'html',
            'group_work', 'sdlc', 'sway', 'other_primary', 'other_secondary', 'none'
        ]
        # 1. Gather all quizzes (cleaned names)
        all_quizzes_set = set()
        # 2. For each topic, map topic -> set of students
        topic_students = {topic: set() for topic in summary_topics}
        # 3. For each student, gather all quizzes completed at least once
        student_quizzes = {}
        # 4. For each student, gather all topics written at least once
        student_topics = {}
        for student_id, data in student_data.items():
            quizzes_completed = set()
            topics_written = set()
            for ref_num, ref_path in reflection_files:
                # --- Gather quizzes ---
                # Try to get from Student object or grades file
                student_obj = student_lookup.get(student_id)
                grades_dict = None
                grades_df = None
                row_match = None
                if student_obj and ref_num in student_obj.reflection_data:
                    grades_dict = student_obj.reflection_data[ref_num].get('grades')
                else:
                    grades_file = None
                    dir_path = os.path.dirname(ref_path)
                    for fname in os.listdir(dir_path):
                        if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                            grades_file = os.path.join(dir_path, fname)
                            break
                    if not grades_file:
                        results_dir = os.path.join(dir_path, 'results')
                        if os.path.exists(results_dir):
                            for fname in os.listdir(results_dir):
                                if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                                    grades_file = os.path.join(results_dir, fname)
                                    break
                    if grades_file:
                        if grades_file not in grades_cache:
                            try:
                                grades_cache[grades_file] = pd.read_csv(grades_file)
                            except Exception:
                                grades_cache[grades_file] = None
                        grades_df = grades_cache[grades_file]
                        if grades_df is not None and 'ID' in grades_df.columns:
                            row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                            if row_match.empty and student_id.isdigit() and len(student_id) == 4:
                                row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.startswith(student_id)]
                # Collect quizzes from grades_dict
                if grades_dict:
                    for col in grades_dict:
                        if isinstance(col, str) and 'feedback quiz' in col.lower():
                            try:
                                score = float(grades_dict[col])
                                if score > 0:
                                    quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(col)).strip()
                                    if any(c.isalpha() for c in quiz_clean):
                                        quizzes_completed.add(quiz_clean)
                                        all_quizzes_set.add(quiz_clean)
                            except Exception:
                                continue
                # Collect quizzes from grades_df
                elif grades_df is not None and row_match is not None and not row_match.empty:
                    for col in grades_df.columns:
                        if isinstance(col, str) and 'feedback quiz' in col.lower():
                            try:
                                score = float(row_match.iloc[0][col])
                                if score > 0:
                                    quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(col)).strip()
                                    if any(c.isalpha() for c in quiz_clean):
                                        quizzes_completed.add(quiz_clean)
                                        all_quizzes_set.add(quiz_clean)
                            except Exception:
                                continue
                # --- Gather topics ---
                ref_data = data.get(f'ref{ref_num}', {})
                # Extracted topics from topic analysis file
                topic_csv = os.path.join(os.path.dirname(ref_path), 'results', f'{course.course_name}_ref{ref_num}_exploded.csv')
                topics_found = set()
                if os.path.exists(topic_csv):
                    try:
                        topic_df = pd.read_csv(topic_csv)
                        topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                        if topic_rows.empty and student_id.isdigit() and len(student_id) == 4:
                            topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.startswith(student_id)]
                        if not topic_rows.empty:
                            topic_col = None
                            for col in topic_rows.columns:
                                if 'primary_labels_selected' in col or 'topic' in col.lower():
                                    topic_col = col
                                    break
                            if topic_col and topic_col in topic_rows.columns:
                                vals = topic_rows[topic_col].dropna().tolist()
                                for val in vals:
                                    val_str = str(val)
                                    if ';' in val_str:
                                        topics_found.update([v.strip() for v in val_str.split(';') if v.strip()])
                                    elif ',' in val_str:
                                        topics_found.update([v.strip() for v in val_str.split(',') if v.strip()])
                                    else:
                                        topics_found.add(val_str.strip())
                    except Exception:
                        pass
                # Normalize topics to match summary_topics
                for t in topics_found:
                    t_key = t.lower().replace(' ', '_')
                    if t_key in summary_topics:
                        topics_written.add(t_key)
            student_quizzes[student_id] = quizzes_completed
            student_topics[student_id] = topics_written
            for t in topics_written:
                if t in topic_students:
                    topic_students[t].add(student_id)
        all_quizzes = sorted(all_quizzes_set)
        # Get the number of students with email-format IDs from the Course object
        num_students_with_email_id = course.get_num_students_with_email_id()
        # Build the table
        support_quiz_completion_table_html = '<div class="table-responsive" style="margin-top:32px;">'
        support_quiz_completion_table_html += '<h3>Support Quiz Completion by Topic</h3>'
        support_quiz_completion_table_html += '<table class="emotions-topics-table">'
        support_quiz_completion_table_html += '<thead><tr><th>Topic</th><th># Students</th>'
        for quiz in all_quizzes:
            support_quiz_completion_table_html += f'<th>{quiz}</th>'
        support_quiz_completion_table_html += '</tr></thead><tbody>'
        for topic in summary_topics:
            students = topic_students[topic]
            count = len(students)
            percent = (count / num_students_with_email_id * 100) if num_students_with_email_id > 0 else 0
            support_quiz_completion_table_html += f'<tr><td>{topic}</td><td>{count} ({percent:.0f}%)</td>'
            for quiz in all_quizzes:
                quiz_count = sum(1 for s in students if quiz in student_quizzes.get(s, set()))
                quiz_percent_all = (quiz_count / num_students_with_email_id * 100) if num_students_with_email_id > 0 else 0
                quiz_percent_topic = (quiz_count / count * 100) if count > 0 else 0
                support_quiz_completion_table_html += f'<td>{quiz_count} ({quiz_percent_all:.0f}% of all, {quiz_percent_topic:.1f}% of topic)</td>'
            support_quiz_completion_table_html += '</tr>'
        support_quiz_completion_table_html += '</tbody></table></div>'
        # --- Visualization of "of topic" rates ---
        viz_data = []
        for topic in summary_topics:
            students = topic_students[topic]
            count = len(students)
            for quiz in all_quizzes:
                quiz_count = sum(1 for s in students if quiz in student_quizzes.get(s, set()))
                quiz_percent_topic = (quiz_count / count * 100) if count > 0 else 0
                viz_data.append({'Topic': topic, 'Quiz': quiz, 'PercentOfTopic': quiz_percent_topic})
        try:
            viz_df = pd.DataFrame(viz_data)
            quiz_palette = plotly.colors.qualitative.Plotly + plotly.colors.qualitative.Set2 + plotly.colors.qualitative.Pastel
            quiz_color_map = {quiz: quiz_palette[i % len(quiz_palette)] for i, quiz in enumerate(all_quizzes)}
            fig = px.bar(
                viz_df, x='Topic', y='PercentOfTopic', color='Quiz', barmode='group',
                title='Quiz Completion Rate by Topic (of topic)',
                labels={'PercentOfTopic': '% Completed (of topic)'},
                color_discrete_map=quiz_color_map
            )
            fig.update_layout(margin=dict(t=60, b=40))
            quiz_completion_rate_chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
        except Exception as e:
            quiz_completion_rate_chart_html = f'<div style="color:red;">Error generating visualization: {e}</div>'

        # --- Collapsible, color-coded statistical comparison section ---
        # Remove any inclusion of the chi-square legend or chi-square table from this block
        statistical_comparison_html = self._build_statistical_comparison_card(summary_topics, all_quizzes, topic_students, student_quizzes)

        # Export data to CSV and get the path for chart generation
        csv_path = None
        try:
            csv_path = self.export_emotions_topics_to_csv(reflection_files, course)
        except Exception as e:
            print(f"Warning: Failed to export CSV: {e}")

        return html, student_topics, student_quizzes, summary_topics, all_quizzes, student_topics_by_reflection, student_quizzes_by_reflection, statistical_comparison_html, support_quiz_completion_table_html, quiz_completion_rate_chart_html, csv_path

    def _build_statistical_comparison_card(self, summary_topics, all_quizzes, topic_students, student_quizzes):
        quiz_colors = [
            '#1976d2',  # blue
            '#388e3c',  # green
            '#fbc02d',  # yellow
            '#d32f2f',  # red
            '#7b1fa2',  # purple
            '#0288d1',  # light blue
            '#c2185b',  # pink
        ]
        quiz_color_map = {quiz: quiz_colors[i % len(quiz_colors)] for i, quiz in enumerate(all_quizzes)}
        html = ''
        html += '<div style="margin-bottom:16px; font-size:1.1em;">'
        html += '<b>Statistical Comparison of "of topic" Rates Between Topics (per Quiz)</b><br>'
        html += 'This section compares the rates at which students who mention a topic complete each quiz, using a chi-square test for each quiz.'
        html += '</div>'
        html += '<div class="table-responsive">'
        html += '<table class="emotions-topics-table"><thead><tr><th>Quiz</th><th>p-value</th><th>Significance</th></tr></thead><tbody>'
        for quiz in all_quizzes:
            color = quiz_color_map.get(quiz, '#333')
            # Build contingency table: rows=topics, cols=[completed, not completed]
            table = []
            topic_labels = []
            for topic in summary_topics:
                students = topic_students[topic]
                count = len(students)
                quiz_count = sum(1 for s in students if quiz in student_quizzes.get(s, set()))
                not_quiz_count = count - quiz_count
                if count > 0:
                    table.append([quiz_count, not_quiz_count])
                    topic_labels.append(topic)
            if len(table) > 1:
                try:
                    chi2, p, dof, expected = chi2_contingency(table)
                    html += f'<tr><td style="color:{color}"><b>{quiz}</b></td><td>{p:.4f}</td>'
                    if p < 0.05:
                        html += f'<td><span style="color:#388e3c;">Significant difference (p={p:.4f})</span></td>'
                    else:
                        html += f'<td>No significant difference (p={p:.4f})</td>'
                    html += '</tr>'
                except Exception as e:
                    html += f'<tr><td>{quiz}</td><td colspan="2">Error: {e}</td></tr>'
        html += '</tbody></table>'
        html += '</div>'
        return html

    # Chi-square topic-quiz analysis method removed (research mode functionality)

    # Chi-square explanation method removed (research mode functionality)

    # Chi-square legend method removed (research mode functionality)

    # Reverse chi-square analysis method removed (research mode functionality)

    def _build_module_availability_and_prepost_analysis(self, course, reflection_files, summary_topics, all_quizzes, student_topics, student_quizzes, student_topics_by_reflection, student_quizzes_by_reflection):
        """Detect module availability, run pre/post topic analysis, and visualize topic frequency changes using per-reflection data."""
        import plotly.graph_objects as go
        import plotly.express as px
        import pandas as pd
        html = '<details style="margin-top:32px;"><summary style="font-size:1.2em;cursor:pointer;"><b>Module Availability & Pre/Post Topic Analysis</b></summary>'
        # Only use whole number reflections
        ref_nums = [ref for ref, _ in reflection_files if isinstance(ref, int) or (isinstance(ref, float) and ref.is_integer())]
        ref_nums = [int(ref) for ref in ref_nums]
        # Ensure group_work and time_management_and_motivation are included
        if 'group_work' not in summary_topics:
            summary_topics.append('group_work')
        if 'time_management_and_motivation' not in summary_topics:
            summary_topics.append('time_management_and_motivation')
        if 'Group Work Module Feedback Quiz' not in all_quizzes:
            all_quizzes.append('Group Work Module Feedback Quiz')
        if 'Time Management Module Feedback Quiz' not in all_quizzes:
            all_quizzes.append('Time Management Module Feedback Quiz')
        # 1. Detect first reflection where each module was completed by any student
        module_first_available = {}
        for quiz in all_quizzes:
            first_ref = None
            for student_id, quizzes_by_ref in student_quizzes_by_reflection.items():
                for ref_num in sorted(ref_nums):
                    if quiz in quizzes_by_ref.get(ref_num, set()):
                        if first_ref is None or ref_num < first_ref:
                            first_ref = ref_num
            module_first_available[quiz] = first_ref
        # 2. For each topic, count how many students reported it in each reflection
        topic_freq_by_ref = {topic: {ref: 0 for ref in ref_nums} for topic in summary_topics}
        for ref_num in ref_nums:
            for topic in summary_topics:
                count = 0
                for student_id, topics_by_ref in student_topics_by_reflection.items():
                    if topic in topics_by_ref.get(ref_num, set()):
                        count += 1
                topic_freq_by_ref[topic][ref_num] = count
        # 3. For each module, plot topic frequency across reflections
        html += '<div style="margin-bottom:12px;">'
        html += '<b>Module First Available (by Reflection):</b><br>'
        for quiz in all_quizzes:
            first_ref = module_first_available.get(quiz, None)
            html += f'<span style="margin-right:18px;"><b>{quiz}:</b> {"N/A" if first_ref is None else f"Reflection {first_ref}"}</span>'
        html += '</div>'
        # Add explicit pairs for group_work and time_management_and_motivation
        explicit_pairs = [
            ('Group Work Module Feedback Quiz', 'group_work'),
            ('Time Management Module Feedback Quiz', 'time_management_and_motivation')
        ]
        for quiz in all_quizzes:
            # Guess related topic by matching quiz name to topic name
            related_topic = None
            for topic in summary_topics:
                if topic in quiz.lower():
                    related_topic = topic
                    break
            # If not found, check explicit pairs
            if not related_topic:
                for q, t in explicit_pairs:
                    if quiz == q:
                        related_topic = t
                        break
            if not related_topic:
                continue
            first_ref = module_first_available.get(quiz, None)
            # Gather topic frequency across reflections
            x = []
            y = []
            for ref in sorted(ref_nums):
                x.append(ref)
                y.append(topic_freq_by_ref[related_topic].get(ref, 0))
            # Pre/post split
            if first_ref:
                pre = [y[i] for i, r in enumerate(x) if r < first_ref]
                post = [y[i] for i, r in enumerate(x) if r >= first_ref]
                pre_mean = sum(pre)/len(pre) if pre else 0
                post_mean = sum(post)/len(post) if post else 0
                html += f'<div style="margin-top:18px;"><b>{quiz} ({related_topic}):</b> Pre-mean: {pre_mean:.2f}, Post-mean: {post_mean:.2f}'
                if post_mean < pre_mean:
                    html += ' <span style="color:#388e3c;">(decrease after module)</span>'
                elif post_mean > pre_mean:
                    html += ' <span style="color:#d32f2f;">(increase after module)</span>'
                else:
                    html += ' <span>(no change)</span>'
                html += '</div>'
            # Plot
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', name=related_topic, line=dict(color='#1976d2')))
            if first_ref:
                fig.add_vline(x=first_ref, line_dash='dash', line_color='#d32f2f', annotation_text='Module Available', annotation_position='top right')
            fig.update_layout(title=f'Topic Frequency Over Time: {related_topic} (related to {quiz})', xaxis_title='Reflection', yaxis_title='Count of Students Mentioning Topic', margin=dict(t=60, b=40), xaxis=dict(tickmode='array', tickvals=x))
            html += fig.to_html(full_html=False, include_plotlyjs=False)
        html += '</details>'
        return html

    def extract_student_topics_by_reflection(self, reflection_files, course):
        """Extract per-student, per-reflection topic mappings using robust ID matching."""
        student_topics_by_reflection = {}
        for ref_num, csv_path in reflection_files:
            print(f"[extract_student_topics_by_reflection] Processing reflection {ref_num}, file: {csv_path}")
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    student_id = row.get('ID', '')
                    if pd.isna(student_id):
                        continue
                    student_id = str(student_id).strip()
                    is_valid_id = (
                        '@' in student_id or  # Email ID
                        (student_id.isdigit() and len(student_id) == 4)  # 4-digit ID
                    )
                    if not is_valid_id:
                        continue
                    if student_id not in student_topics_by_reflection:
                        student_topics_by_reflection[student_id] = {}
                    # Extract topics from exploded topic analysis file
                    topic_csv = os.path.join(os.path.dirname(csv_path), 'results', f'{course.course_name}_ref{ref_num}_exploded.csv')
                    topics_found = set()
                    if os.path.exists(topic_csv):
                        try:
                            topic_df = pd.read_csv(topic_csv)
                            topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                            if topic_rows.empty and student_id.isdigit() and len(student_id) == 4:
                                topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.startswith(student_id)]
                            if not topic_rows.empty:
                                topic_col = None
                                for col in topic_rows.columns:
                                    if 'primary_labels_selected' in col or 'topic' in col.lower():
                                        topic_col = col
                                        break
                                if topic_col and topic_col in topic_rows.columns:
                                    vals = topic_rows[topic_col].dropna().tolist()
                                    for val in vals:
                                        val_str = str(val)
                                        if ';' in val_str:
                                            topics_found.update([v.strip().lower() for v in val_str.split(';') if v.strip()])
                                        elif ',' in val_str:
                                            topics_found.update([v.strip().lower() for v in val_str.split(',') if v.strip()])
                                        else:
                                            topics_found.add(val_str.strip().lower())
                                print(f"[extract_student_topics_by_reflection] Student {student_id}, Reflection {ref_num}, Topics found: {topics_found}")
                        except Exception as e:
                            print(f"[extract_student_topics_by_reflection] Error reading {topic_csv}: {e}")
                    student_topics_by_reflection[student_id][ref_num] = topics_found
        print(f"[extract_student_topics_by_reflection] Final mapping: {student_topics_by_reflection}")
        return student_topics_by_reflection

    def get_student_topic_grade_map(self, reflection_files, course):
        """Return a mapping {topic: {ref_num: [grades]}} for students with email IDs who submitted reflections."""
        # Build a mapping from student_id to Student object (email and 4-digit ID)
        student_lookup = {}
        for student in course.students.values():
            student_lookup[student.email] = student
            if student.email.split('@')[0].isdigit() and len(student.email.split('@')[0]) == 4:
                student_lookup[student.email.split('@')[0]] = student
        # Cache for grades DataFrames per reflection
        grades_cache = {}
        # Build topic mapping
        topic_grade_map = {}  # {topic: {ref_num: [grades]}}
        for ref_num, csv_path in reflection_files:
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    student_id = row.get('ID', '')
                    if pd.isna(student_id):
                        continue
                    student_id = str(student_id).strip()
                    # Only use students with email IDs
                    if '@' not in student_id or student_id not in course.students:
                        continue
                    # Extract topics from exploded topic analysis file
                    topic_csv = os.path.join(os.path.dirname(csv_path), 'results', f'{course.course_name}_ref{ref_num}_exploded.csv')
                    topics_found = set()
                    if os.path.exists(topic_csv):
                        try:
                            topic_df = pd.read_csv(topic_csv)
                            topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                            if topic_rows.empty and student_id.isdigit() and len(student_id) == 4:
                                topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.startswith(student_id)]
                            if not topic_rows.empty:
                                topic_col = None
                                for col in topic_rows.columns:
                                    if 'primary_labels_selected' in col or 'topic' in col.lower():
                                        topic_col = col
                                        break
                                if topic_col and topic_col in topic_rows.columns:
                                    vals = topic_rows[topic_col].dropna().tolist()
                                    for val in vals:
                                        val_str = str(val)
                                        if ';' in val_str:
                                            topics_found.update([v.strip().lower() for v in val_str.split(';') if v.strip()])
                                        elif ',' in val_str:
                                            topics_found.update([v.strip().lower() for v in val_str.split(',') if v.strip()])
                                        else:
                                            topics_found.add(val_str.strip().lower())
                        except Exception:
                            pass
                    # Get grade for this student/reflection
                    grade = None
                    grades_dict = None
                    grades_df = None
                    row_match = None
                    student_obj = course.students.get(student_id)
                    if student_obj and ref_num in student_obj.reflection_data:
                        grades_dict = student_obj.reflection_data[ref_num].get('grades')
                        if grades_dict and 'Current Score' in grades_dict:
                            try:
                                grade = float(grades_dict['Current Score'])
                            except Exception:
                                grade = None
                    if grade is None:
                        grades_file = None
                        dir_path = os.path.dirname(csv_path)
                        for fname in os.listdir(dir_path):
                            if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                                grades_file = os.path.join(dir_path, fname)
                                break
                        if not grades_file:
                            results_dir = os.path.join(dir_path, 'results')
                            if os.path.exists(results_dir):
                                for fname in os.listdir(results_dir):
                                    if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                                        grades_file = os.path.join(results_dir, fname)
                                        break
                        if grades_file:
                            if grades_file not in grades_cache:
                                try:
                                    grades_cache[grades_file] = pd.read_csv(grades_file)
                                except Exception:
                                    grades_cache[grades_file] = None
                            grades_df = grades_cache[grades_file]
                            if grades_df is not None and 'ID' in grades_df.columns and 'Current Score' in grades_df.columns:
                                row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]
                                if row_match.empty and student_id.isdigit() and len(student_id) == 4:
                                    row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.startswith(student_id)]
                                if not row_match.empty:
                                    grade_val = row_match.iloc[0]['Current Score']
                                    if pd.notna(grade_val):
                                        try:
                                            grade = float(grade_val)
                                        except Exception:
                                            grade = None
                    # Map topics to grades
                    for topic in topics_found:
                        if topic not in topic_grade_map:
                            topic_grade_map[topic] = {}
                        if ref_num not in topic_grade_map[topic]:
                            topic_grade_map[topic][ref_num] = []
                        if grade is not None:
                            topic_grade_map[topic][ref_num].append(grade)
        return topic_grade_map

    def export_emotions_topics_to_csv(self, reflection_files, course, output_dir=None):
        """Export student emotions and topics data to CSV format"""
        if output_dir is None:
            # Create output directory in the course folder
            course_dir = os.path.join("application", "model", "reflections", course.course_name)
            output_dir = os.path.join(course_dir, "exports")
            os.makedirs(output_dir, exist_ok=True)

        # Collect student data similar to _build_emotions_topics_table
        student_data = {}
        student_lookup = {}

        # Build student lookup
        for student in course.students.values():
            student_lookup[student.email] = student
            if student.email.split('@')[0].isdigit() and len(student.email.split('@')[0]) == 4:
                student_lookup[student.email.split('@')[0]] = student

        # Cache for grades DataFrames
        grades_cache = {}

        # Define emotion to numeric mapping
        emotion_value_map = {
            'excited': 6,
            'satisfied': 5,
            'neutral': 4,
            'confused': 2,
            'frustrated': 1
        }

        print(f"DEBUG: Starting export for {len(reflection_files)} reflections")

        # Process each reflection file
        for ref_num, csv_path in reflection_files:
            print(f"DEBUG: Processing reflection {ref_num} from {csv_path}")

            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)

                # Find emotion and topic columns
                emotion_col = None
                topic_col = None
                for col in df.columns:
                    if isinstance(col, str):
                        col_lower = col.strip().lower()
                        if col_lower.startswith("how do you feel about the course so far?"):
                            emotion_col = col
                        elif col_lower.startswith("what topics would you like to discuss?"):
                            topic_col = col

                if emotion_col or topic_col:
                    for _, row in df.iterrows():
                        student_id = row.get('ID', '')
                        if pd.isna(student_id):
                            continue

                        student_id = str(student_id).strip()

                        # Check if it's a valid ID
                        is_valid_id = (
                            '@' in student_id or
                            (student_id.isdigit() and len(student_id) == 4)
                        )

                        if is_valid_id:
                            if student_id not in student_data:
                                student_data[student_id] = {}

                            # Get basic reflection data
                            emotions = row.get(emotion_col, '') if emotion_col else ''
                            topics = row.get(topic_col, '') if topic_col else ''

                            # Process this student using helper method
                            self._process_student_reflection_data(student_id, ref_num, csv_path, emotions, topics,
                                                                student_lookup, grades_cache, emotion_value_map, student_data)

                # Second, process ALL students from grade files (even those who didn't submit reflections)
                dir_path = os.path.dirname(csv_path)
                grades_file = None
                for fname in os.listdir(dir_path):
                    if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                        grades_file = os.path.join(dir_path, fname)
                        print(f"DEBUG: Found grades file for ref{ref_num}: {grades_file}")
                        break

                if not grades_file:
                    results_dir = os.path.join(dir_path, 'results')
                    if os.path.exists(results_dir):
                        for fname in os.listdir(results_dir):
                            if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                                grades_file = os.path.join(results_dir, fname)
                                print(f"DEBUG: Found grades file in results for ref{ref_num}: {grades_file}")
                                break

                if grades_file and os.path.exists(grades_file):
                    try:
                        grades_df = pd.read_csv(grades_file)
                        print(f"DEBUG: Loaded grades file with {len(grades_df)} rows and columns: {list(grades_df.columns)}")

                        if 'ID' in grades_df.columns and 'Current Score' in grades_df.columns:
                            valid_grades_count = 0
                            # Process each student in the grades file
                            for _, grade_row in grades_df.iterrows():
                                grade_student_id = str(grade_row.get('ID', '')).strip()
                                if grade_student_id and grade_student_id.lower() != 'student, test':
                                    current_score = grade_row.get('Current Score')
                                    if pd.notna(current_score) and str(current_score).strip() not in ['-', '', 'N/A', 'n/a']:
                                        valid_grades_count += 1

                                    # Skip if we already processed this student from reflection data
                                    if grade_student_id not in student_data:
                                        student_data[grade_student_id] = {}

                                    # Check if this reflection data already exists for this student
                                    if f'ref{ref_num}' not in student_data[grade_student_id]:
                                        # Process grade data for this student (no reflection data)
                                        self._process_student_reflection_data(grade_student_id, ref_num, csv_path, '', '',
                                                                            student_lookup, grades_cache, emotion_value_map, student_data)
                            print(f"DEBUG: Found {valid_grades_count} students with valid grades in ref{ref_num}")
                        else:
                            print(f"WARNING: Grades file for ref{ref_num} missing required columns: {list(grades_df.columns)}")
                    except Exception as e:
                        print(f"Warning: Could not process grades file {grades_file}: {e}")
                else:
                    print(f"WARNING: No grades file found for reflection {ref_num} in {dir_path} or {os.path.join(dir_path, 'results')}")

        # Create CSV data
        csv_data = []
        reflection_numbers = sorted([ref_num for ref_num, _ in reflection_files])

        # Create header
        header = ['Student_ID']
        for ref_num in reflection_numbers:
            header.extend([
                f'Ref{ref_num}_Grade',
                f'Ref{ref_num}_Grade_Trend',
                f'Ref{ref_num}_Passing_Status',
                f'Ref{ref_num}_Emotions',
                f'Ref{ref_num}_Emotion_Sentiment',
                f'Ref{ref_num}_Emotion_Change',
                f'Ref{ref_num}_Topics',
                f'Ref{ref_num}_Extracted_Topics',
                f'Ref{ref_num}_Completed_Quizzes'
            ])

        # Add data rows
        for student_id in sorted(student_data.keys()):
            row = [student_id]
            for ref_num in reflection_numbers:
                ref_data = student_data[student_id].get(f'ref{ref_num}', {})
                row.extend([
                    ref_data.get('grade', ''),
                    ref_data.get('grade_trend', ''),
                    ref_data.get('passing_status', ''),
                    ref_data.get('emotions', ''),
                    ref_data.get('emotion_sentiment', ''),
                    ref_data.get('emotion_change', ''),
                    ref_data.get('topics', ''),
                    ref_data.get('extracted_topics', ''),
                    ref_data.get('completed_quizzes', '')
                ])
            csv_data.append(row)

        # Write CSV file
        csv_filename = f"{course.course_name}_student_emotions_topics_over_time.csv"
        csv_path = os.path.join(output_dir, csv_filename)

        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            writer.writerows(csv_data)

        print(f"CSV exported successfully to: {csv_path}")
        return csv_path

    def _build_grade_chart_from_csv(self, course, csv_path):
        """
        Build the Average Grade Over Time chart using data from individual grade files.
        This ensures accurate counts for each reflection period.
        """
        # Find all available reflection files to get the grade files
        reflection_dir = os.path.join("application", "model", "reflections", course.course_name)
        reflection_subdirs = [d for d in os.listdir(reflection_dir) if d.startswith('ref') and os.path.isdir(os.path.join(reflection_dir, d))]
        reflection_files = []
        for subdir in reflection_subdirs:
            try:
                ref_num = int(subdir.replace('ref', ''))
                candidate_csv = os.path.join(reflection_dir, subdir, f"{course.course_name}_ref{ref_num}.csv")
                if os.path.exists(candidate_csv):
                    reflection_files.append((ref_num, candidate_csv))
            except Exception:
                continue
        reflection_files = sorted(reflection_files, key=lambda x: x[0])

        if not reflection_files:
            return '<div style="color:red;">No reflection files found.</div>'

        # Calculate average grades from individual grade files
        avg_grade_data = []

        for ref_num, reflection_path in reflection_files:
            # Find the corresponding grade file
            grades_path = os.path.join(os.path.dirname(reflection_path), 'results', f'{course.course_name}_grades_ref{ref_num}.csv')
            if not os.path.exists(grades_path):
                grades_path = os.path.join(os.path.dirname(reflection_path), f'{course.course_name}_grades_ref{ref_num}.csv')

            if os.path.exists(grades_path):
                try:
                    grades_df = pd.read_csv(grades_path)
                    print(f"DEBUG CHART: Processing grade file for Reflection {ref_num}: {grades_path}")
                    print(f"DEBUG CHART: Grade file has {len(grades_df)} rows")

                    if 'ID' in grades_df.columns and 'Current Score' in grades_df.columns:
                        # Remove rows with empty IDs
                        grades_df = grades_df[grades_df['ID'].notna() & (grades_df['ID'].astype(str).str.strip() != '')]

                        # Filter out 'Student, Test' from ID or Student columns
                        mask = ~grades_df['ID'].astype(str).str.strip().str.lower().eq('student, test')
                        if 'Student' in grades_df.columns:
                            mask &= ~grades_df['Student'].astype(str).str.strip().str.lower().eq('student, test')
                        grades_df = grades_df[mask]

                        # Use only unique, non-empty IDs
                        grades_df = grades_df.drop_duplicates(subset=['ID'])

                        # Convert grades to numeric, excluding invalid values
                        all_grades_raw = grades_df['Current Score'].replace(['-', '', 'N/A', 'n/a'], pd.NA)
                        grades = pd.to_numeric(all_grades_raw, errors='coerce').dropna()

                        print(f"DEBUG CHART: Reflection {ref_num} - Total students in grade file: {len(grades_df)}")
                        print(f"DEBUG CHART: Reflection {ref_num} - Students with valid grades: {len(grades)}")

                        if not grades.empty:
                            avg_grade = grades.mean()
                            count = len(grades)

                            avg_grade_data.append({
                                'Reflection': ref_num,
                                'AverageGrade': round(avg_grade, 2),
                                'Count': count
                            })
                            print(f"DEBUG CHART: Added data point for ref{ref_num}: avg={avg_grade:.2f}, count={count}")
                        else:
                            print(f"WARNING: No valid grades found for Reflection {ref_num}")
                    else:
                        print(f"WARNING: Grade file for Reflection {ref_num} missing required columns")
                except Exception as e:
                    print(f"ERROR: Could not process grade file for Reflection {ref_num}: {e}")
            else:
                print(f"WARNING: No grade file found for Reflection {ref_num}")

        # Generate the chart HTML
        if avg_grade_data:
            # Check for data quality issues
            data_warnings = []
            for data_point in avg_grade_data:
                if data_point['Count'] < 5:  # Arbitrary threshold for "low data"
                    data_warnings.append(f"Reflection {data_point['Reflection']} has only {data_point['Count']} valid grades")

            # Add warning message if there are data quality issues
            warning_html = ""
            if data_warnings:
                warning_html = f'''
                <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin-bottom: 15px; border-radius: 5px;">
                    <strong>⚠️ Data Quality Notice:</strong><br>
                    {" • ".join(data_warnings)}<br>
                    <small>Low grade counts may indicate incomplete data or missing grade files for those reflections.</small>
                </div>
                '''

            # Simplified explanation about the chart
            chart_info_html = '''
            <div style="background-color: #e3f2fd; border: 1px solid #90caf9; padding: 10px; margin-bottom: 15px; border-radius: 5px;">
                <strong>📊 Chart Information:</strong><br>
                • Shows average grades for students with valid grade data in each reflection period<br>
                • The 'n' value for each data point represents the number of students with valid grades for that specific reflection<br>
                • Data is extracted directly from individual Canvas gradebook exports for each reflection period<br>
                • <em>Note: Student counts may vary between reflections due to enrollment changes, missing data, or different participation rates</em><br>
                <small>Grade data is extracted from Canvas gradebook exports for each reflection period.</small>
            </div>
            '''

            avg_grade_json = json.dumps(avg_grade_data)

            chart_html = warning_html + chart_info_html + '''<div id="simple-grade-chart-container" style="margin-bottom:32px;"></div>'''
            chart_html += '''<div id="simple-grade-data" style="display:none;">''' + avg_grade_json + '''</div>'''
            chart_html += '''
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script>
            function renderSimpleGradeChart() {
                var mainData = JSON.parse(document.getElementById('simple-grade-data').textContent);

                // Main average grade trace
                var x = mainData.map(d => d.Reflection);
                var y = mainData.map(d => d.AverageGrade);
                var count = mainData.map(d => d.Count);
                var text = mainData.map((d, i) => `Avg: ${d.AverageGrade} (n=${d.Count})`);
                var traces = [{
                    x: x,
                    y: y,
                    text: text,
                    customdata: count,
                    mode: 'lines+markers+text',
                    name: 'Average Grade (All Students)',
                    textposition: 'top right',
                    textfont: {size: 11},
                    marker: {size: 8},
                    line: {width: 2, color: '#1976d2'},
                    hovertemplate: 'Reflection: %{x}<br>Average Grade: %{y:.2f}<br>Number of Students: %{customdata}<extra></extra>'
                }];

                var layout = {
                    title: 'Average Grade Over Time',
                    xaxis: {title: 'Reflection', tickmode: 'linear', dtick: 1},
                    yaxis: {
                        title: 'Average Grade',
                        // Dynamic range based on data with padding for better visibility
                        autorange: false,
                        range: function() {
                            if (y.length > 0) {
                                var minGrade = Math.min(...y);
                                var maxGrade = Math.max(...y);
                                var padding = (maxGrade - minGrade) * 0.1; // 10% padding
                                return [Math.max(0, minGrade - padding), Math.min(100, maxGrade + padding)];
                            }
                            return [0, 100];
                        }()
                    },
                    margin: {t: 60, b: 40}
                };
                Plotly.newPlot('simple-grade-chart-container', traces, layout, {responsive: true});
            }
            document.addEventListener('DOMContentLoaded', renderSimpleGradeChart);
            </script>
            '''

            return chart_html
        else:
            return '<div style="color:red;">No valid grade data found in any reflection period.</div>'

    def _process_student_reflection_data(self, student_id, ref_num, csv_path, emotions, topics,
                                       student_lookup, grades_cache, emotion_value_map, student_data):
        """Helper method to process student reflection and grade data"""
        # Get grade data
        grade = "-"
        grade_trend = ""
        passing_status = ""

        student_obj = student_lookup.get(student_id)
        grades_dict = None
        grades_df = None

        # Debug: Print what we're looking for
        if ref_num == 4 and student_id.endswith('@'):  # Only debug for Reflection 4 and email students
            print(f"DEBUG: Looking for grade data for student {student_id} in Reflection {ref_num}")

        # Try to get from Student object
        if student_obj and ref_num in student_obj.reflection_data:
            grades_dict = student_obj.reflection_data[ref_num].get('grades')
            if grades_dict and 'Current Score' in grades_dict:
                grade = grades_dict['Current Score']
                if ref_num == 4 and student_id.endswith('@'):
                    print(f"DEBUG: Found grade from Student object: {grade}")

        # If not found, try grades file
        if grade == "-":
            grades_file = None
            dir_path = os.path.dirname(csv_path)

            # Debug: List all files in directory for Reflection 4
            if ref_num == 4 and student_id.endswith('@'):
                print(f"DEBUG: Looking in directory: {dir_path}")
                print(f"DEBUG: Files in directory: {os.listdir(dir_path) if os.path.exists(dir_path) else 'Directory not found'}")

            # Look for grades file - try both patterns for better compatibility
            for fname in os.listdir(dir_path):
                if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                    grades_file = os.path.join(dir_path, fname)
                    if ref_num == 4 and student_id.endswith('@'):
                        print(f"DEBUG: Found grades file: {grades_file}")
                    break

            # If not found in main directory, try results subdirectory
            if not grades_file:
                results_dir = os.path.join(dir_path, 'results')
                if os.path.exists(results_dir):
                    for fname in os.listdir(results_dir):
                        if fname.endswith(f'_grades_ref{ref_num}.csv') or fname.endswith(f'grades_ref{ref_num}.csv'):
                            grades_file = os.path.join(results_dir, fname)
                            if ref_num == 4 and student_id.endswith('@'):
                                print(f"DEBUG: Found grades file in results: {grades_file}")
                            break

            if grades_file:
                if grades_file not in grades_cache:
                    try:
                        grades_cache[grades_file] = pd.read_csv(grades_file)
                        if ref_num == 4 and student_id.endswith('@'):
                            print(f"DEBUG: Loaded grades file with columns: {list(grades_cache[grades_file].columns)}")
                    except Exception as e:
                        grades_cache[grades_file] = None
                        if ref_num == 4 and student_id.endswith('@'):
                            print(f"DEBUG: Error loading grades file: {e}")
                grades_df = grades_cache[grades_file]

                if grades_df is not None and 'ID' in grades_df.columns and 'Current Score' in grades_df.columns:
                    # Try multiple matching strategies for better compatibility
                    row_match = pd.DataFrame()

                    # Strategy 1: Exact match (case-insensitive)
                    row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]

                    # Strategy 2: If email, try matching with SIS Login ID column
                    if row_match.empty and '@' in student_id and 'SIS Login ID' in grades_df.columns:
                        sis_login = student_id.split('@')[0]  # Extract username part
                        row_match = grades_df[grades_df['SIS Login ID'].astype(str).str.strip().str.lower() == sis_login.lower()]
                        if not row_match.empty:
                            print(f"DEBUG: Found match using SIS Login ID for {student_id}")

                    # Strategy 3: If numeric ID from reflection, try to find partial match in longer grade IDs
                    if row_match.empty and student_id.isdigit():
                        # Try to find a grade ID that ends with or contains this number
                        for idx, grade_id in enumerate(grades_df['ID']):
                            grade_id_str = str(grade_id).strip()
                            if grade_id_str.endswith(student_id) or student_id in grade_id_str:
                                row_match = grades_df.iloc[[idx]]
                                print(f"DEBUG: Found partial match: reflection ID '{student_id}' matched with grade ID '{grade_id_str}'")
                                break

                    # Strategy 4: Legacy 4-digit matching (for backwards compatibility)
                    if row_match.empty and student_id.isdigit() and len(student_id) == 4:
                        row_match = grades_df[grades_df['ID'].astype(str).str.strip().str.startswith(student_id)]

                    if not row_match.empty:
                        grade_val = row_match.iloc[0]['Current Score']
                        if pd.notna(grade_val) and str(grade_val).strip() not in ['(read only)', 'N/A', 'n/a', '-', '']:
                            grade = grade_val
                            if ref_num == 4 and student_id.endswith('@'):
                                print(f"DEBUG: Found grade from grades file: {grade}")
                    else:
                        if ref_num == 4 and student_id.endswith('@'):
                            print(f"DEBUG: No matching student found in grades file for {student_id}")
                            print(f"DEBUG: Sample grade file IDs: {grades_df['ID'].head(5).tolist()}")
                else:
                    if ref_num == 4 and student_id.endswith('@'):
                        print(f"DEBUG: Grades file missing required columns or failed to load")

        # Final debug output
        if ref_num == 4 and student_id.endswith('@'):
            print(f"DEBUG: Final grade for {student_id} in Reflection {ref_num}: {grade}")

        # Calculate grade trend and passing status
        try:
            grade_val_float = float(grade)
            if grade_val_float >= 70:
                passing_status = 'Passing'
            else:
                passing_status = 'Fail'

            # Calculate trend if previous grade exists
            prev_ref_data = student_data[student_id].get(f'ref{ref_num-1}')
            if prev_ref_data and prev_ref_data.get('grade_numeric'):
                prev_grade = float(prev_ref_data['grade_numeric'])
                if grade_val_float > prev_grade:
                    grade_trend = 'Increasing'
                elif grade_val_float < prev_grade:
                    grade_trend = 'Decreasing'
                else:
                    grade_trend = 'Constant'
            else:
                grade_trend = 'N/A'
        except:
            grade_val_float = None
            passing_status = ""
            grade_trend = ""

        # Get completed quizzes
        completed_quizzes = []
        if grades_dict:
            for col in grades_dict:
                if isinstance(col, str) and 'feedback quiz' in col.lower():
                    try:
                        score = float(grades_dict[col])
                        if score > 0:
                            quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(col)).strip()
                            if any(c.isalpha() for c in quiz_clean):
                                completed_quizzes.append(quiz_clean)
                    except Exception:
                        continue
        elif grades_df is not None and 'row_match' in locals() and not row_match.empty:
            for col in grades_df.columns:
                if isinstance(col, str) and 'feedback quiz' in col.lower():
                    try:
                        score = float(row_match.iloc[0][col])
                        if score > 0:
                            quiz_clean = re.sub(r'\s*\(\d+\)\s*$', '', str(col)).strip()
                            if any(c.isalpha() for c in quiz_clean):
                                completed_quizzes.append(quiz_clean)
                    except Exception:
                        continue

        # Get extracted topics from topic analysis (moved outside grade processing)
        extracted_topics = []

        # Extract course name from CSV path to build exploded CSV filename
        # CSV path format: .../course_name/ref{num}/course_name_ref{num}.csv
        dir_path = os.path.dirname(csv_path)
        path_parts = dir_path.split(os.sep)

        # Find course name from path - it should be the directory name that contains ref{num}
        course_name = None
        for i, part in enumerate(path_parts):
            # Check if this is a ref directory (ref followed by digits)
            if part.startswith('ref') and len(part) > 3 and part[3:].isdigit():
                # The course name is the previous directory
                if i > 0:
                    course_name = path_parts[i-1]
                break

        # Alternative method: extract course name from the CSV filename itself
        if not course_name:
            csv_filename = os.path.basename(csv_path)
            # Pattern: {course_name}_ref{num}.csv
            if '_ref' in csv_filename:
                course_name = csv_filename.split('_ref')[0]

        if course_name:
            topic_csv = os.path.join(dir_path, 'results', f'{course_name}_ref{ref_num}_exploded.csv')

            if os.path.exists(topic_csv):
                try:
                    topic_df = pd.read_csv(topic_csv)

                    # Try different matching strategies for topic data
                    topic_rows = pd.DataFrame()

                    # Strategy 1: Exact match (case-insensitive)
                    topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.lower() == student_id.lower()]

                    # Strategy 2: If email ID, try matching username part
                    if topic_rows.empty and '@' in student_id:
                        username = student_id.split('@')[0].lower()
                        topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.lower() == username]
                        if not topic_rows.empty:
                            print(f"DEBUG: Found topic match using username '{username}' for email '{student_id}'")

                    # Strategy 3: Legacy 4-digit matching
                    if topic_rows.empty and student_id.isdigit() and len(student_id) == 4:
                        topic_rows = topic_df[topic_df['ID'].astype(str).str.strip().str.startswith(student_id)]

                    if not topic_rows.empty:
                        topic_col = None
                        for col in topic_rows.columns:
                            if 'primary_labels_selected' in col.lower():
                                topic_col = col
                                break

                        if topic_col:
                            for topic_val in topic_rows[topic_col].dropna():
                                if topic_val and str(topic_val).strip():
                                    extracted_topics.extend([t.strip().lower() for t in str(topic_val).split(';') if t.strip()])
                            extracted_topics = list(set(extracted_topics))  # Remove duplicates

                except Exception as e:
                    print(f"ERROR: Failed to process topic CSV {topic_csv}: {e}")
        else:
            if '@' in student_id:
                print(f"WARNING: Could not extract course name from path: {dir_path}")

        # Process emotions
        emotion_value = 0
        emotion_sentiment = ''
        emotion_change = ''

        if emotions:
            emotion_lower = str(emotions).lower().strip()
            for emotion, value in emotion_value_map.items():
                if emotion in emotion_lower:
                    emotion_value = value
                    break

            if emotion_value >= 5:
                emotion_sentiment = 'Positive'
            elif emotion_value >= 4:
                emotion_sentiment = 'Neutral'
            elif emotion_value >= 1:
                emotion_sentiment = 'Negative'
            else:
                emotion_sentiment = ''

        # Calculate emotion change
        emotion_change = ""
        prev_ref_data = student_data[student_id].get(f'ref{ref_num-1}')
        if prev_ref_data and prev_ref_data.get('emotion_value') and emotion_value > 0:
            prev_emotion_value = prev_ref_data['emotion_value']
            if emotion_value > prev_emotion_value:
                emotion_change = 'Increasing'
            elif emotion_value < prev_emotion_value:
                emotion_change = 'Decreasing'
            else:
                emotion_change = 'Constant'
        else:
            emotion_change = 'N/A'

        student_data[student_id][f'ref{ref_num}'] = {
            'emotions': emotions,
            'emotion_sentiment': emotion_sentiment,
            'emotion_change': emotion_change,
            'emotion_value': emotion_value,
            'topics': topics,
            'extracted_topics': '; '.join(extracted_topics) if extracted_topics else '',
            'grade': grade,
            'grade_numeric': grade_val_float,
            'grade_trend': grade_trend,
            'passing_status': passing_status,
            'completed_quizzes': '; '.join(completed_quizzes) if completed_quizzes else ''
        }

    def diagnose_grade_data_issues(self, reflection_files, course):
        """
        Diagnostic function to help identify issues with grade data processing.
        This will check file structure, naming patterns, and data contents.
        """
        print("\n" + "="*60)
        print("GRADE DATA DIAGNOSTIC REPORT")
        print("="*60)

        for ref_num, csv_path in reflection_files:
            print(f"\n--- REFLECTION {ref_num} ---")
            print(f"Reflection file: {csv_path}")
            print(f"Reflection file exists: {os.path.exists(csv_path)}")

            if not os.path.exists(csv_path):
                print("❌ Cannot proceed - reflection file missing")
                continue

            # Check directory structure
            dir_path = os.path.dirname(csv_path)
            print(f"Directory: {dir_path}")

            # List all files in directory
            all_files = os.listdir(dir_path) if os.path.exists(dir_path) else []
            csv_files = [f for f in all_files if f.endswith('.csv')]
            print(f"All CSV files in directory: {csv_files}")

            # Look for grade files using different patterns
            grade_files_found = []
            for fname in all_files:
                if 'grade' in fname.lower() and f'ref{ref_num}' in fname:
                    grade_files_found.append(fname)
                elif fname.endswith(f'_grades_ref{ref_num}.csv'):
                    grade_files_found.append(fname)
                elif fname.endswith(f'grades_ref{ref_num}.csv'):
                    grade_files_found.append(fname)

            print(f"Grade files found: {grade_files_found}")

            # Check results subdirectory
            results_dir = os.path.join(dir_path, 'results')
            if os.path.exists(results_dir):
                results_files = os.listdir(results_dir)
                results_csv = [f for f in results_files if f.endswith('.csv')]
                results_grades = [f for f in results_files if 'grade' in f.lower() and f'ref{ref_num}' in f]
                print(f"Results directory exists with CSV files: {results_csv}")
                print(f"Grade files in results: {results_grades}")
            else:
                print("Results directory does not exist")

            # Try to load and examine the grade file
            grades_file = None
            for fname in grade_files_found:
                potential_path = os.path.join(dir_path, fname)
                if os.path.exists(potential_path):
                    grades_file = potential_path
                    break

            if not grades_file and os.path.exists(results_dir):
                for fname in os.listdir(results_dir):
                    if 'grade' in fname.lower() and f'ref{ref_num}' in fname:
                        potential_path = os.path.join(results_dir, fname)
                        if os.path.exists(potential_path):
                            grades_file = potential_path
                            break

            if grades_file:
                print(f"✅ Using grade file: {grades_file}")
                try:
                    grades_df = pd.read_csv(grades_file)
                    print(f"Grade file shape: {grades_df.shape}")
                    print(f"Grade file columns: {list(grades_df.columns)}")

                    # Check for required columns
                    has_id = 'ID' in grades_df.columns
                    has_current_score = 'Current Score' in grades_df.columns
                    print(f"Has 'ID' column: {has_id}")
                    print(f"Has 'Current Score' column: {has_current_score}")

                    if has_id and has_current_score:
                        # Analyze the data
                        valid_ids = grades_df['ID'].dropna()
                        email_ids = valid_ids[valid_ids.astype(str).str.contains('@', na=False)]
                        numeric_ids = valid_ids[valid_ids.astype(str).str.match(r'^\d{4}$', na=False)]

                        print(f"Total students with IDs: {len(valid_ids)}")
                        print(f"Students with email IDs: {len(email_ids)}")
                        print(f"Students with 4-digit IDs: {len(numeric_ids)}")

                        # Check grade data
                        current_scores = grades_df['Current Score']
                        valid_scores = pd.to_numeric(current_scores, errors='coerce').dropna()
                        print(f"Total grade entries: {len(current_scores)}")
                        print(f"Valid numeric grades: {len(valid_scores)}")

                        if len(valid_scores) > 0:
                            print(f"Grade range: {valid_scores.min():.2f} - {valid_scores.max():.2f}")
                            print(f"Average grade: {valid_scores.mean():.2f}")
                            print(f"Sample grades: {valid_scores.head(5).tolist()}")
                        else:
                            print("❌ No valid numeric grades found!")
                            print(f"Sample grade values: {current_scores.head(10).tolist()}")
                    else:
                        print("❌ Missing required columns!")

                except Exception as e:
                    print(f"❌ Error reading grade file: {e}")
            else:
                print("❌ No grade file found for this reflection")

        print("\n" + "="*60)
        print("END DIAGNOSTIC REPORT")
        print("="*60 + "\n")

    def calculate_matching_students_count(self, course: Course, reflection_files: List[Tuple[int, str]]) -> int:
        """
        Calculate the number of students who can be matched between their MOST RECENT reflection and grade data.

        A student matches if:
        1. They submitted the most recent reflection with an email ID (contains '@')
        2. The username part (before '@') matches a 'SIS Login ID' in the most recent grade file
        3. They have valid grade data in the most recent grade file

        Args:
            course: Course object
            reflection_files: List of (reflection_number, file_path) tuples

        Returns:
            int: Number of students with both recent reflection and recent grade data
        """
        if not reflection_files:
            return 0

        # Find the most recent reflection
        most_recent_ref = max(reflection_files, key=lambda x: x[0])
        ref_num, reflection_path = most_recent_ref

        print(f"DEBUG: Calculating matching students for most recent reflection: {ref_num}")

        if not os.path.exists(reflection_path):
            print(f"DEBUG: Most recent reflection file not found: {reflection_path}")
            return 0

        try:
            # Read most recent reflection file
            reflection_df = pd.read_csv(reflection_path)
            if 'ID' not in reflection_df.columns:
                print(f"DEBUG: No 'ID' column in reflection file")
                return 0

            # Find corresponding most recent grade file
            grades_path = os.path.join(os.path.dirname(reflection_path), 'results', f'{course.course_name}_grades_ref{ref_num}.csv')
            if not os.path.exists(grades_path):
                grades_path = os.path.join(os.path.dirname(reflection_path), f'{course.course_name}_grades_ref{ref_num}.csv')

            if not os.path.exists(grades_path):
                print(f"DEBUG: Most recent grade file not found: {grades_path}")
                return 0

            # Read most recent grade file
            grades_df = pd.read_csv(grades_path)
            if 'SIS Login ID' not in grades_df.columns:
                print(f"DEBUG: No 'SIS Login ID' column in grade file")
                return 0

            # Create mapping of SIS Login IDs to check for valid grades
            valid_sis_students = {}
            for _, grade_row in grades_df.iterrows():
                sis_id = str(grade_row.get('SIS Login ID', '')).strip().lower()
                current_score = grade_row.get('Current Score', '')

                # Only include students with valid grade data
                if sis_id and pd.notna(current_score) and str(current_score).strip() not in ['-', '', 'N/A', 'n/a', '(read only)']:
                    try:
                        # Verify it's a numeric grade
                        float(current_score)
                        valid_sis_students[sis_id] = current_score
                    except (ValueError, TypeError):
                        pass  # Skip non-numeric grades

            print(f"DEBUG: Found {len(valid_sis_students)} students with valid grades in most recent grade file")

            # Count students who submitted the most recent reflection AND have valid grades
            matched_students = set()

            for _, row in reflection_df.iterrows():
                student_id = row.get('ID', '')
                if pd.isna(student_id):
                    continue

                student_id = str(student_id).strip()

                # Only process email IDs (must contain '@')
                if '@' in student_id:
                    # Extract username part (before '@')
                    username = student_id.split('@')[0].strip().lower()

                    # Check if this username has valid grade data
                    if username in valid_sis_students:
                        matched_students.add(student_id)
                        print(f"DEBUG: Matched student {student_id} (username: {username}) with valid grade: {valid_sis_students[username]}")

            matching_count = len(matched_students)
            print(f"DEBUG: Total students with BOTH most recent reflection AND valid grade data: {matching_count}")
            return matching_count

        except Exception as e:
            print(f"Error processing most recent reflection matching: {e}")
            return 0

    def _ensure_correct_total_students_count(self, course, reflection_files):
        """
        Ensure the total students count is set correctly from the most recent reflection's grade file.
        This ensures consistency across all parts of the application.
        """
        if not reflection_files:
            return

        # Find the most recent reflection
        most_recent_ref = max(reflection_files, key=lambda x: x[0])
        ref_num, reflection_path = most_recent_ref

        # Find the corresponding grade file
        grades_path = os.path.join(os.path.dirname(reflection_path), 'results', f'{course.course_name}_grades_ref{ref_num}.csv')
        if not os.path.exists(grades_path):
            grades_path = os.path.join(os.path.dirname(reflection_path), f'{course.course_name}_grades_ref{ref_num}.csv')

        if os.path.exists(grades_path):
            try:
                grades_df = pd.read_csv(grades_path)
                if 'ID' in grades_df.columns:
                    # Remove rows with empty IDs
                    grades_df = grades_df[grades_df['ID'].notna() & (grades_df['ID'].astype(str).str.strip() != '')]
                    # Filter out 'Student, Test' from ID or Student columns
                    mask = ~grades_df['ID'].astype(str).str.strip().str.lower().eq('student, test')
                    if 'Student' in grades_df.columns:
                        mask &= ~grades_df['Student'].astype(str).str.strip().str.lower().eq('student, test')
                    grades_df = grades_df[mask]
                    grades_df = grades_df.drop_duplicates(subset=['ID'])

                    # Set the total students count from the most recent grade file
                    total_students_in_course = grades_df['ID'].nunique()
                    course.set_filtered_total_students(total_students_in_course)
                    print(f"DEBUG: Set total students count to {total_students_in_course} from most recent grade file (Reflection {ref_num})")
                else:
                    print(f"WARNING: Grade file for Reflection {ref_num} missing 'ID' column")
            except Exception as e:
                print(f"ERROR: Could not process grade file for total students count: {e}")
        else:
            print(f"WARNING: No grade file found for Reflection {ref_num}")

    def _set_total_students_from_latest_grade_file(self, course, reflection_files):
        """
        Set the total students count from the most recent reflection's grade file.
        """
        if not reflection_files:
            return

        # Find the most recent reflection
        most_recent_ref = max(reflection_files, key=lambda x: x[0])
        ref_num, reflection_path = most_recent_ref

        # Find the corresponding grade file
        grades_path = os.path.join(os.path.dirname(reflection_path), 'results', f'{course.course_name}_grades_ref{ref_num}.csv')
        if not os.path.exists(grades_path):
            grades_path = os.path.join(os.path.dirname(reflection_path), f'{course.course_name}_grades_ref{ref_num}.csv')

        if os.path.exists(grades_path):
            try:
                grades_df = pd.read_csv(grades_path)
                if 'ID' in grades_df.columns:
                    # Remove rows with empty IDs
                    grades_df = grades_df[grades_df['ID'].notna() & (grades_df['ID'].astype(str).str.strip() != '')]
                    # Filter out 'Student, Test' from ID or Student columns
                    mask = ~grades_df['ID'].astype(str).str.strip().str.lower().eq('student, test')
                    if 'Student' in grades_df.columns:
                        mask &= ~grades_df['Student'].astype(str).str.strip().str.lower().eq('student, test')
                    grades_df = grades_df[mask]
                    grades_df = grades_df.drop_duplicates(subset=['ID'])

                    # Set the total students count from the most recent grade file
                    total_students_in_course = grades_df['ID'].nunique()
                    course.set_filtered_total_students(total_students_in_course)
                    print(f"DEBUG: Set total students count to {total_students_in_course} from most recent grade file (Reflection {ref_num})")
                else:
                    print(f"WARNING: Grade file for Reflection {ref_num} missing 'ID' column")
            except Exception as e:
                print(f"ERROR: Could not process grade file for total students count: {e}")
        else:
            print(f"WARNING: No grade file found for Reflection {ref_num}")

    def _create_anonymized_students(self, original_students):
        """
        Create anonymized versions of students by masking personal information.

        Args:
            original_students: Dictionary of original Student objects

        Returns:
            List of anonymized Student objects with masked names, emails, and sections
        """
        from application.model.models.student import Student
        import string

        anonymized_students = []
        student_counter = 0

        # Create a mapping of original students to anonymized versions
        for original_student in original_students.values():
            student_counter += 1

            # Create anonymous identifier (Student A, Student B, etc.)
            # Handle cases where we have more than 26 students
            if student_counter <= 26:
                anonymous_name = f"Student {string.ascii_uppercase[student_counter - 1]}"
                email_prefix = string.ascii_uppercase[student_counter - 1]
            else:
                # For more than 26 students, use Student AA, Student AB, etc.
                first_letter = string.ascii_uppercase[(student_counter - 1) // 26 - 1]
                second_letter = string.ascii_uppercase[(student_counter - 1) % 26]
                anonymous_name = f"Student {first_letter}{second_letter}"
                email_prefix = f"{first_letter}{second_letter}"

            # Create masked email using the assigned alphabet letter(s)
            masked_email = f"{email_prefix}***@domain.edu"

            # Create anonymized student object
            anonymized_student = Student(
                name=anonymous_name,
                email=masked_email,
                course=original_student.course
            )

            # Copy all reflection data (this contains the analytical insights)
            anonymized_student.reflection_data = original_student.reflection_data.copy()

            # Remove section information for privacy
            anonymized_student.section = None

            # Store reference to original student for internal use (for debugging)
            anonymized_student._original_student = original_student

            anonymized_students.append(anonymized_student)

        print(f"DEBUG: Created {len(anonymized_students)} anonymized students")
        if anonymized_students:
            print(f"DEBUG: Example anonymized student: {anonymized_students[0].name} ({anonymized_students[0].email})")

        return anonymized_students
