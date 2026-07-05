# =========================================================
# ApexDeploy - Code Review Agent
# LLM-powered source analysis, architecture review, and code smell detection
# =========================================================

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.core.base_agent import BaseAgent
from src.core.exceptions import AgentException
from src.llm.gemini_client import generate_structured_json
from src.llm.prompts import CODE_REVIEW_SYSTEM_INSTRUCTION, CODE_REVIEW_USER_PROMPT
from src.mcp import read_file, search_files, write_file

logger = logging.getLogger("agents.code_review")


class CodeSmell(BaseModel):
    """Pydantic model for a single code quality issue."""
    file_path: str = Field(description="Relative path of the source file containing the issue.")
    line_number: Optional[int] = Field(default=None, description="Line number of the issue.")
    severity: str = Field(description="Classification of severity (low, medium, high).")
    description: str = Field(description="Explanation of the issue or code smell.")
    recommendation: str = Field(description="Actionable suggestion to resolve the issue.")


class CodeReviewReport(BaseModel):
    """Pydantic model for the unified structured LLM code review report."""
    review_status: str = Field(description="Review pass/fail status ('passed' or 'failed').")
    complexity_score: str = Field(description="Overall code complexity classification ('low', 'medium', 'high').")
    duplicate_code_detected: bool = Field(description="True if major duplicate block duplications exist.")
    architecture_summary: str = Field(description="Architectural design layout and structure comments.")
    code_smells: List[CodeSmell] = Field(default_factory=list, description="List of detected code smells.")
    suggestions: List[str] = Field(default_factory=list, description="List of general recommendations.")


class CodeReviewAgent(BaseAgent):
    """CodeReviewAgent reads target programming source files from checkout workspaces,
    calls Gemini to produce structured code reviews, and writes review artifacts.
    """

    def __init__(self):
        super().__init__("code_review")

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_run_id = context.get("pipeline_run_id")
        git_results = context.get("git_results", {})
        cloned_path = git_results.get("cloned_path")
        language = git_results.get("language", "python").lower()

        if not cloned_path:
            logger.warning("No cloned repository workspace found in context. Skipping code review.")
            return {
                "review_status": "passed",
                "complexity_score": "low",
                "duplicate_code_detected": False,
                "architecture_summary": "Skipped code review - no checkout path was provided.",
                "code_smells": [],
                "suggestions": []
            }

        logger.info(f"CodeReviewAgent scanning directory: {cloned_path} (Language: {language})")

        try:
            # 1. Map target file search patterns based on detected language
            patterns = ["**/*.py"]
            if language in ["javascript", "typescript"]:
                patterns = ["**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
            elif language == "java":
                patterns = ["**/*.java"]
            elif language == "go":
                patterns = ["**/*.go"]
            
            # Find files inside sandbox
            all_files: List[str] = []
            for pattern in patterns:
                found = search_files(dir_path=cloned_path, pattern=pattern)
                all_files.extend(found)

            # 2. Read file contents up to token/size limits (max 10 files, max 8KB per file)
            logger.info(f"Found {len(all_files)} files matching extension patterns.")
            selected_files = all_files[:10]
            
            files_payload = []
            for file_path in selected_files:
                try:
                    # Make path relative to cloned directory for prompt clarity
                    rel_path = Path(file_path).relative_to(Path(cloned_path))
                    content = read_file(filepath=file_path)
                    
                    # Truncate very long files to save context window space
                    lines = content.splitlines()
                    if len(lines) > 150:
                        content = "\n".join(lines[:150]) + "\n... [TRUNCATED] ..."
                        
                    files_payload.append(f"--- File: {rel_path} ---\n{content}\n")
                except Exception as file_err:
                    logger.warning(f"Skipping file {file_path} in prompt formulation: {file_err}")

            if not files_payload:
                logger.info("No matching source code files could be loaded. Passing code review.")
                return {
                    "review_status": "passed",
                    "complexity_score": "low",
                    "duplicate_code_detected": False,
                    "architecture_summary": "Passed code review - no source files found to evaluate.",
                    "code_smells": [],
                    "suggestions": []
                }

            files_content_str = "\n".join(files_payload)

            # 3. Formulate prompt and invoke Gemini with output structure schema
            user_prompt = CODE_REVIEW_USER_PROMPT.format(
                language=language,
                files_content=files_content_str
            )

            logger.info("Invoking Gemini for structured code review...")
            raw_report = await generate_structured_json(
                prompt=user_prompt,
                response_schema=CodeReviewReport,
                system_instruction=CODE_REVIEW_SYSTEM_INSTRUCTION
            )

            # Validate and convert back to dictionary
            report_data = CodeReviewReport(**raw_report).model_dump()

            # 4. Save code review result under artifacts folder
            artifact_file = f"./artifacts/{pipeline_run_id}/code_review.json"
            logger.info(f"Writing code review JSON artifact to: {artifact_file}")
            write_file(
                filepath=artifact_file,
                content=json.dumps(report_data, indent=2)
            )

            return report_data

        except Exception as e:
            logger.error(f"CodeReviewAgent execution failed: {e}", exc_info=True)
            raise AgentException(
                f"CodeReviewAgent execution failed: {e}",
                details={"pipeline_run_id": pipeline_run_id}
            ) from e
