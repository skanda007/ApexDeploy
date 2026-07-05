# =========================================================
# ApexDeploy - Gemini LLM Client
# Integrates with the Google GenAI SDK and ADK wrappers
# =========================================================

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel
from pydantic.fields import PydanticUndefined

from google import genai
from google.genai import types
from google.adk.models.google_llm import Gemini

from src.config.settings import settings
from src.llm.safety import get_safety_settings

logger = logging.getLogger("llm.gemini")


def _build_mock_dict(schema: Type[BaseModel]) -> Dict[str, Any]:
    """Builds a complete, Pydantic-valid fallback dict for any BaseModel schema.
    Introspects model_fields to provide sensible defaults for every field,
    including required ones that have no declared default value.
    """
    result: Dict[str, Any] = {}
    for field_name, field_info in schema.model_fields.items():
        # 1. Use declared default if present
        if field_info.default is not PydanticUndefined:
            result[field_name] = field_info.default
        # 2. Use default_factory if present (e.g. default_factory=list)
        elif field_info.default_factory is not None:
            result[field_name] = field_info.default_factory()
        else:
            # 3. Derive a safe default from the annotation type
            ann = field_info.annotation
            origin = getattr(ann, "__origin__", None)
            if ann in (str, Optional[str]) or ann is str:
                result[field_name] = "mock"
            elif ann in (bool, Optional[bool]) or ann is bool:
                result[field_name] = False
            elif ann in (int, Optional[int]) or ann is int:
                result[field_name] = 0
            elif ann in (float, Optional[float]) or ann is float:
                result[field_name] = 0.0
            elif origin is list or ann is list:
                result[field_name] = []
            else:
                result[field_name] = None
    return result


def get_genai_client() -> genai.Client:
    """Instantiates the google-genai Client using the configured API key."""
    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        logger.warning("GOOGLE_API_KEY is not defined in settings. Calls to Gemini may fail.")
        return genai.Client()
    return genai.Client(api_key=api_key)


def get_gemini_adk_model(model_name: str = "gemini-2.5-flash") -> Gemini:
    """Returns a Google ADK Gemini model instance for agent integration."""
    return Gemini(model=model_name)


async def generate_content(
    prompt: str,
    system_instruction: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.2,
) -> str:
    """Calls Gemini to generate plain-text content."""
    logger.info(f"Generating content using Gemini model: {model_name}")
    
    if not settings.GOOGLE_API_KEY:
        logger.warning("No GOOGLE_API_KEY set. Returning mock fallback response.")
        return f"Mock content response for: {prompt[:30]}..."
        
    try:
        client = get_genai_client()
        loop = asyncio.get_running_loop()
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            safety_settings=get_safety_settings()
        )
        
        def _call():
            return client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            
        response = await loop.run_in_executor(None, _call)
        return response.text or ""
        
    except Exception as e:
        logger.error(f"Gemini content generation failed: {e}", exc_info=True)
        if settings.APP_ENV == "development":
            return f"Error occurred but running in development. Details: {e}"
        raise


async def generate_structured_json(
    prompt: str,
    response_schema: Type[BaseModel],
    system_instruction: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """Sends a request to Gemini and returns parsed JSON matching the given Pydantic model schema."""
    logger.info(f"Generating structured JSON content for model: {response_schema.__name__}")
    
    if not settings.GOOGLE_API_KEY:
        logger.warning(
            "GOOGLE_API_KEY is not set. Gemini call skipped — returning mock fallback for %s. "
            "Set GOOGLE_API_KEY in your .env file to enable real AI analysis.",
            response_schema.__name__,
        )
        return _build_mock_dict(response_schema)
        
    try:
        client = get_genai_client()
        loop = asyncio.get_running_loop()
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_schema,
            safety_settings=get_safety_settings()
        )
        
        def _call():
            return client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            
        response = await loop.run_in_executor(None, _call)
        if not response.text:
            raise ValueError("Empty response received from Gemini.")
            
        return json.loads(response.text)
        
    except Exception as e:
        logger.error(f"Gemini structured generation failed: {e}", exc_info=True)
        if settings.APP_ENV == "development":
            logger.warning("Development mode: returning mock fallback for %s after error.", response_schema.__name__)
            return _build_mock_dict(response_schema)
        raise
