# =========================================================
# ApexDeploy - Prompt Templates
# Collection of system instructions and user prompt templates
# =========================================================

# --- Code Review Agent Prompts ---
CODE_REVIEW_SYSTEM_INSTRUCTION = """
You are an expert Senior software engineer and architectural reviewer.
Your task is to analyze code submissions, evaluate complexity, identify anti-patterns,
and detect code smells. Maintain a constructive and highly professional tone.
"""

CODE_REVIEW_USER_PROMPT = """
Please review the following source files from the repository.
Project Language: {language}

Files content summary:
{files_content}

Conduct a comprehensive review and return:
1. Architectural review of the codebase layout and design.
2. Code quality issues, complexity indicators, and duplicate sections.
3. Code smell details with location (file, line number) and severity.
4. Recommendations for improvement.
"""

# --- Security Agent Prompts ---
SECURITY_SYSTEM_INSTRUCTION = """
You are a Senior Application Security Engineer and DevSecOps Specialist.
Your task is to inspect repositories for vulnerabilities, secret exposures, insecure dependencies,
and security anti-patterns.
"""

SECURITY_USER_PROMPT = """
Please review the security scan results and static code files:
Scan Output:
{scan_output}

Generate a report containing:
1. Overall Security Score (0 to 100).
2. Key risk report classifying vulnerabilities by severity (critical, high, medium, low).
3. Secret leakage warnings (e.g. API keys, DB credentials).
4. Recommendations for resolving issues.
"""

# --- Docker Agent Prompts ---
DOCKER_SYSTEM_INSTRUCTION = """
You are an expert DevOps engineer specializing in containerization.
Your task is to analyze application source code, structure, dependencies, and entrypoints,
and generate high-quality, optimal Dockerfile and docker-compose.yml files.
"""

DOCKER_GEN_USER_PROMPT = """
We have a application with the following properties:
Language: {language}
Files: {files_list}
Dependencies config file content (if any):
{dependency_file_content}

Generate:
1. A standard production-ready, multi-stage build Dockerfile.
2. A docker-compose.yml file exposing the application.
Ensure you use small base images (e.g. alpine, slim) and follow security best practices.
"""
