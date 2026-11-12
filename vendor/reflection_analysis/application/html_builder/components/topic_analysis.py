from pathlib import Path
import pandas as pd
import plotly.express as px
from application.html_builder.templates.template_manager import TemplateManager
import json

class TopicAnalysisBuilder:
    def __init__(self, data_path=None):
        self.data_path = Path(data_path) if data_path is not None else Path(__file__).parent.parent.parent / "model" / "reflections"
        self.template_manager = TemplateManager()
        self.template = self.template_manager.load_template('topic_analysis')

    def load_reflection_data(self, course_name: str, ref_num: int, anonymized: bool = False):
        """Load all reflection analysis files for a course/reflection period"""
        base_path = self.data_path / course_name / f"ref{ref_num}" / "results"
        print(f"Looking for files in: {base_path}")

        try:
            # Load exploded data and plot data
            exploded_df = pd.read_csv(base_path / f"{course_name}_ref{ref_num}_exploded.csv")
            plot_df = pd.read_csv(base_path / f"{course_name}_ref{ref_num}_plot_data.csv")

            # Get all column names from exploded data
            columns = exploded_df.columns.tolist()
            print("Columns in exploded data:", columns)

            # Detect section column(s)
            section_columns = [col for col in columns if isinstance(col, str) and 'section' in col.lower()]
            section_col = section_columns[0] if section_columns else None
            if section_col:
                print(f"Section column detected: {section_col}")
                print(f"Unique section values: {exploded_df[section_col].unique()}")
            # Specify columns to show in main table
            main_columns = ['ID']
            if section_col:
                main_columns.append(section_col)
            main_columns += ['primary_labels_selected', 'resolution_primary_labels', 'urgency', 'reflection_summary', 'instructor_suggestions']
            # Only keep columns that exist in the data
            visible_columns = [col for col in main_columns if col in columns]
            # If anonymized, remove ID column
            if anonymized and 'ID' in visible_columns:
                visible_columns.remove('ID')
            thead = "<thead>\n<tr>"
            for idx, col in enumerate(visible_columns):
                if len(str(col)) > 30:
                    short_label = f"Q{idx+1}"
                    thead += f'<th><span class="short-label">{short_label}</span> <button class="expand-question" onclick="toggleQuestion(this)">+</button><span class="full-question" style="display:none;">{col}</span></th>'
                else:
                    thead += f'<th>{col}</th>'
            thead += '<th>Details</th>'
            thead += "</tr>\n</thead>"

            # Build a unique id for each row for modal targeting
            tbody = "<tbody>\n"
            modal_sections = ''
            for row_idx, row in enumerate(exploded_df.iterrows()):
                idx, row = row_idx, row[1]
                row_id = f'ref-details-{idx}'

                # Debug: Check ID consistency
                original_id = row.get('ID', '')
                print(f"DEBUG TABLE: Row {idx} - Original ID from exploded CSV: '{original_id}' (type: {type(original_id)})")

                tbody += "<tr>"
                for col in visible_columns:
                    cell_value = row.get(col, "")
                    if col == 'ID':
                        print(f"DEBUG TABLE: Displaying ID in table cell: '{cell_value}'")
                        # Format ID display based on type for better visual distinction
                        if '@' in str(cell_value):
                            # Email format
                            formatted_value = f'<span class="email-id" style="color:#2196F3;font-weight:500;" title="Email ID">{cell_value}</span>'
                        elif str(cell_value).isdigit() and len(str(cell_value)) == 4:
                            # 4-digit format
                            formatted_value = f'<span class="digit-id" style="color:#FF9800;font-weight:500;" title="4-digit ID">{cell_value}</span>'
                        elif str(cell_value).isdigit() and len(str(cell_value)) <= 3:
                            # 2-3 digit format
                            formatted_value = f'<span class="short-id" style="color:#9C27B0;font-weight:500;" title="Short numeric ID">{cell_value}</span>'
                        else:
                            # Other format (like ID-XX)
                            formatted_value = f'<span class="other-id" style="color:#607D8B;font-weight:500;" title="Generated ID">{cell_value}</span>'
                        tbody += f'<td>{formatted_value}</td>'
                    else:
                        tbody += f'<td>{cell_value}</td>'
                tbody += f'<td><button class="expand-reflection" onclick="showReflectionModal(\'{row_id}\')">Show Full Reflection</button></td>'
                tbody += "</tr>\n"

                # Build modal/section for Q/A pairs (all columns except ID), as a table
                qa_table = '<table class="reflection-qa-table" style="width:100%;background:#f8f9fa;border-radius:6px;"><thead><tr><th style="width:35%;text-align:left;">Field</th><th style="text-align:left;">Response</th></tr></thead><tbody>'
                for col in columns:
                    if col != 'ID':
                        qa_table += f'<tr><td style="font-weight:600;">{col}</td><td>{row.get(col, "")}</td></tr>'
                    # Omit ID row in anonymized mode
                    # else:
                    #     id_value = row.get(col, "")
                    #     print(f"DEBUG MODAL: ID in modal for row {idx}: '{id_value}' (should match table)")
                    #     qa_table += f'<tr><td style="font-weight:600;">{col}</td><td>{id_value}</td></tr>'
                qa_table += '</tbody></table>'
                # Modal/section hidden by default
                modal_sections += f'''<div id="{row_id}" class="reflection-modal" style="display:none;position:fixed;top:10vh;left:50%;transform:translateX(-50%);background:#fff;z-index:1000;padding:32px 24px;border-radius:10px;box-shadow:0 4px 24px rgba(0,0,0,0.18);max-width:90vw;max-height:80vh;overflow:auto;">
  <button onclick="closeReflectionModal('{row_id}')" style="position:absolute;top:12px;right:18px;font-size:1.5em;background:none;border:none;cursor:pointer;">&times;</button>
  <h3>Full Reflection Details</h3>
  <div style="background:#e8f4f8;padding:12px;margin-bottom:16px;border-radius:6px;border-left:4px solid #2196F3;">
    {'<strong>Student ID:</strong> ' + str(original_id) + '<br>' if not anonymized else ''}
    <strong>Row:</strong> {idx + 1} of {len(exploded_df)}<br>
    <strong>Analysis:</strong> {row.get('primary_labels_selected', 'N/A')} → {row.get('resolution_primary_labels', 'N/A')}
  </div>
  {qa_table}
</div>\n'''
            tbody += "</tbody>"
            # Add JS for modal logic
            modal_js = '''
<script>
function showReflectionModal(id) {
  document.getElementById(id).style.display = 'block';
  document.body.style.overflow = 'hidden';
}
function closeReflectionModal(id) {
  document.getElementById(id).style.display = 'none';
  document.body.style.overflow = '';
}
</script>
'''
            return {
                'exploded_table': thead + '\n' + tbody,
                'modal_html': modal_sections + modal_js,
                'plot_data': plot_df
            }

        except Exception as e:
            print(f"Error loading reflection data: {e}")
            return {
                'exploded_table': '<thead><tr><th>Error</th></tr></thead><tbody><tr><td>No data available</td></tr></tbody>',
                'modal_html': '',
                'plot_data': pd.DataFrame()
            }

    def _get_empty_data(self):
        """Return empty data structure with appropriate HTML placeholders"""
        return {
            'counts': pd.DataFrame(),
            'exploded': pd.DataFrame(),
            'label_counts': pd.DataFrame(),
            'plot_data': pd.DataFrame(),
            'responses': pd.DataFrame(),
            'exploded_table': '<tr><td colspan="7" class="no-data">No analysis data available</td></tr>',
            'label_counts_html': '<div class="no-data">No label counts available</div>',
            'filter_options': {
                'urgency': '',
                'topics': '',
                'resolution': ''
            }
        }

    def _add_percentage_column(self, plot_data, total_students):
        """Add a percentage column to the plot data DataFrame based on total students."""
        if total_students <= 0:
            plot_data['PercentageOfTotal'] = 0.0
        else:
            plot_data['PercentageOfTotal'] = (plot_data['Count'] / total_students * 100).round(1)
        return plot_data

    def create_topic_plot(self, plot_data, total_students, show='both', total_reflections_submitted=None, reflection_file_path=None):
        """Create topic distribution plot with numbers and percentages (percentages are of total students)."""
        if plot_data.empty:
            return None
        try:
            # If total_reflections_submitted is not provided, try to load from reflection_file_path
            if total_reflections_submitted is None and reflection_file_path is not None:
                try:
                    df = pd.read_csv(reflection_file_path)
                    if 'ID' in df.columns:
                        df = df[df['ID'].notna() & (df['ID'].astype(str).str.strip() != '')]
                        df = df[~df['ID'].astype(str).str.strip().str.lower().eq('student, test')]
                        total_reflections_submitted = df['ID'].nunique()
                    else:
                        total_reflections_submitted = len(df)
                except Exception as e:
                    print(f"Error loading reflection file for total_reflections_submitted: {e}")
                    total_reflections_submitted = 0
            # Define a more visually distinct color scheme
            color_map = {
                'resolved': '#00876c',      # Teal green
                'unresolved': '#e63946',    # Bright red
                'unspecified': '#fca311',   # Orange
                'no_challenge': '#457b9d',  # Steel blue
                'in_progress': '#8338ec',   # Purple
                'needs_review': '#ff006e',  # Pink
                'not_started': '#6c757d'    # Gray
            }
            # Clean up the data
            plot_data['Topic'] = plot_data['Topic'].str.replace('_', ' ').str.title()
            plot_data['Resolution Status'] = plot_data['Resolution Status'].str.lower()
            # Add percentage column based on total students
            plot_data = self._add_percentage_column(plot_data, total_students)
            # Choose text to display
            if show == 'count':
                text = plot_data['Count'].astype(str)
            elif show == 'percent':
                text = plot_data['PercentageOfTotal'].astype(str) + '%'
            else:  # both
                text = plot_data.apply(lambda row: f"{row['Count']} ({row['PercentageOfTotal']}%)", axis=1)
            print("[DEBUG] Bar text values:", list(text))
            print("[DEBUG] PercentageOfTotal column:", list(plot_data['PercentageOfTotal']))
            # Create stacked bar plot
            fig = px.bar(
                plot_data,
                x='Topic',
                y='Count',
                color='Resolution Status',
                title='Topic Distribution by Resolution Status',
                labels={
                    'Topic': 'Topic',
                    'Count': 'Number of Students',
                    'Resolution Status': 'Resolution Status'
                },
                height=600,
                color_discrete_map=color_map,
                text=text
            )
            # Update layout for better appearance
            fig.update_layout(
                title_x=0.5,
                title_font_size=24,
                barmode='stack',
                plot_bgcolor='white',
                paper_bgcolor='white',
                bargap=0.3,
                margin=dict(t=100, l=50, r=20, b=150),
                font=dict(
                    family="Arial, sans-serif",
                    size=14
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    bgcolor='rgba(255, 255, 255, 0.9)',
                    bordercolor='#dee2e6',
                    borderwidth=1,
                    font=dict(size=12)
                ),
                hoverlabel=dict(
                    bgcolor="white",
                    font_size=14,
                    font_family="Arial, sans-serif"
                ),
                showlegend=True
            )
            # Update axes
            fig.update_xaxes(
                tickangle=45,
                tickfont=dict(size=12),
                gridcolor='#f0f0f0',
                title_font=dict(size=16),
                showgrid=True,
                title_standoff=25
            )
            fig.update_yaxes(
                gridcolor='#f0f0f0',
                tickfont=dict(size=12),
                title_font=dict(size=16),
                showgrid=True,
                title_standoff=25
            )
            # Precompute total reflections for each topic
            topic_totals = plot_data.groupby('Topic')['Count'].sum().to_dict()
            # Add customdata for each bar: [topic_total, total_reflections_submitted]
            customdata = plot_data.apply(lambda row: [topic_totals.get(row['Topic'], 0), total_reflections_submitted], axis=1)
            fig.update_traces(
                textposition='auto',
                customdata=customdata,
                hovertemplate="<b>%{x}</b><br>Resolution Status: %{fullData.name}<br>Count: %{y}<br>Total in Topic: %{customdata[0]}<br>Total Reflections Submitted: %{customdata[1]}<extra></extra>"
            )
            return fig
        except Exception as e:
            print(f"Error creating topic plot: {e}")
            return None

    def build_analysis(self, course: object, ref_num: int) -> str:
        """Build topic analysis HTML. Uses course.get_total_reflections_submitted() for correct percentage calculation."""
        try:
            course_name = course.course_name
            # Determine if anonymized mode is enabled (attribute or fallback)
            anonymized = getattr(course, 'anonymized', False)
            data = self.load_reflection_data(course_name, ref_num, anonymized=anonymized)
            total_reflections_submitted = course.get_total_reflections_submitted()
            # Fallback if not set
            if not total_reflections_submitted:
                reflection_file_path = self.data_path / course_name / f"ref{ref_num}" / f"{course_name}_ref{ref_num}.csv"
                if reflection_file_path.exists():
                    try:
                        df = pd.read_csv(reflection_file_path)
                        if 'ID' in df.columns:
                            df = df[df['ID'].notna() & (df['ID'].astype(str).str.strip() != '')]
                            df = df[~df['ID'].astype(str).str.strip().str.lower().eq('student, test')]
                            total_reflections_submitted = df['ID'].nunique()
                        else:
                            total_reflections_submitted = len(df)
                    except Exception as e:
                        print(f"Error loading reflection file for total_reflections_submitted: {e}")
                        total_reflections_submitted = 0
                else:
                    total_reflections_submitted = 0
                course.set_total_reflections_submitted(total_reflections_submitted)

            # Use the same logic as Student Profiles tab - students with recent data
            # This counts students who submitted the most recent reflection AND have valid grade data
            students_with_recent_data = course.get_matching_students_count()

            # Fallback to the old logic if matching_students_count is not set
            if not students_with_recent_data:
                # Calculate number of students who shared their identities (old logic)
                num_students_with_id = 0
                reflection_file_path = self.data_path / course_name / f"ref{ref_num}" / f"{course_name}_ref{ref_num}.csv"
                if reflection_file_path.exists():
                    try:
                        df = pd.read_csv(reflection_file_path)
                        if 'ID' in df.columns:
                            df = df[df['ID'].notna() & (df['ID'].astype(str).str.strip() != '')]
                            df = df[~df['ID'].astype(str).str.strip().str.lower().eq('student, test')]
                            df = df[df['ID'].astype(str).str.contains('@')]
                            num_students_with_id = df['ID'].nunique()
                        else:
                            num_students_with_id = 0
                    except Exception as e:
                        print(f"Error loading reflection file for num_students_with_id: {e}")
                        num_students_with_id = 0
                students_with_recent_data = num_students_with_id
                course.set_num_students_with_email_id(num_students_with_id)

            plot = self.create_topic_plot(data['plot_data'], total_reflections_submitted, total_reflections_submitted=total_reflections_submitted)
            if plot:
                plot_html = plot.to_html(full_html=False, include_plotlyjs='cdn')
                print("\nPlot HTML generated:", plot_html[:200])
            else:
                plot_html = ''
                print("\nNo plot generated")
            context = {
                'plot_html': plot_html,
                'exploded_table': data['exploded_table'],
                'modal_html': data['modal_html'],
                'course_name': course_name,
                'ref_num': ref_num,
                'num_students_with_id': students_with_recent_data
            }
            return self.template_manager.render_topic_analysis(self.template, context)
        except Exception as e:
            print(f"Error building topic analysis: {e}")
            return f"<div>Error building topic analysis: {str(e)}</div>"
