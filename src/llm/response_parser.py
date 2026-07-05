# =========================================================
# ApexDeploy - LLM Response Parser
# Cleans and parses LLM outputs
# =========================================================

import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger("llm.parser")


def clean_json_string(text: str) -> str:
    """Cleans markdown code block boundaries (like ```json ... ```) from a string."""
    text = text.strip()
    
    # Remove leading/trailing markdown blocks
    pattern = r"^```(?:json)?\s*(.*?)\s*```$"
    match = re.match(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    return text


def parse_json_safely(text: str) -> Dict[str, Any]:
    """Safely cleans and parses a string as JSON, returning an empty dict on failure."""
    if not text:
        return {}
        
    cleaned = clean_json_string(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}. Raw input string starts with: {text[:100]}")
        return {
            "parse_error": str(e),
            "raw_text": text
        }
