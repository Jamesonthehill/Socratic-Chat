"""
Outlier detection and removal service for statistical analysis.
"""
from typing import Dict, List, Tuple, Optional, Union
import pandas as pd
import numpy as np
from dataclasses import dataclass

@dataclass
class OutlierAnalysis:
    """Container for outlier analysis results."""
    original_data: pd.DataFrame
    filtered_data: pd.DataFrame
    outliers: pd.DataFrame
    outlier_indices: List[int]
    outlier_bounds: Dict[str, Tuple[float, float]]
    summary: Dict[str, int]

class OutlierDetector:
    """Service for detecting and removing outliers using statistical methods."""

    @staticmethod
    def detect_outliers_iqr(
        data: pd.DataFrame,
        columns: List[str],
        iqr_multiplier: float = 1.5
    ) -> OutlierAnalysis:
        """
        Detect outliers using the Interquartile Range (IQR) method.

        The IQR method identifies outliers as values that fall below Q1 - (iqr_multiplier * IQR)
        or above Q3 + (iqr_multiplier * IQR), where IQR = Q3 - Q1.

        Args:
            data: DataFrame containing the data to analyze
            columns: List of column names to check for outliers
            iqr_multiplier: Multiplier for IQR (default 1.5, stricter would be 1.0)

        Returns:
            OutlierAnalysis object containing original data, filtered data, and outlier info
        """
        if data.empty:
            return OutlierAnalysis(
                original_data=data,
                filtered_data=data,
                outliers=pd.DataFrame(),
                outlier_indices=[],
                outlier_bounds={},
                summary={'total_rows': 0, 'outliers_removed': 0, 'rows_remaining': 0}
            )

        # Work with a copy to avoid modifying original data
        df = data.copy()
        outlier_bounds = {}
        outlier_mask = pd.Series(False, index=df.index)

        for column in columns:
            if column not in df.columns:
                continue

            # Skip non-numeric columns
            if not pd.api.types.is_numeric_dtype(df[column]):
                continue

            # Calculate quartiles and IQR
            Q1 = df[column].quantile(0.25)
            Q3 = df[column].quantile(0.75)
            IQR = Q3 - Q1

            # Calculate outlier bounds
            lower_bound = Q1 - (iqr_multiplier * IQR)
            upper_bound = Q3 + (iqr_multiplier * IQR)
            outlier_bounds[column] = (lower_bound, upper_bound)

            # Identify outliers for this column
            column_outliers = (df[column] < lower_bound) | (df[column] > upper_bound)
            outlier_mask = outlier_mask | column_outliers

        # Get outlier rows and their indices
        outliers = df[outlier_mask]
        outlier_indices = outlier_mask[outlier_mask].index.tolist()

        # Create filtered dataset (without outliers)
        filtered_data = df[~outlier_mask]

        # Create summary statistics
        summary = {
            'total_rows': len(df),
            'outliers_removed': len(outliers),
            'rows_remaining': len(filtered_data)
        }

        return OutlierAnalysis(
            original_data=data,
            filtered_data=filtered_data,
            outliers=outliers,
            outlier_indices=outlier_indices,
            outlier_bounds=outlier_bounds,
            summary=summary
        )

    @staticmethod
    def detect_outliers_zscore(
        data: pd.DataFrame,
        columns: List[str],
        threshold: float = 3.0
    ) -> OutlierAnalysis:
        """
        Detect outliers using the Z-score method.

        The Z-score method identifies outliers as values with absolute Z-scores
        greater than the threshold (typically 3.0).

        Args:
            data: DataFrame containing the data to analyze
            columns: List of column names to check for outliers
            threshold: Z-score threshold for outlier detection (default 3.0)

        Returns:
            OutlierAnalysis object containing original data, filtered data, and outlier info
        """
        if data.empty:
            return OutlierAnalysis(
                original_data=data,
                filtered_data=data,
                outliers=pd.DataFrame(),
                outlier_indices=[],
                outlier_bounds={},
                summary={'total_rows': 0, 'outliers_removed': 0, 'rows_remaining': 0}
            )

        # Work with a copy to avoid modifying original data
        df = data.copy()
        outlier_bounds = {}
        outlier_mask = pd.Series(False, index=df.index)

        for column in columns:
            if column not in df.columns:
                continue

            # Skip non-numeric columns
            if not pd.api.types.is_numeric_dtype(df[column]):
                continue

            # Calculate Z-scores
            mean_val = df[column].mean()
            std_val = df[column].std()

            if std_val == 0:  # Handle case where all values are the same
                continue

            z_scores = np.abs((df[column] - mean_val) / std_val)

            # Calculate outlier bounds for reference
            lower_bound = mean_val - (threshold * std_val)
            upper_bound = mean_val + (threshold * std_val)
            outlier_bounds[column] = (lower_bound, upper_bound)

            # Identify outliers for this column
            column_outliers = z_scores > threshold
            outlier_mask = outlier_mask | column_outliers

        # Get outlier rows and their indices
        outliers = df[outlier_mask]
        outlier_indices = outlier_mask[outlier_mask].index.tolist()

        # Create filtered dataset (without outliers)
        filtered_data = df[~outlier_mask]

        # Create summary statistics
        summary = {
            'total_rows': len(df),
            'outliers_removed': len(outliers),
            'rows_remaining': len(filtered_data)
        }

        return OutlierAnalysis(
            original_data=data,
            filtered_data=filtered_data,
            outliers=outliers,
            outlier_indices=outlier_indices,
            outlier_bounds=outlier_bounds,
            summary=summary
        )

    @staticmethod
    def detect_outliers_threshold(
        data: pd.DataFrame,
        columns: List[str],
        min_threshold: Optional[float] = None,
        max_threshold: Optional[float] = None
    ) -> OutlierAnalysis:
        """
        Detect outliers using simple threshold values.

        This method identifies outliers as values that fall below min_threshold
        or above max_threshold. Useful for domain-specific outlier removal
        (e.g., removing grades below 20 or above 100).

        Args:
            data: DataFrame containing the data to analyze
            columns: List of column names to check for outliers
            min_threshold: Minimum acceptable value (values below this are outliers)
            max_threshold: Maximum acceptable value (values above this are outliers)

        Returns:
            OutlierAnalysis object containing original data, filtered data, and outlier info
        """
        if data.empty:
            return OutlierAnalysis(
                original_data=data,
                filtered_data=data,
                outliers=pd.DataFrame(),
                outlier_indices=[],
                outlier_bounds={},
                summary={'total_rows': 0, 'outliers_removed': 0, 'rows_remaining': 0}
            )

        # Work with a copy to avoid modifying original data
        df = data.copy()
        outlier_bounds = {}
        outlier_mask = pd.Series(False, index=df.index)

        for column in columns:
            if column not in df.columns:
                continue

            # Skip non-numeric columns
            if not pd.api.types.is_numeric_dtype(df[column]):
                continue

            # Set bounds for reference
            actual_min = df[column].min()
            actual_max = df[column].max()
            lower_bound = min_threshold if min_threshold is not None else actual_min
            upper_bound = max_threshold if max_threshold is not None else actual_max
            outlier_bounds[column] = (lower_bound, upper_bound)

            # Identify outliers for this column
            column_outliers = pd.Series(False, index=df.index)

            if min_threshold is not None:
                column_outliers = column_outliers | (df[column] < min_threshold)

            if max_threshold is not None:
                column_outliers = column_outliers | (df[column] > max_threshold)

            outlier_mask = outlier_mask | column_outliers

        # Get outlier rows and their indices
        outliers = df[outlier_mask]
        outlier_indices = outlier_mask[outlier_mask].index.tolist()

        # Create filtered dataset (without outliers)
        filtered_data = df[~outlier_mask]

        # Create summary statistics
        summary = {
            'total_rows': len(df),
            'outliers_removed': len(outliers),
            'rows_remaining': len(filtered_data)
        }

        return OutlierAnalysis(
            original_data=data,
            filtered_data=filtered_data,
            outliers=outliers,
            outlier_indices=outlier_indices,
            outlier_bounds=outlier_bounds,
            summary=summary
        )

    @staticmethod
    def apply_outlier_removal(
        data: Union[pd.DataFrame, List, np.ndarray],
        method: str = 'iqr',
        columns: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[Union[pd.DataFrame, List, np.ndarray], OutlierAnalysis]:
        """
        Apply outlier removal to data and return both cleaned data and analysis results.

        Args:
            data: Data to clean (DataFrame, list, or numpy array)
            method: Outlier detection method ('iqr', 'zscore', or 'threshold')
            columns: Columns to check for outliers (for DataFrames)
            **kwargs: Additional arguments for the outlier detection method
                     For 'threshold' method: min_threshold, max_threshold

        Returns:
            Tuple of (cleaned_data, outlier_analysis)
        """
        # Convert input data to DataFrame for processing
        if isinstance(data, pd.DataFrame):
            df = data.copy()
            if columns is None:
                # Use all numeric columns
                columns = df.select_dtypes(include=[np.number]).columns.tolist()
        elif isinstance(data, (list, np.ndarray)):
            # Convert to DataFrame with a default column name
            df = pd.DataFrame({'value': data})
            columns = ['value']
        else:
            raise ValueError("Data must be a pandas DataFrame, list, or numpy array")

        # Apply outlier detection
        if method.lower() == 'iqr':
            analysis = OutlierDetector.detect_outliers_iqr(df, columns, **kwargs)
        elif method.lower() == 'zscore':
            analysis = OutlierDetector.detect_outliers_zscore(df, columns, **kwargs)
        elif method.lower() == 'threshold':
            analysis = OutlierDetector.detect_outliers_threshold(df, columns, **kwargs)
        else:
            raise ValueError("Method must be 'iqr', 'zscore', or 'threshold'")

        # Return data in the same format as input
        if isinstance(data, pd.DataFrame):
            return analysis.filtered_data, analysis
        elif isinstance(data, list):
            return analysis.filtered_data['value'].tolist(), analysis
        else:  # numpy array
            return analysis.filtered_data['value'].values, analysis

    @staticmethod
    def generate_outlier_report(analysis: OutlierAnalysis) -> str:
        """
        Generate a human-readable report of outlier analysis results.

        Args:
            analysis: OutlierAnalysis object from outlier detection

        Returns:
            HTML string containing the outlier report
        """
        if analysis.summary['outliers_removed'] == 0:
            return '''
            <div class="outlier-report no-outliers">
                <h4>📊 Outlier Analysis Results</h4>
                <p><strong>✅ No outliers detected</strong></p>
                <p>All {total_rows} data points are within normal statistical bounds.</p>
            </div>
            '''.format(**analysis.summary)

        outlier_percentage = (analysis.summary['outliers_removed'] / analysis.summary['total_rows']) * 100

        bounds_info = ""
        if analysis.outlier_bounds:
            bounds_info = "<h5>Outlier Bounds:</h5><ul>"
            for column, (lower, upper) in analysis.outlier_bounds.items():
                bounds_info += f"<li><strong>{column}:</strong> {lower:.2f} to {upper:.2f}</li>"
            bounds_info += "</ul>"

        return f'''
        <div class="outlier-report">
            <h4>📊 Outlier Analysis Results</h4>
            <div class="outlier-summary">
                <p><strong>Original data points:</strong> {analysis.summary['total_rows']}</p>
                <p><strong>Outliers detected:</strong> {analysis.summary['outliers_removed']} ({outlier_percentage:.1f}%)</p>
                <p><strong>Data points remaining:</strong> {analysis.summary['rows_remaining']}</p>
            </div>
            {bounds_info}
            <p class="outlier-note">
                <em>Note: Outliers are identified using statistical methods and may represent legitimate extreme values
                or data collection errors. Analysis is provided both with and without outliers for comparison.</em>
            </p>
        </div>
        '''
