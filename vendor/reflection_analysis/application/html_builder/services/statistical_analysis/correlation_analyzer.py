"""
Correlation analysis service for analyzing relationships between variables.
"""
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from scipy.stats import pearsonr, spearmanr, mannwhitneyu
import plotly.express as px
from dataclasses import dataclass

@dataclass
class CorrelationResult:
    """Container for correlation analysis results."""
    pearson_corr: float
    pearson_p: float
    spearman_corr: float
    spearman_p: float
    plot_html: str
    table_html: str

class CorrelationAnalyzer:
    """Service for performing correlation analysis between variables."""

    @staticmethod
    def analyze_grade_module_correlation(
        course_data: pd.DataFrame,
        reflection_num: int = 4
    ) -> CorrelationResult:
        """
        Analyze correlation between grades and module completion.

        Args:
            course_data: DataFrame containing student data
            reflection_num: Reflection number to analyze

        Returns:
            CorrelationResult containing correlation statistics and visualizations
        """
        # Compute correlations
        pearson_corr, pearson_p = pearsonr(
            course_data['num_modules_completed'],
            course_data['reflection_4_grade']
        )
        spearman_corr, spearman_p = spearmanr(
            course_data['num_modules_completed'],
            course_data['reflection_4_grade']
        )

        # Create scatter plot
        fig = px.scatter(
            course_data,
            x='num_modules_completed',
            y='reflection_4_grade',
            trendline='ols',
            labels={
                'num_modules_completed': 'Number of Support Modules Completed',
                'reflection_4_grade': 'Reflection 4 Grade'
            },
            title='Reflection 4 Grade vs. Number of Support Modules Completed'
        )

        fig.update_traces(
            marker=dict(size=10, color='#1976d2', line=dict(width=1, color='#333'))
        )
        fig.update_layout(
            xaxis=dict(dtick=1),
            yaxis=dict(range=[0, 100]),
            plot_bgcolor='#fff',
            margin=dict(t=60, b=40)
        )

        plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
        table_html = course_data.to_html(
            index=False,
            float_format='%.2f',
            classes='emotions-topics-table',
            border=0
        )

        return CorrelationResult(
            pearson_corr=pearson_corr,
            pearson_p=pearson_p,
            spearman_corr=spearman_corr,
            spearman_p=spearman_p,
            plot_html=plot_html,
            table_html=table_html
        )

    @staticmethod
    def analyze_module_completion_grade_comparison(
        course_data: pd.DataFrame,
        reflection_num: int = 4
    ) -> Tuple[str, str]:
        """
        Compare grades between students who completed and did not complete each module.

        Args:
            course_data: DataFrame containing student data
            reflection_num: Reflection number to analyze

        Returns:
            Tuple of (table_html, plots_html) containing statistical results and visualizations
        """
        summary_rows = []
        boxplots = []

        for module in course_data['module'].unique():
            group1 = course_data[
                (course_data['module'] == module) &
                (course_data['completed'] == True)
            ]['grade']
            group2 = course_data[
                (course_data['module'] == module) &
                (course_data['completed'] == False)
            ]['grade']

            if len(group1) < 2 or len(group2) < 2:
                p_val = float('nan')
            else:
                _, p_val = mannwhitneyu(group1, group2, alternative='two-sided')

            mean1, mean2 = group1.mean(), group2.mean()
            med1, med2 = group1.median(), group2.median()

            summary_rows.append({
                'Module': module,
                'N Completed': len(group1),
                'N Not Completed': len(group2),
                'Mean Grade (Completed)': mean1,
                'Mean Grade (Not Completed)': mean2,
                'Median Grade (Completed)': med1,
                'Median Grade (Not Completed)': med2,
                'p-value': p_val
            })

            # Create boxplot
            plot_df = pd.DataFrame({
                'Grade': pd.concat([group1, group2]),
                'Completed': (['Yes'] * len(group1)) + (['No'] * len(group2))
            })

            fig = px.box(
                plot_df,
                x='Completed',
                y='Grade',
                points='all',
                color='Completed',
                color_discrete_map={'Yes': '#1976d2', 'No': '#bdbdbd'},
                title=f'Grades by Completion of "{module}"',
                labels={'Grade': 'Reflection 4 Grade', 'Completed': 'Completed Module'}
            )

            fig.update_layout(
                showlegend=False,
                yaxis=dict(range=[0, 100]),
                plot_bgcolor='#fff',
                margin=dict(t=50, b=40)
            )

            # Add p-value annotation
            fig.add_annotation(
                text=f"p = {p_val:.3g}" if not pd.isna(p_val) else "p = N/A",
                x=0.5, y=1.08,
                xref='paper',
                yref='paper',
                showarrow=False,
                font=dict(size=13)
            )

            boxplots.append(fig.to_html(full_html=False, include_plotlyjs=False))

        # Create summary table
        summary_df = pd.DataFrame(summary_rows)

        def highlight_sig(val):
            try:
                if float(val) < 0.05:
                    return 'background-color:#d4edda;font-weight:bold;'
            except:
                pass
            return ''

        table_html = summary_df.style.applymap(
            highlight_sig,
            subset=['p-value']
        ).set_caption(
            '<b>Statistically significant results (p < 0.05) are highlighted in green.</b>'
        ).to_html(
            index=False,
            float_format='%.2f',
            classes='emotions-topics-table',
            border=0,
            escape=False
        )

        plots_html = '<br/>'.join(boxplots)

        return table_html, plots_html
