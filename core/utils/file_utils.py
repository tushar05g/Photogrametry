"""
File system utilities for the Morphic 3D Scanner system.
"""

import os
import shutil
from pathlib import Path
from typing import Union, List


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def safe_delete(path: Union[str, Path]) -> bool:
    """
    Safely delete a file or directory.
    
    Args:
        path: Path to delete
        
    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        path_obj = Path(path)
        if path_obj.is_file():
            path_obj.unlink()
        elif path_obj.is_dir():
            shutil.rmtree(path_obj)
        return True
    except (OSError, PermissionError):
        return False


def get_file_size(path: Union[str, Path]) -> int:
    """
    Get file size in bytes.
    
    Args:
        path: File path
        
    Returns:
        File size in bytes, 0 if file doesn't exist
    """
    try:
        return Path(path).stat().st_size
    except (OSError, FileNotFoundError):
        return 0


def list_files(
    directory: Union[str, Path],
    pattern: str = "*",
    recursive: bool = False
) -> List[Path]:
    """
    List files in a directory matching a pattern.
    
    Args:
        directory: Directory to search
        pattern: Glob pattern to match
        recursive: Whether to search recursively
        
    Returns:
        List of matching file paths
    """
    dir_path = Path(directory)
    if recursive:
        return list(dir_path.rglob(pattern))
    else:
        return list(dir_path.glob(pattern))


def cleanup_temp_files(temp_dir: Union[str, Path], max_age_hours: int = 24) -> int:
    """
    Clean up temporary files older than specified age.
    
    Args:
        temp_dir: Temporary directory
        max_age_hours: Maximum age in hours
        
    Returns:
        Number of files cleaned up
    """
    import time
    
    temp_path = Path(temp_dir)
    if not temp_path.exists():
        return 0
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    cleaned_count = 0
    
    for file_path in temp_path.rglob("*"):
        if file_path.is_file():
            file_age = current_time - file_path.stat().st_mtime
            if file_age > max_age_seconds:
                if safe_delete(file_path):
                    cleaned_count += 1
    
    return cleaned_count
