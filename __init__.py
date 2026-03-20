"""
Tangi - Universal Model Interface for Local AI Inference
Created by BigSlimThic
"""

__version__ = "1.0.0"
__author__ = "BigSlimThic"

from Tangi.main import main
from Tangi.ui.main_window import RawChat

# Export main classes for easy import
__all__ = [
    'main',
    'RawChat',
    '__version__',
    '__author__'
]