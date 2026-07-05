# =========================================================
# ApexDeploy - Language Detector
# Detects the primary programming language of a directory
# =========================================================

import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger("utils.language_detector")


def detect_primary_language(directory_path: str) -> str:
    """Scans the directory structure and maps file extensions to detect the primary language.

    Args:
        directory_path: Directory path to scan.

    Returns:
        The detected language name (e.g. 'python', 'javascript', etc.) or 'python' as default fallback.
    """
    target = Path(directory_path).resolve()
    if not target.exists() or not target.is_dir():
        logger.warning(f"Scan directory does not exist or is not a directory: {directory_path}")
        return "python"

    # Mapping of file suffixes to standard languages
    language_map: Dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
    }

    counts: Dict[str, int] = {}

    try:
        for p in target.rglob("*"):
            # Exclude hidden files/directories and common dependency folders
            if any(part.startswith(".") for part in p.parts):
                continue
            if "node_modules" in p.parts or "venv" in p.parts or ".venv" in p.parts:
                continue

            if p.is_file():
                suffix = p.suffix.lower()
                if suffix in language_map:
                    lang = language_map[suffix]
                    counts[lang] = counts.get(lang, 0) + 1

    except Exception as e:
        logger.error(f"Error scanning workspace {directory_path} for languages: {e}")

    if not counts:
        logger.info(f"No matchable source files found in {directory_path}. Fallback: python")
        return "python"

    # Identify language with highest file counts
    primary = max(counts, key=counts.get)
    logger.info(f"Primary language detected: {primary} ({counts[primary]} files)")
    return primary
