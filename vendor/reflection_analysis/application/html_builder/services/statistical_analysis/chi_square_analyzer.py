"""
Chi-square analysis service for statistical testing of categorical relationships.
"""
from typing import List, Tuple, Dict, Any
import pandas as pd
from scipy.stats import chi2_contingency

class ChiSquareAnalyzer:
    """Service for performing chi-square analysis on categorical data."""

    @staticmethod
    def safe_odds_ratio(a: int, b: int, c: int, d: int) -> float:
        """
        Calculate odds ratio with continuity correction.

        Args:
            a: True positive count
            b: False positive count
            c: False negative count
            d: True negative count

        Returns:
            float: Odds ratio with continuity correction
        """
        a, b, c, d = a+0.5, b+0.5, c+0.5, d+0.5
        return (a * d) / (b * c)

    @staticmethod
    def analyze_topic_quiz_correlation(
        student_topics: Dict[str, set],
        student_quizzes: Dict[str, set],
        summary_topics: List[str],
        all_quizzes: List[str]
    ) -> List[Tuple[str, str, float, List[List[int]], float]]:
        """
        Analyze correlation between topics and quiz completion using chi-square test.

        Args:
            student_topics: Dictionary mapping student IDs to sets of topics
            student_quizzes: Dictionary mapping student IDs to sets of completed quizzes
            summary_topics: List of all topics to analyze
            all_quizzes: List of all quizzes to analyze

        Returns:
            List of tuples containing (topic, quiz, p-value, contingency table, odds ratio)
        """
        results = []
        for topic in summary_topics:
            for quiz in all_quizzes:
                data = []
                for student_id in student_topics:
                    has_topic = int(topic in student_topics[student_id])
                    completed_quiz = int(quiz in student_quizzes.get(student_id, set()))
                    data.append((has_topic, completed_quiz))

                df = pd.DataFrame(data, columns=['has_topic', 'completed_quiz'])
                table = pd.crosstab(df['has_topic'], df['completed_quiz'])

                if table.shape == (2, 2):
                    chi2, p, _, _ = chi2_contingency(table)
                    a = table.loc[1, 1]
                    b = table.loc[1, 0]
                    c = table.loc[0, 1]
                    d = table.loc[0, 0]
                    or_value = ChiSquareAnalyzer.safe_odds_ratio(a, b, c, d)

                    if p < 0.05:  # Only include statistically significant results
                        results.append((topic, quiz, p, table.values.tolist(), or_value))

        return results

    @staticmethod
    def analyze_quiz_topic_correlation(
        student_topics: Dict[str, set],
        student_quizzes: Dict[str, set],
        summary_topics: List[str],
        all_quizzes: List[str]
    ) -> List[Tuple[str, str, float, List[List[int]], float]]:
        """
        Analyze correlation between quiz completion and topics using chi-square test.
        This is the reverse of analyze_topic_quiz_correlation.

        Args:
            student_topics: Dictionary mapping student IDs to sets of topics
            student_quizzes: Dictionary mapping student IDs to sets of completed quizzes
            summary_topics: List of all topics to analyze
            all_quizzes: List of all quizzes to analyze

        Returns:
            List of tuples containing (quiz, topic, p-value, contingency table, odds ratio)
        """
        results = []
        for quiz in all_quizzes:
            for topic in summary_topics:
                data = []
                for student_id in student_topics:
                    completed_quiz = int(quiz in student_quizzes.get(student_id, set()))
                    has_topic = int(topic in student_topics[student_id])
                    data.append((completed_quiz, has_topic))

                df = pd.DataFrame(data, columns=['completed_quiz', 'has_topic'])
                table = pd.crosstab(df['completed_quiz'], df['has_topic'])

                if table.shape == (2, 2):
                    chi2, p, _, _ = chi2_contingency(table)
                    a = table.loc[1, 1]
                    b = table.loc[1, 0]
                    c = table.loc[0, 1]
                    d = table.loc[0, 0]
                    or_value = ChiSquareAnalyzer.safe_odds_ratio(a, b, c, d)

                    if p < 0.05:  # Only include statistically significant results
                        results.append((quiz, topic, p, table.values.tolist(), or_value))

        return results
