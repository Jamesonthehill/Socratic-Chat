"""
Statistical analysis services for the HTML builder.
This package contains services for various statistical analyses including:
- Chi-square analysis
- Correlation analysis
- Grade analysis
- Outlier detection and removal
"""

from .chi_square_analyzer import ChiSquareAnalyzer
from .correlation_analyzer import CorrelationAnalyzer
from .outlier_detector import OutlierDetector, OutlierAnalysis

__all__ = ['ChiSquareAnalyzer', 'CorrelationAnalyzer', 'OutlierDetector', 'OutlierAnalysis']
