"""
Utilities Module

Contains shared utility functions and classes used across
the Morphic 3D Scanner system.
"""

from .logger import get_logger, setup_logging
from .file_utils import safe_delete, ensure_directory
from .api_utils import make_api_request, handle_api_error

__all__ = [
    'get_logger',
    'setup_logging',
    'safe_delete',
    'ensure_directory',
    'make_api_request',
    'handle_api_error'
]
