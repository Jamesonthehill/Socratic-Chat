import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd


def _safe_read_csv(path: str) -> Optional[pd.DataFrame]:
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
    except Exception:
        pass
    return None


def _ai_disabled() -> bool:
    """Global gate to disable AI calls.
    Checks env vars and, if available, Streamlit session state.
    """
    try:
        # Environment variables take precedence
        flag1 = os.environ.get("ADAE_DISABLE_AI", "").strip().lower()
        flag2 = os.environ.get("DISABLE_AI_GENERATION", "").strip().lower()
        if flag1 in ("1", "true", "yes") or flag2 in ("1", "true", "yes"):
            print(f"DEBUG: AI disabled via env var (ADAE_DISABLE_AI={flag1}, DISABLE_AI_GENERATION={flag2})")
            return True
    except Exception:
        pass
    try:
        import streamlit as st  # type: ignore
        testing_mode = st.session_state.get("summ_testing_mode", False)
        print(f"DEBUG: summ_testing_mode = {testing_mode}")
        if bool(testing_mode):
            print("DEBUG: AI disabled via testing_mode checkbox")
            return True
    except Exception as e:
        print(f"DEBUG: Could not check streamlit session state: {e}")
    return False


def _summarize_with_gpt(system_instructions: str, content: str, *, model: str = "gpt-4o-mini", max_tokens: int = 800) -> Optional[str]:
    """Best-effort LLM call. If the OpenAI client/env is not available, return None."""
    # Global AI disable gate
    if _ai_disabled():
        print("DEBUG: AI is disabled via _ai_disabled()")
        return None

    # Check API key directly here
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        print(f"DEBUG: API key from env starts with: '{api_key[:15]}...'")
        print(f"DEBUG: API key length: {len(api_key)}")
    else:
        print("DEBUG: OPENAI_API_KEY environment variable is NOT SET")
        return None

    try:
        # Lazy import to avoid crashing when OPENAI_API_KEY is not set
        from application.controller.gpt_api import Model  # type: ignore
    except Exception as e:
        print(f"DEBUG: Failed to import Model: {e}")
        return None
    try:
        print(f"DEBUG: Calling GPT with model={model}")
        result = Model.prompt(system_instructions, content, model=model, max_tokens=max_tokens, json=False)
        print(f"DEBUG: GPT returned result of length {len(result) if result else 0}")
        return result
    except Exception as e:
        print(f"DEBUG: GPT call failed with error: {e}")
        return None


def _html_section(title: str, body_html: str) -> str:
    style = """
<style>
  .summary-section h2 { margin: 12px 0 8px 0; font-size: 1.4rem; }
  .summary-body { line-height: 1.5; font-size: 1rem; }
  .summary-body h1, .summary-body h2, .summary-body h3 { margin: 14px 0 8px 0; }
  .summary-body p { margin: 6px 0; }
  .summary-body ul { margin: 6px 0 10px 24px; }
  .summary-body li { margin: 3px 0; }
  .summary-body table { border-collapse: collapse; margin: 8px 0; }
  .summary-body table td, .summary-body table th { border: 1px solid #ddd; padding: 6px 8px; }
  .summary-body hr { margin: 12px 0; }
</style>
"""
    return f"""
{style}
<div class="summary-section">
  <h2>{title}</h2>
  <div class="summary-body">{body_html}</div>
  <hr/>
  <br/>
</div>
"""


def _truncate(text: str, max_chars: int = 20000) -> str:
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.6)
    tail = int(max_chars * 0.3)
    return text[:head] + "\n\n... [truncated for length] ...\n\n" + text[-tail:]


def _build_name_map(grades_df: Optional[pd.DataFrame]) -> Dict[str, str]:
    """Build a mapping of student email/ID -> display name from the grades CSV.

    Prefers an email-like ID from 'ID' when present; otherwise uses 'SIS Login ID' + '@charlotte.edu'.
    Returns lowercase keys for consistent lookup.
    """
    name_map: Dict[str, str] = {}
    try:
        if grades_df is None or grades_df.empty:
            return name_map
        # Determine columns
        id_col = None
        if "ID" in grades_df.columns:
            id_col = "ID"
        sis_col = "SIS Login ID" if "SIS Login ID" in grades_df.columns else None
        name_col = "Student" if "Student" in grades_df.columns else None
        for _, row in grades_df.iterrows():
            display = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else ""
            key: Optional[str] = None
            if id_col and pd.notna(row.get(id_col)):
                v = str(row[id_col]).strip()
                if v:
                    key = v if "@" in v else None
            if key is None and sis_col and pd.notna(row.get(sis_col)):
                u = str(row[sis_col]).strip().lower()
                if u:
                    key = f"{u}@charlotte.edu"
            if key:
                name_map[key.strip().lower()] = display or key
    except Exception:
        # Best-effort mapping only
        return name_map
    return name_map


@dataclass
class StudentFilter:
    min_grade: Optional[float] = None
    max_grade: Optional[float] = None
    unresolved_only: bool = False
    urgency_levels: Optional[List[str]] = None


class SummarizationService:
    """Generate instructor-focused summaries from existing reflection/analysis data.

    This service is intentionally light-weight and reuses existing artifacts:
    - Reflection CSV: {course}_{ref}.csv
    - Grades CSV: {course}_grades_{ref}.csv
    - Exploded topic results: results/{course}_{ref}_exploded.csv
    """

    def __init__(self, base_path: str = os.path.join("application", "model", "reflections")) -> None:
        self.base_path = base_path

    def _paths(self, course_name: str, reflection_folder: str) -> Dict[str, str]:
        ref_num = reflection_folder.replace("ref", "")
        folder_path = os.path.join(self.base_path, course_name, reflection_folder)
        results_path = os.path.join(folder_path, "results")
        return {
            "folder": folder_path,
            "results": results_path,
            "reflection_csv": os.path.join(folder_path, f"{course_name}_{reflection_folder}.csv"),
            "grades_csv": os.path.join(folder_path, f"{course_name}_grades_{reflection_folder}.csv"),
            "exploded_csv": os.path.join(results_path, f"{course_name}_{reflection_folder}_exploded.csv"),
            "counts_csv": os.path.join(results_path, f"{course_name}_{reflection_folder}_counts.csv"),
            "plot_csv": os.path.join(results_path, f"{course_name}_{reflection_folder}_plot_data.csv"),
        }

    def load_available_data(self, course_name: str, reflection_folder: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        paths = self._paths(course_name, reflection_folder)
        reflection_df = _safe_read_csv(paths["reflection_csv"])  # Raw reflections
        grades_df = _safe_read_csv(paths["grades_csv"])          # Gradebook
        exploded_df = _safe_read_csv(paths["exploded_csv"])      # Topic analysis results
        return reflection_df, grades_df, exploded_df

    # ---------------------------- High-level entrypoints ----------------------------
    def build_complete_summary_html(self, course_name: str, reflection_folder: str) -> str:
        reflection_df, grades_df, exploded_df = self.load_available_data(course_name, reflection_folder)
        name_map = _build_name_map(grades_df)

        # Aggregate key signals
        meta_bits: List[str] = []

        if reflection_df is not None and not reflection_df.empty:
            num_reflections = len(reflection_df)
            meta_bits.append(f"Total reflections: {num_reflections}")
            # Emotions column (case-insensitive prefix match used elsewhere)
            emotion_col = next((c for c in reflection_df.columns if isinstance(c, str) and c.strip().lower().startswith("how do you feel about the course so far?")), None)
            if emotion_col:
                emotions = reflection_df[emotion_col].dropna().astype(str)
                top_emotions = emotions.value_counts().head(10).to_dict()
                if top_emotions:
                    meta_bits.append("Top emotions: " + ", ".join(f"{k} ({v})" for k, v in top_emotions.items()))

        if exploded_df is not None and not exploded_df.empty:
            topic_counts = exploded_df["primary_labels_selected"].astype(str).value_counts().head(10).to_dict()
            if topic_counts:
                meta_bits.append("Top topics: " + ", ".join(f"{k} ({v})" for k, v in topic_counts.items()))
            unresolved = exploded_df[exploded_df["resolution_primary_labels"].astype(str).str.lower() == "unresolved"]
            meta_bits.append(f"Unresolved items: {len(unresolved)}")

        if grades_df is not None and not grades_df.empty:
            # Prefer Current Score if present
            grade_series = None
            if "Current Score" in grades_df.columns:
                grade_series = pd.to_numeric(grades_df["Current Score"], errors="coerce")
            elif "Current Grade" in grades_df.columns:
                grade_series = pd.to_numeric(grades_df["Current Grade"], errors="coerce")
            if grade_series is not None:
                grade_desc = grade_series.describe(percentiles=[0.25, 0.5, 0.75]).to_dict()
                meta_bits.append(
                    "Grade distribution (min/25%/50%/75%/max): "
                    + ", ".join(
                        [
                            f"{k}={round(v, 1)}"
                            for k, v in grade_desc.items()
                            if k in ("min", "25%", "50%", "75%", "max") and pd.notna(v)
                        ]
                    )
                )

        meta_text = "\n".join(meta_bits) if meta_bits else "No basic metrics available."

        # Build content for GPT
        content_parts: List[str] = []
        if exploded_df is not None and not exploded_df.empty:
            # Use reflection_summary and instructor_suggestions when available
            cols = [c for c in ["ID", "primary_labels_selected", "resolution_primary_labels", "urgency", "reflection_summary", "instructor_suggestions"] if c in exploded_df.columns]
            sample = exploded_df[cols].copy()
            if "ID" in sample.columns:
                sample["ID"] = sample["ID"].astype(str)
                # Add display name column when available
                try:
                    sample["StudentName"] = sample["ID"].astype(str).str.strip().str.lower().map(lambda k: name_map.get(k, ""))
                except Exception:
                    sample["StudentName"] = ""
            sample = sample.astype(str)
            content_parts.append(sample.to_csv(index=False))
        elif reflection_df is not None and not reflection_df.empty:
            content_parts.append(reflection_df.head(300).to_csv(index=False))
        content = _truncate("\n\n".join(content_parts) if content_parts else meta_text)

        system = (
            "You are an academic analytics assistant. Create an executive summary for the instructor. "
            "Summarize key themes, unresolved issues, emotions signals, and grade risks. Provide 5-8 actionable recommendations. "
            "When a particular student mentions a challenge or topic, name the student explicitly using available display names (avoid vague phrases like 'some students'). "
            "Be concise and structured with headings and bullet points."
        )

        gpt = _summarize_with_gpt(system, content)
        if gpt:
            return _html_section("Executive Summary", self._render_text_as_html(gpt))

        # Fallback (no API): render basic metrics
        fallback_html = """
        <ul>
          <li>{}</li>
        </ul>
        """.format("</li><li>".join(meta_bits) if meta_bits else "No metrics available.")
        return _html_section("Executive Summary", fallback_html)

    def _load_previous_grades_df(self, course_name: str, reflection_folder: str) -> Optional[pd.DataFrame]:
        """Load the previous reflection's grades CSV if available.

        Example mapping: ref2 -> ref1, ref3 -> ref2.
        """
        try:
            ref_num_str = reflection_folder.replace("ref", "").strip()
            ref_num = int(ref_num_str)
            if ref_num <= 1:
                return None
            prev_ref = f"ref{ref_num - 1}"
            prev_paths = self._paths(course_name, prev_ref)
            return _safe_read_csv(prev_paths["grades_csv"])  # type: ignore
        except Exception:
            return None

    def build_grade_decliners_html(self, course_name: str, reflection_folder: str) -> str:
        """Build a section that highlights students whose grades dropped vs the previous reflection,
        and show a short per-student reflection summary from the current analysis.

        Behavior:
        - Uses current reflection's grades CSV (Current Score/Current Grade)
        - Compares to previous reflection's grades CSV if available
        - Lists students where current - previous < 0, sorted by largest drop
        - For each, include a brief reflection/topic summary from the current exploded.csv if present
        """
        reflection_df, grades_df, exploded_df = self.load_available_data(course_name, reflection_folder)
        prev_grades_df = self._load_previous_grades_df(course_name, reflection_folder)

        # If we don't have current grades or previous grades, show a helpful message
        if grades_df is None or grades_df.empty or prev_grades_df is None or prev_grades_df.empty:
            return _html_section(
                "Grade Decliners",
                "<div>Previous or current grade file not found. Add both grade CSVs to enable grade change analysis.</div>"
            )

        # Build normalized email keys for both dataframes
        def _email_from_row(row: pd.Series) -> Optional[str]:
            try:
                if 'ID' in row.index and isinstance(row['ID'], str) and '@' in row['ID']:
                    return row['ID'].strip().lower()
                if 'SIS Login ID' in row.index and pd.notna(row['SIS Login ID']):
                    return f"{str(row['SIS Login ID']).strip().lower()}@charlotte.edu"
            except Exception:
                return None
            return None

        def _score_from_row(row: pd.Series) -> Optional[float]:
            for c in ("Current Score", "Current Grade"):
                if c in row.index:
                    try:
                        v = float(pd.to_numeric(row[c], errors='coerce'))
                        if pd.notna(v):
                            return v
                    except Exception:
                        continue
            return None

        prev_map: Dict[str, float] = {}
        for _, r in prev_grades_df.iterrows():
            email = _email_from_row(r)
            if not email:
                continue
            val = _score_from_row(r)
            if val is not None:
                prev_map[email] = val

        current_map: Dict[str, float] = {}
        for _, r in grades_df.iterrows():
            email = _email_from_row(r)
            if not email:
                continue
            val = _score_from_row(r)
            if val is not None:
                current_map[email] = val

        # Compute declines
        declines: List[Tuple[str, float, float, float]] = []  # (email, previous, current, delta)
        for email, prev_score in prev_map.items():
            curr = current_map.get(email)
            if curr is None:
                continue
            delta = curr - prev_score
            if pd.notna(delta) and delta < 0:
                declines.append((email, prev_score, curr, delta))

        if not declines:
            return _html_section("Grade Decliners", "<div>No students show a grade decline between reflections.</div>")

        # Sort by largest negative change
        declines.sort(key=lambda x: x[3])  # delta ascending (most negative first)

        # Build table with optional reflection/topic snippets from current exploded_df
        rows_html: List[str] = []
        for email, prev_score, curr_score, delta in declines:
            summary_bits: List[str] = []
            try:
                if exploded_df is not None and not exploded_df.empty:
                    e = exploded_df[exploded_df['ID'].astype(str).str.strip().str.lower() == email]
                    if not e.empty:
                        # Prefer reflection_summary; fall back to instructor_suggestions or topic list
                        if 'reflection_summary' in e.columns and e['reflection_summary'].notna().any():
                            txt = str(e['reflection_summary'].dropna().astype(str).iloc[0])
                            summary_bits.append(self._render_text_as_html(txt))
                        elif 'instructor_suggestions' in e.columns and e['instructor_suggestions'].notna().any():
                            txt = str(e['instructor_suggestions'].dropna().astype(str).iloc[0])
                            summary_bits.append(self._render_text_as_html(txt))
                        else:
                            topics = e['primary_labels_selected'].astype(str).dropna().unique().tolist() if 'primary_labels_selected' in e.columns else []
                            if topics:
                                summary_bits.append(f"<p><b>Topics:</b> {', '.join(topics[:5])}</p>")
            except Exception:
                pass

            rows_html.append(
                f"<tr>"
                f"<td>{email}</td>"
                f"<td>{prev_score:.1f}</td>"
                f"<td>{curr_score:.1f}</td>"
                f"<td style=\"color:#d32f2f;\">{delta:.1f}</td>"
                f"<td>{''.join(summary_bits) or '<i>No summary available</i>'}</td>"
                f"</tr>"
            )

        table_html = (
            "<table style=\"width:100%;border-collapse:collapse;\">"
            "<thead><tr>"
            "<th style=\"text-align:left;border-bottom:1px solid #ddd;\">Student</th>"
            "<th style=\"text-align:right;border-bottom:1px solid #ddd;\">Prev Grade</th>"
            "<th style=\"text-align:right;border-bottom:1px solid #ddd;\">Current Grade</th>"
            "<th style=\"text-align:right;border-bottom:1px solid #ddd;\">Δ</th>"
            "<th style=\"text-align:left;border-bottom:1px solid #ddd;\">Current Reflection Summary</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows_html)}</tbody>"
            "</table>"
        )

        return _html_section("Grade Decliners (Previous vs Current)", table_html)

    def build_topic_summaries_html(self, course_name: str, reflection_folder: str, *, selected_topics: Optional[List[str]] = None) -> str:
        _, grades_df, exploded_df = self.load_available_data(course_name, reflection_folder)
        name_map = _build_name_map(grades_df)
        if exploded_df is None or exploded_df.empty:
            return _html_section("Topic Summaries", "<div>No topic analysis data found. Run Topic Analysis first.</div>")

        df = exploded_df.copy()
        if selected_topics:
            df = df[df["primary_labels_selected"].astype(str).isin(selected_topics)]
            if df.empty:
                return _html_section("Topic Summaries", "<div>No rows match the selected topics.</div>")

        summaries_html: List[str] = []
        for topic, g in df.groupby(df["primary_labels_selected"].astype(str)):
            unresolved = (g["resolution_primary_labels"].astype(str).str.lower() == "unresolved").sum()
            total = len(g)
            urg = g["urgency"].astype(str).value_counts().to_dict() if "urgency" in g.columns else {}
            # Build a student names list for this topic
            try:
                emails = g['ID'].astype(str).str.strip().str.lower().dropna().unique().tolist()
                names = [name_map.get(e, e) for e in emails][:24]
                names_line = ", ".join(names)
            except Exception:
                names_line = ""

            sample_rows = g[[c for c in ["reflection_summary", "instructor_suggestions"] if c in g.columns]].head(40)
            content = _truncate(sample_rows.to_csv(index=False))
            system = (
                f"Summarize the student reflections for topic '{topic}'. Include counts (total={total}, unresolved={unresolved}) "
                f"and urgency distribution {urg}. Name students explicitly when they mention this topic (avoid 'some students'). "
                f"Students: {names_line}. Provide concise instructor actions and early-warning signals."
            )
            gpt = _summarize_with_gpt(system, content)
            if not gpt:
                # Fallback textual card
                gpt = (
                    f"<p><b>Topic:</b> {topic} (total={total}, unresolved={unresolved})</p>"
                    + (f"<p><b>Urgency:</b> {urg}</p>" if urg else "")
                    + (f"<p><b>Students:</b> {names_line}</p>" if names_line else "")
                )
            else:
                gpt = self._render_text_as_html(gpt)
            summaries_html.append(_html_section(f"Topic: {topic}", gpt))

        return "\n".join(summaries_html) if summaries_html else _html_section("Topic Summaries", "<div>No topics found.</div>")

    def build_student_summaries_html(self, course_name: str, reflection_folder: str, *, student_filter: Optional[StudentFilter] = None) -> str:
        _, grades_df, exploded_df = self.load_available_data(course_name, reflection_folder)
        if exploded_df is None or exploded_df.empty:
            return _html_section("Student Summaries", "<div>No topic analysis data found. Run Topic Analysis first.</div>")

        # Build grade lookup by email if possible
        grade_by_email: Dict[str, float] = {}
        if grades_df is not None and not grades_df.empty:
            key_col = None
            if "ID" in grades_df.columns:
                key_col = "ID"
            elif "SIS Login ID" in grades_df.columns:
                key_col = "SIS Login ID"
            score_col = None
            for c in ["Current Score", "Current Grade"]:
                if c in grades_df.columns:
                    score_col = c
                    break
            if key_col and score_col:
                tmp = grades_df[[key_col, score_col]].copy()
                tmp[key_col] = tmp[key_col].astype(str).str.strip()
                grade_by_email = pd.to_numeric(tmp[score_col], errors="coerce").to_dict()

        df = exploded_df.copy()
        df["ID"] = df.get("ID", "").astype(str).str.strip()

        # Apply filters
        if student_filter:
            # Unresolved only
            if student_filter.unresolved_only and "resolution_primary_labels" in df.columns:
                df = df[df["resolution_primary_labels"].astype(str).str.lower() == "unresolved"]

            # Urgency filter
            if student_filter.urgency_levels and "urgency" in df.columns:
                df = df[df["urgency"].astype(str).isin(student_filter.urgency_levels)]

            # Grade filters
            if grade_by_email and (student_filter.min_grade is not None or student_filter.max_grade is not None):
                def _grade_ok(email: str) -> bool:
                    val = grade_by_email.get(email)
                    if val is None or pd.isna(val):
                        return False
                    if student_filter.min_grade is not None and val < student_filter.min_grade:
                        return False
                    if student_filter.max_grade is not None and val > student_filter.max_grade:
                        return False
                    return True

                df = df[df["ID"].map(_grade_ok)]

        if df.empty:
            return _html_section("Student Summaries", "<div>No students matched the selected filters.</div>")

        cards: List[str] = []
        for student_id, g in df.groupby("ID"):
            topics = g["primary_labels_selected"].astype(str).value_counts().head(5).to_dict() if "primary_labels_selected" in g.columns else {}
            unresolved = (g["resolution_primary_labels"].astype(str).str.lower() == "unresolved").sum() if "resolution_primary_labels" in g.columns else 0
            urgency_counts = g["urgency"].astype(str).value_counts().to_dict() if "urgency" in g.columns else {}
            grade_val = grade_by_email.get(student_id)

            # Skip GPT for individual students (too slow with many students)
            # Just show the metrics directly
            gpt = None  # Disable per-student GPT calls for speed
            if not gpt:
                gpt = (
                    f"<p><b>Student:</b> {student_id}</p>"
                    + (f"<p><b>Grade:</b> {round(grade_val, 1)}</p>" if grade_val is not None and pd.notna(grade_val) else "")
                    + (f"<p><b>Top topics:</b> {topics}</p>" if topics else "")
                    + (f"<p><b>Unresolved items:</b> {unresolved}</p>" if unresolved else "")
                    + (f"<p><b>Urgency:</b> {urgency_counts}</p>" if urgency_counts else "")
                )
            else:
                gpt = self._render_text_as_html(gpt)
            cards.append(_html_section(f"Student: {student_id}", gpt))

        return "\n".join(cards)

    # ---------------------------- Report integration helpers ----------------------------
    def build_report_html(self, course_name: str, reflection_folder: str, *, include_topics: bool = True) -> str:
        sections: List[str] = []
        sections.append(self.build_complete_summary_html(course_name, reflection_folder))
        if include_topics:
            sections.append(self.build_topic_summaries_html(course_name, reflection_folder))
        # Add grade decliners section (previous vs current reflection)
        try:
            sections.append(self.build_grade_decliners_html(course_name, reflection_folder))
        except Exception:
            # Never break report rendering if the optional section fails
            pass
        return "\n".join(sections)

    def save_html(self, course_name: str, reflection_folder: str, html_content: str, filename: str) -> str:
        paths = self._paths(course_name, reflection_folder)
        os.makedirs(paths["results"], exist_ok=True)
        out_path = os.path.join(paths["results"], filename)
        with open(out_path, "w") as f:
            f.write(html_content)
        return out_path

    # ---------------------------- Rendering helpers ----------------------------
    def build_individual_email_text(self, *, name: str, email: str, current_grade: Optional[float], urgency: Optional[str], resolution: Optional[str], missing_assignments: Optional[List[str]] = None) -> Tuple[str, str]:
        subject = f"Quick check‑in for {name}"
        lines: List[str] = []
        lines.append(f"Hi {name.split(',')[0]},")
        lines.append("")
        lines.append("I reviewed your latest reflection and grade. I want to help you keep momentum.")
        if current_grade is not None:
            lines.append(f"Current grade: {current_grade:.1f}.")
        if resolution and resolution != "resolved":
            lines.append(f"Some items are {resolution}—let’s address them together.")
        if urgency and urgency != "none":
            lines.append(f"You indicated {urgency} urgency—let’s handle the highest‑impact step this week.")
        if missing_assignments:
            lines.append("")
            lines.append("Missing assignments:")
            lines.append("- " + "\n- ".join(missing_assignments))
        lines.append("")
        lines.append("Next steps:")
        lines.append("- Book a 15‑minute office hour: <add link>")
        lines.append("- Skim the attached resources for your topic(s)")
        lines.append("- Reply with the specific concept you want help with")
        lines.append("")
        lines.append("Best,")
        lines.append("<Instructor Name>")
        return subject, "\n".join(lines)

    def generate_ai_email(self, course_name: str, reflection_folder: str, *, student_email: str, student_name: Optional[str] = None, missing_assignments: Optional[List[str]] = None) -> Tuple[str, str]:
        """Generate an individualized email using LLM (falls back to template on failure)."""
        # DISABLED - Email generation takes too long
        return ("", "")
        # Gather context
        reflection_df, grades_df, exploded_df = self.load_available_data(course_name, reflection_folder)
        current_grade: Optional[float] = None
        urgency: Optional[str] = None
        resolution: Optional[str] = None
        missing: List[str] = []
        name = student_name or student_email

        # If AI is disabled, quickly return the template
        if _ai_disabled():
            return self.build_individual_email_text(
                name=name,
                email=student_email,
                current_grade=None,
                urgency=None,
                resolution=None,
                missing_assignments=missing_assignments or None,
            )

        try:
            # Grade
            if grades_df is not None and not grades_df.empty:
                # Try ID/email match
                row = None
                if 'ID' in grades_df.columns:
                    row = grades_df[grades_df['ID'].astype(str).str.strip().str.lower() == student_email.lower()]
                if (row is None or row.empty) and 'SIS Login ID' in grades_df.columns:
                    row = grades_df[grades_df['SIS Login ID'].astype(str).str.strip().str.lower() == student_email.split('@')[0].lower()]
                if row is not None and not row.empty:
                    if 'Current Score' in row.columns:
                        current_grade = float(pd.to_numeric(row['Current Score'], errors='coerce').iloc[0])
                    elif 'Current Grade' in row.columns:
                        current_grade = float(pd.to_numeric(row['Current Grade'], errors='coerce').iloc[0])
        except Exception:
            pass

        try:
            if exploded_df is not None and not exploded_df.empty:
                r = exploded_df[exploded_df['ID'].astype(str).str.strip().str.lower() == student_email.lower()]
                if not r.empty:
                    if 'urgency' in r.columns:
                        urgency = str(r['urgency'].iloc[0])
                    if 'resolution_primary_labels' in r.columns:
                        resolution = str(r['resolution_primary_labels'].iloc[0])
        except Exception:
            pass

        # Missing assignments best-effort: compare against cohort max per assignment from grades_df (already encapsulated elsewhere)
        # For now, no heavy recomputation here to keep things fast; rely on template if needed.

        # Build reflection content
        content_parts: List[str] = []
        try:
            if reflection_df is not None and not reflection_df.empty and 'ID' in reflection_df.columns:
                rf = reflection_df[reflection_df['ID'].astype(str).str.strip().str.lower() == student_email.lower()]
                if not rf.empty:
                    # include first few Q/A columns
                    content_parts.append(rf.head(1).to_csv(index=False))
        except Exception:
            pass
        try:
            if exploded_df is not None and not exploded_df.empty:
                e = exploded_df[exploded_df['ID'].astype(str).str.strip().str.lower() == student_email.lower()]
                if not e.empty:
                    cols = [c for c in ['primary_labels_selected','resolution_primary_labels','urgency','reflection_summary','instructor_suggestions'] if c in e.columns]
                    content_parts.append(e[cols].head(4).to_csv(index=False))
        except Exception:
            pass
        merged_content = _truncate("\n\n".join(content_parts) or "No reflection details available.")

        # Try LLM JSON response
        try:
            from application.controller.gpt_api import Model  # type: ignore
            instructions = (
                "You are an academic advisor. Write a short, supportive email for one student. "
                "Use the provided details (reflection snippets, topics, urgency, resolution, grade). "
                "If missing_assignments are provided, incorporate them briefly as a bulleted list in the body. "
                "Output JSON with keys: subject, body. Body must start with 'Hi {first_name},' and be under 180 words."
            )
            user = (
                f"Student: name={name}, email={student_email}, current_grade={current_grade}, "
                f"urgency={urgency}, resolution={resolution}, missing_assignments={missing_assignments}.\n\nDetails:\n{merged_content}"
            )
            resp = Model.prompt(instructions, user, json=True)
            import json as _json
            data = _json.loads(resp)
            subj = str(data.get('subject') or '').strip()
            body = str(data.get('body') or '').strip()
            if subj and body:
                return subj, body
        except Exception:
            pass

        # Fallback template
        return self.build_individual_email_text(
            name=name,
            email=student_email,
            current_grade=current_grade,
            urgency=urgency,
            resolution=resolution,
            missing_assignments=missing_assignments or None,
        )
    def _render_text_as_html(self, text: str) -> str:
        """Convert markdown/plaintext to HTML for readable display.

        Tries the `markdown` package; falls back to simple line/heading/bullet handling.
        """
        if not text:
            return ""
        try:
            import markdown  # type: ignore
            return markdown.markdown(
                text,
                extensions=["extra", "sane_lists", "nl2br", "tables"],
                output_format="html5",
            )
        except Exception:
            pass

        import html
        escaped = html.escape(text)
        lines = escaped.split("\n")
        html_lines = []
        in_list = False
        for ln in lines:
            s = ln.strip()
            if s.startswith("### "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h3>{s[4:]}</h3>")
            elif s.startswith("## "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h2>{s[3:]}</h2>")
            elif s.startswith("# "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h1>{s[2:]}</h1>")
            elif s.startswith("- ") or s.startswith("* "):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                html_lines.append(f"<li>{s[2:]}</li>")
            elif s:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<p>{s}</p>")
            else:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
        if in_list:
            html_lines.append("</ul>")
        return "\n".join(html_lines)


# ---------------------------- Additions: Performance-based filtering and V2 summaries ----------------------------
    def _detect_grade_columns(self, grades_df: pd.DataFrame) -> Tuple[List[str], List[str]]:
        """Identify quiz and assignment-like columns by name heuristics (case-insensitive).
        Returns (quiz_cols, assignment_cols).
        """
        if grades_df is None or grades_df.empty:
            return [], []

        quiz_keywords = ["quiz", "test", "exam"]
        assign_keywords = ["assignment", "hw", "homework", "project", "lab"]

        def _is_quiz(col: str) -> bool:
            c = str(col).lower()
            return any(k in c for k in quiz_keywords)

        def _is_assignment(col: str) -> bool:
            c = str(col).lower()
            return any(k in c for k in assign_keywords)

        skip_cols = {"id", "sis user id", "section", "student", "sis login id", "current score", "current grade"}

        quiz_cols: List[str] = []
        assignment_cols: List[str] = []
        for col in grades_df.columns:
            cl = str(col).strip().lower()
            if cl in skip_cols:
                continue
            if _is_quiz(col):
                quiz_cols.append(col)
            elif _is_assignment(col):
                assignment_cols.append(col)
        return quiz_cols, assignment_cols

    def _email_from_grades_row(self, row: pd.Series) -> Optional[str]:
        """Derive an email-like key from a grades row using ID or SIS Login ID.
        Falls back to username@charlotte.edu for SIS Login ID.
        """
        try:
            # Prefer ID if it already looks like an email
            if 'ID' in row.index:
                val = str(row['ID'])
                if '@' in val:
                    return val.strip().lower()
            # Otherwise use SIS Login ID -> username@charlotte.edu
            if 'SIS Login ID' in row.index:
                username = str(row['SIS Login ID']).strip()
                if username and username.lower() not in {"nan", "", "none"}:
                    return f"{username.lower()}@charlotte.edu"
        except Exception:
            pass
        return None

    def _normalize_columns_percent(self, df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """Create normalized percentage columns (0-100) for each col using cohort max as denominator."""
        out = pd.DataFrame(index=df.index)
        for col in cols:
            try:
                series = pd.to_numeric(df[col], errors='coerce')
                max_val = series.max(skipna=True)
                if pd.isna(max_val) or max_val == 0:
                    continue
                out[col] = (series / max_val) * 100.0
            except Exception:
                continue
        return out

    def _compute_performance_averages(self, grades_df: pd.DataFrame) -> pd.DataFrame:
        """Compute per-student average % for quizzes and assignments based on cohort-normalized columns."""
        quiz_cols, assignment_cols = self._detect_grade_columns(grades_df)
        if not quiz_cols and not assignment_cols:
            return pd.DataFrame(columns=["email", "quiz_avg", "assignment_avg"]).set_index('email')

        quiz_norm = self._normalize_columns_percent(grades_df, quiz_cols) if quiz_cols else pd.DataFrame(index=grades_df.index)
        assign_norm = self._normalize_columns_percent(grades_df, assignment_cols) if assignment_cols else pd.DataFrame(index=grades_df.index)

        # Build email keys
        emails: List[Optional[str]] = []
        for _, row in grades_df.iterrows():
            emails.append(self._email_from_grades_row(row))
        emails_series = pd.Series(emails, index=grades_df.index, name='email')

        # Aggregate
        parts = [emails_series]
        if not quiz_norm.empty:
            parts.append(quiz_norm)
        if not assign_norm.empty:
            parts.append(assign_norm)
        merged = pd.concat(parts, axis=1)
        merged = merged.dropna(subset=['email'])
        grouped = merged.groupby('email')

        def _avg(df_sub: pd.DataFrame, cols: List[str]) -> pd.Series:
            if not cols:
                return pd.Series([], dtype=float)
            present = [c for c in cols if c in df_sub.columns]
            if not present:
                return pd.Series([], dtype=float)
            return df_sub[present].mean(axis=1, skipna=True)

        quiz_avgs = grouped.apply(lambda g: _avg(g, quiz_cols).mean(skipna=True) if quiz_cols else float('nan'))
        assign_avgs = grouped.apply(lambda g: _avg(g, assignment_cols).mean(skipna=True) if assignment_cols else float('nan'))

        result = pd.DataFrame({
            'quiz_avg': quiz_avgs,
            'assignment_avg': assign_avgs,
        })
        return result

    def get_performance_filtered_emails(self, course_name: str, reflection_folder: str, *, mode: Optional[str], threshold: float = 80.0) -> List[str]:
        """Return list of student emails filtered by performance mode.

        mode: 'good_quiz_weak_assignment' | 'weak_quiz_good_assignment' | None
        threshold: percent threshold (80 = default)
        """
        _, grades_df, _ = self.load_available_data(course_name, reflection_folder)
        if grades_df is None or grades_df.empty or not mode:
            return []
        perf = self._compute_performance_averages(grades_df)
        if perf.empty:
            return []
        perf = perf.fillna(-1)
        if mode == 'good_quiz_weak_assignment':
            mask = (perf['quiz_avg'] >= threshold) & (perf['assignment_avg'] >= 0) & (perf['assignment_avg'] < threshold)
        elif mode == 'weak_quiz_good_assignment':
            mask = (perf['assignment_avg'] >= threshold) & (perf['quiz_avg'] >= 0) & (perf['quiz_avg'] < threshold)
        else:
            return []
        return perf.index[mask].tolist()

    def build_student_summaries_html_v2(self, course_name: str, reflection_folder: str, *, performance_mode: Optional[str] = None, generate_ai_emails: bool = False) -> str:
        """Student summaries with optional performance filtering and AI email generation toggle.

        performance_mode: 'good_quiz_weak_assignment' | 'weak_quiz_good_assignment' | None
        generate_ai_emails: if True, attempts per-student AI email; otherwise skips for speed
        """
        reflection_df, grades_df, exploded_df = self.load_available_data(course_name, reflection_folder)
        if exploded_df is None or exploded_df.empty:
            return _html_section("Student Summaries (V2)", "<div>No topic analysis data found. Run Topic Analysis first.</div>")

        # Determine student set
        filtered_emails: Optional[List[str]] = None
        if performance_mode:
            filtered_emails = self.get_performance_filtered_emails(course_name, reflection_folder, mode=performance_mode)

        df = exploded_df.copy()
        df['ID'] = df['ID'].astype(str).str.strip().str.lower()
        if filtered_emails:
            allowed = set([e.lower() for e in filtered_emails])
            df = df[df['ID'].isin(allowed)]

        if df.empty:
            return _html_section("Student Summaries (V2)", "<div>No students matched the selected performance filter.</div>")

        # Build grade lookup for display
        grade_by_email: Dict[str, float] = {}
        if grades_df is not None and not grades_df.empty:
            key_col = None
            if 'ID' in grades_df.columns:
                key_col = 'ID'
            elif 'SIS Login ID' in grades_df.columns:
                key_col = 'SIS Login ID'
            score_col = None
            for c in ['Current Score', 'Current Grade']:
                if c in grades_df.columns:
                    score_col = c
                    break
            if key_col and score_col:
                tmp = grades_df[[key_col, score_col]].copy()
                if key_col == 'SIS Login ID':
                    tmp['email'] = tmp[key_col].astype(str).str.strip().str.lower() + '@charlotte.edu'
                else:
                    tmp['email'] = tmp[key_col].astype(str).str.strip().str.lower()
                tmp['score'] = pd.to_numeric(tmp[score_col], errors='coerce')
                grade_by_email = tmp.set_index('email')['score'].to_dict()

        # Cards
        cards: List[str] = []
        for student_id, g in df.groupby('ID'):
            topics = g['primary_labels_selected'].astype(str).value_counts().head(5).to_dict() if 'primary_labels_selected' in g.columns else {}
            unresolved = (g['resolution_primary_labels'].astype(str).str.lower() == 'unresolved').sum() if 'resolution_primary_labels' in g.columns else 0
            urgency_counts = g['urgency'].astype(str).value_counts().to_dict() if 'urgency' in g.columns else {}
            grade_val = grade_by_email.get(student_id)

            # Email generation disabled - only summaries
            email_html = ""

            body = []
            body.append(f"<p><b>Student:</b> {student_id}</p>")
            if grade_val is not None and pd.notna(grade_val):
                body.append(f"<p><b>Current Grade:</b> {round(float(grade_val), 1)}</p>")
            if topics:
                body.append(f"<p><b>Top Topics:</b> {topics}</p>")
            body.append(f"<p><b>Unresolved items:</b> {unresolved}</p>")
            if urgency_counts:
                body.append(f"<p><b>Urgency:</b> {urgency_counts}</p>")
            body.append(email_html)

            cards.append(_html_section(f"Student: {student_id}", "\n".join(body)))

        header_bits = []
        if performance_mode == 'good_quiz_weak_assignment':
            header_bits.append("Filter: Good in quizzes (≥80%), weak in assignments (<80%)")
        elif performance_mode == 'weak_quiz_good_assignment':
            header_bits.append("Filter: Weak in quizzes (<80%), good in assignments (≥80%)")
        header_bits.append(f"AI Emails: {'On' if generate_ai_emails else 'Off'}")
        header_html = "<p>" + " | ".join(header_bits) + "</p>"

        return _html_section("Student Summaries (V2)", header_html + "\n" + "\n".join(cards))
