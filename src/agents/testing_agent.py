# =========================================================
# ApexDeploy - Testing Agent
# Automatically detects language, runs test suites, collects coverage & logs
# =========================================================

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict

from src.core.base_agent import BaseAgent
from src.core.exceptions import AgentException
from src.mcp import execute_command, write_file

logger = logging.getLogger("agents.testing")


class TestingAgent(BaseAgent):
    """TestingAgent detects Python, Node.js, or Java test setups in workspace directories,
    invokes appropriate test commands via Terminal MCP, extracts result metrics, and writes reports.
    """

    # We set __test__ = False to prevent Pytest from treating this class as a test collection target.
    __test__ = False

    def __init__(self):
        super().__init__("testing")

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_run_id = context.get("pipeline_run_id")
        git_results = context.get("git_results", {})
        cloned_path = git_results.get("cloned_path")

        if not cloned_path:
            logger.warning("No cloned repository workspace found in context. Skipping tests.")
            return {
                "test_status": "passed",
                "framework_detected": "none",
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "tests_skipped": 0,
                "coverage_percentage": None,
                "execution_time_seconds": 0.0,
                "failures": [],
                "logs": "Skipped testing - no checkout path was provided."
            }

        logger.info(f"TestingAgent scanning workspace: {cloned_path}")
        workspace_dir = Path(cloned_path)

        # 1. Automatically detect stack type
        framework = "pytest"
        command = "pytest"

        # Check Node.js
        if (workspace_dir / "package.json").exists():
            framework = "npm"
            command = "npm test"
        # Check Java Maven
        elif (workspace_dir / "pom.xml").exists():
            framework = "maven"
            command = "mvn test"
        # Python defaults
        else:
            # Check for virtual environment pytest runner
            venv_pytest = workspace_dir / ".venv" / "Scripts" / "pytest.exe"
            if not venv_pytest.exists():
                venv_pytest = workspace_dir / ".venv" / "bin" / "pytest"
            
            if venv_pytest.exists():
                command = f"{venv_pytest} --tb=short"
            else:
                command = "pytest --tb=short"

        logger.info(f"Detected framework: {framework}. Executing test command: {command}")

        # 2. Run test execution
        try:
            exec_res = await execute_command(
                command=command,
                cwd=cloned_path,
                timeout=120
            )

            exit_code = exec_res.get("exit_code", -1)
            stdout = exec_res.get("stdout", "")
            stderr = exec_res.get("stderr", "")
            duration = exec_res.get("duration_seconds", 0.0)

            # Combine output streams for log collections
            logs = f"=== STDOUT ===\n{stdout}\n=== STDERR ===\n{stderr}"

            # 3. Parse test run outputs
            metrics = self._parse_test_output(framework, stdout, stderr, exit_code, duration)

            # Determine overall pass/fail status
            # Exit code 0 implies success. Pytest code 5 means no tests collected (we allow it as passed)
            if exit_code in [0, 5] and metrics["tests_failed"] == 0:
                test_status = "passed"
            else:
                test_status = "failed"

            report = {
                "test_status": test_status,
                "framework_detected": framework,
                "tests_run": metrics["tests_run"],
                "tests_passed": metrics["tests_passed"],
                "tests_failed": metrics["tests_failed"],
                "tests_skipped": metrics["tests_skipped"],
                "coverage_percentage": metrics["coverage_percentage"],
                "execution_time_seconds": round(duration, 2),
                "failures": metrics["failures"],
                "logs": logs
            }

            # 4. Save testing report under artifacts folder
            artifact_file = f"./artifacts/{pipeline_run_id}/testing_report.json"
            logger.info(f"Writing test execution JSON report to: {artifact_file}")
            write_file(
                filepath=artifact_file,
                content=json.dumps(report, indent=2)
            )

            return report

        except Exception as e:
            logger.error(f"TestingAgent failed to execute tests: {e}", exc_info=True)
            raise AgentException(
                f"TestingAgent execution failed: {e}",
                details={"pipeline_run_id": pipeline_run_id}
            ) from e

    def _parse_test_output(
        self,
        framework: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration: float
    ) -> Dict[str, Any]:
        """Parses stdout/stderr outputs to extract pass/fail counts and coverage metrics."""
        metrics = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_skipped": 0,
            "coverage_percentage": None,
            "failures": []
        }

        # Handle process failures or empty logs
        if not stdout and not stderr:
            metrics["failures"].append("Test execution output stream was empty.")
            return metrics

        combined = f"{stdout}\n{stderr}"

        if framework == "pytest":
            # Extract standard pytest counts
            # Look for summary line: e.g. "=== 22 passed, 2 warnings in 14.81s ==="
            passed_match = re.search(r"(\d+)\s+passed", combined)
            failed_match = re.search(r"(\d+)\s+failed", combined)
            skipped_match = re.search(r"(\d+)\s+skipped", combined)
            error_match = re.search(r"(\d+)\s+error", combined)

            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            skipped = int(skipped_match.group(1)) if skipped_match else 0
            errors = int(error_match.group(1)) if error_match else 0

            # Sum errors as failed tests
            failed_total = failed + errors

            # Fallback for no tests ran
            if "collected 0 items" in combined or "no tests ran" in combined:
                passed = 0
                failed_total = 0

            metrics["tests_passed"] = passed
            metrics["tests_failed"] = failed_total
            metrics["tests_skipped"] = skipped
            metrics["tests_run"] = passed + failed_total + skipped

            # Parse coverage percentage: look for TOTAL line
            # TOTAL                               1204    932  22.59%
            cov_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", combined)
            if cov_match:
                metrics["coverage_percentage"] = float(cov_match.group(1))
            else:
                # Look for custom coverage summary logs
                cov_alt_match = re.search(r"Total coverage:\s*([\d.]+)%", combined)
                if cov_alt_match:
                    metrics["coverage_percentage"] = float(cov_alt_match.group(1))

        elif framework == "npm":
            # Extract NPM Jest/Mocha style outputs
            # Mocha: "11 passing (12s)"
            mocha_pass = re.search(r"(\d+)\s+passing", combined)
            mocha_fail = re.search(r"(\d+)\s+failing", combined)
            
            # Jest: "Tests:       1 failed, 12 passed, 13 total"
            jest_match = re.search(r"Tests:\s*(?:(\d+)\s+failed,\s*)?(?:(\d+)\s+passed,\s*)?(\d+)\s+total", combined)

            if jest_match:
                failed = int(jest_match.group(1)) if jest_match.group(1) else 0
                passed = int(jest_match.group(2)) if jest_match.group(2) else 0
                metrics["tests_failed"] = failed
                metrics["tests_passed"] = passed
                metrics["tests_run"] = int(jest_match.group(3))
            elif mocha_pass or mocha_fail:
                passed = int(mocha_pass.group(1)) if mocha_pass else 0
                failed = int(mocha_fail.group(1)) if mocha_fail else 0
                metrics["tests_passed"] = passed
                metrics["tests_failed"] = failed
                metrics["tests_run"] = passed + failed

        elif framework == "maven":
            # Maven surefire pattern: "Tests run: 12, Failures: 0, Errors: 0, Skipped: 0"
            mvn_match = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)", combined)
            if mvn_match:
                run = int(mvn_match.group(1))
                failed = int(mvn_match.group(2))
                errors = int(mvn_match.group(3))
                skipped = int(mvn_match.group(4))
                metrics["tests_run"] = run
                metrics["tests_failed"] = failed + errors
                metrics["tests_skipped"] = skipped
                metrics["tests_passed"] = max(0, run - (failed + errors + skipped))

        # Populate basic failures logs if exit code != 0
        if exit_code not in [0, 5] and metrics["tests_failed"] == 0:
            metrics["failures"].append(f"Test command exited with non-zero exit code: {exit_code}")
        elif metrics["tests_failed"] > 0:
            metrics["failures"].append(f"Detected {metrics['tests_failed']} test failure(s) in execution output.")

        return metrics
