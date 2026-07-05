# =========================================================
# ApexDeploy - Security Utilities
# Helper methods for scrubbing strings and matching leak patterns
# =========================================================

import logging
import re

logger = logging.getLogger("utils.security_utils")

# Simple generic pattern list for scrubbing secrets
SECRET_PATTERNS = [
    r"(?i)(password|passwd|secret|passphrase|token|key|private_key)\s*[:=]\s*['\"]([^'\"]{4,})['\"]",
    r"AKIA[0-9A-Z]{16}",  # AWS Key ID
]


def sanitize_sensitive_data(text: str, replacement: str = "********") -> str:
    """Masks secrets and credentials in logs/outputs to prevent accidental leaks.

    Args:
        text: Raw log text.
        replacement: String to override matched secrets.

    Returns:
        Sanitized text.
    """
    sanitized = text
    for pattern in SECRET_PATTERNS:
        matches = re.findall(pattern, sanitized)
        for match in matches:
            if isinstance(match, tuple):
                # Match contains groups, let's substitute the secret value (group index 1)
                val_to_mask = match[1]
            else:
                val_to_mask = match
            if val_to_mask and val_to_mask != replacement:
                sanitized = sanitized.replace(val_to_mask, replacement)
    return sanitized


def check_for_secrets(text: str) -> bool:
    """Checks if a string contains potential secrets or keys.

    Args:
        text: Input string.

    Returns:
        True if potential secret matches, False otherwise.
    """
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text):
            return True
    return False
