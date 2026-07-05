# =========================================================
# ApexDeploy - Security Agent
# Performs Bandit static analysis, secret scans, dependency audits, and scores risk
# =========================================================

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.core.base_agent import BaseAgent
from src.core.exceptions import AgentException
from src.llm.gemini_client import generate_structured_json
from src.llm.prompts import SECURITY_SYSTEM_INSTRUCTION, SECURITY_USER_PROMPT
from src.mcp import execute_command, write_file, read_file, search_files

logger = logging.getLogger("agents.security")


class Vulnerability(BaseModel):
    """Pydantic model for a single security vulnerability."""
    issue_type: str = Field(description="Type of vulnerability, e.g. hardcoded secret, XSS, insecure package.")
    file_path: str = Field(description="Relative path of file containing the vulnerability.")
    line_number: Optional[int] = Field(default=None, description="Line number where issue is found.")
    severity: str = Field(description="Severity score ('low', 'medium', 'high', 'critical').")
    description: str = Field(description="Explanation of the vulnerability details.")
    recommendation: str = Field(description="Actionable fix recommendation.")


class SecurityReport(BaseModel):
    """Pydantic model for the structured LLM security assessment report."""
    security_score: int = Field(description="Overall security score from 0 to 100.")
    security_status: str = Field(description="Overall status, 'passed' (score >= 70) or 'failed' (score < 70).")
    vulnerabilities: List[Vulnerability] = Field(default_factory=list, description="List of individual vulnerabilities.")
    secret_leaks: List[str] = Field(default_factory=list, description="List of exposed credentials, API keys, or certificates.")
    recommendations: List[str] = Field(default_factory=list, description="Actionable security recommendations.")


class SecurityAgent(BaseAgent):
    """SecurityAgent runs static vulnerability scans (Bandit) and custom secret scanners
    on repository checkouts, queries Gemini to compile structured scores, and generates reports.
    """

    def __init__(self):
        super().__init__("security")

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_run_id = context.get("pipeline_run_id")
        git_results = context.get("git_results", {})
        cloned_path = git_results.get("cloned_path")

        if not cloned_path:
            logger.warning("No cloned repository workspace found in context. Skipping security scans.")
            return {
                "security_score": 100,
                "security_status": "passed",
                "vulnerabilities": [],
                "secret_leaks": [],
                "recommendations": ["Skipped security review - no checkout path was provided."]
            }

        logger.info(f"SecurityAgent starting security analysis on workspace: {cloned_path}")
        workspace_dir = Path(cloned_path)

        # 1. Run Bandit Scan via Terminal MCP
        bandit_output = ""
        try:
            logger.info("Executing Bandit static analysis...")
            # We run bandit recursively on workspace folder. 
            # Exit codes 0 and 1 are expected successes for bandit (0 = no issues, 1 = issues found).
            exec_res = await execute_command(
                command="bandit -r . -f json",
                cwd=cloned_path,
                timeout=60
            )
            exit_code = exec_res.get("exit_code", -1)
            stdout = exec_res.get("stdout", "")
            
            if exit_code in [0, 1] and stdout:
                bandit_output = stdout
                logger.info("Bandit execution completed successfully.")
            else:
                logger.warning(f"Bandit scan exited with non-standard code: {exit_code}. Falling back to regex scanning.")
                bandit_output = f"Bandit scan skipped or failed (exit code: {exit_code})."
        except Exception as e:
            logger.error(f"Bandit execution crashed: {e}")
            bandit_output = f"Bandit analysis failed to run: {e}"

        # 2. Run Custom Regex Secret Scanner
        logger.info("Executing custom credential and secret scanner...")
        detected_secrets = self._scan_for_secrets(workspace_dir)

        # 3. Read dependency declarations
        logger.info("Analyzing package declarations...")
        dependency_info = self._audit_dependencies(workspace_dir)

        # 4. Formulate summary payload for Gemini analysis
        scan_payload = {
            "bandit_results": bandit_output[:5000],  # Truncated if massive to save tokens
            "secret_scans_detected": detected_secrets,
            "dependency_declarations": dependency_info
        }
        
        user_prompt = SECURITY_USER_PROMPT.format(
            scan_output=json.dumps(scan_payload, indent=2)
        )

        try:
            # 5. Call Gemini to format structured security assessment
            logger.info("Invoking Gemini for structured security risk analysis...")
            raw_report = await generate_structured_json(
                prompt=user_prompt,
                response_schema=SecurityReport,
                system_instruction=SECURITY_SYSTEM_INSTRUCTION
            )

            # Validate and convert back to dictionary
            report_data = SecurityReport(**raw_report).model_dump()

            # Enforce pipeline fail state if LLM score is below 70
            if report_data["security_score"] < 70:
                report_data["security_status"] = "failed"

            # 6. Save security report under artifacts folder
            artifact_file = f"./artifacts/{pipeline_run_id}/security_report.json"
            logger.info(f"Writing security JSON report to: {artifact_file}")
            write_file(
                filepath=artifact_file,
                content=json.dumps(report_data, indent=2)
            )

            return report_data

        except Exception as e:
            logger.error(f"SecurityAgent failed to compile risk report: {e}", exc_info=True)
            raise AgentException(
                f"SecurityAgent execution failed: {e}",
                details={"pipeline_run_id": pipeline_run_id}
            ) from e

    def _scan_for_secrets(self, workspace_path: Path) -> List[Dict[str, Any]]:
        """Scans workspace source files for hardcoded secrets, keys, and tokens using regex."""
        # Simple patterns matching key signatures
        patterns = {
            "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
            "Generic Key/Token": re.compile(r"(?:key|api_key|token|secret|password|passwd|private_key)\s*[:=]\s*['\"]([a-zA-Z0-9_\-\.\:\/]{16,})['\"]", re.IGNORECASE),
            "Slack OAuth Token": re.compile(r"xoxb-[0-9]{11,13}-[a-zA-Z0-9]{24}"),
            "Private Key Header": re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----")
        }

        leaks = []
        # Find python, javascript, environment, or config files
        extensions = ["*.py", "*.js", "*.ts", "*.json", "*.env", "*.yml", "*.yaml"]
        try:
            for ext in extensions:
                for file_path in workspace_path.rglob(ext):
                    # Skip common ignore paths
                    if any(part.startswith(".") for part in file_path.parts):
                        continue
                    if "node_modules" in file_path.parts or "venv" in file_path.parts or ".venv" in file_path.parts:
                        continue

                    if file_path.is_file():
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="replace")
                            for line_num, line in enumerate(content.splitlines(), 1):
                                # Exclude placeholders or standard imports/empty strings
                                if "placeholder" in line.lower() or "example" in line.lower() or "your-" in line.lower():
                                    continue
                                for name, pat in patterns.items():
                                    match = pat.search(line)
                                    if match:
                                        # Relative path for cleanliness
                                        rel_path = file_path.relative_to(workspace_path)
                                        # Mask the secret value for log safety
                                        val = match.group(0)
                                        masked = val[:6] + "..." + val[-4:] if len(val) > 10 else "******"
                                        leaks.append({
                                            "file_path": str(rel_path),
                                            "line_number": line_num,
                                            "type": name,
                                            "matched_line": line.strip()[:100],
                                            "masked_value": masked
                                        })
                        except Exception as read_err:
                            logger.debug(f"Secret scanner skipped reading {file_path}: {read_err}")
        except Exception as scan_err:
            logger.error(f"Secret scanner encountered errors walking path: {scan_err}")

        return leaks

    def _audit_dependencies(self, workspace_path: Path) -> Dict[str, Any]:
        """Reads dependency declaration files to supply stack list for security checks."""
        audit = {"requirements": [], "packages": []}
        
        req_file = workspace_path / "requirements.txt"
        if req_file.exists():
            try:
                lines = req_file.read_text(encoding="utf-8", errors="replace").splitlines()
                # Parse lines, strip version pin tags
                audit["requirements"] = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
            except Exception as e:
                logger.warning(f"Failed to read requirements.txt in security scan: {e}")

        pkg_file = workspace_path / "package.json"
        if pkg_file.exists():
            try:
                data = json.loads(pkg_file.read_text(encoding="utf-8", errors="replace"))
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                audit["packages"] = list(deps.keys()) + list(dev_deps.keys())
            except Exception as e:
                logger.warning(f"Failed to parse package.json in security scan: {e}")

        return audit
