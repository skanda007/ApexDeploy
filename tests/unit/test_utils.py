# =========================================================
# ApexDeploy - Unit Tests for Utilities
# Tests language detector, file scanning, and edge cases
# =========================================================

import pytest
from pathlib import Path

from src.utils.language_detector import detect_primary_language


# =========================================================
# LANGUAGE DETECTOR — CORE TESTS
# =========================================================

class TestLanguageDetectorCore:
    """Tests for the primary language detection function."""

    def test_detect_python_primary(self, tmp_path):
        """Verify Python detection when .py files dominate."""
        project = tmp_path / "py_project"
        project.mkdir()
        (project / "app.py").write_text("print('app')")
        (project / "utils.py").write_text("print('utils')")
        (project / "config.py").write_text("print('config')")
        (project / "style.css").write_text("body {}")  # Non-language file

        result = detect_primary_language(str(project))
        assert result == "python"

    def test_detect_javascript_primary(self, tmp_path):
        """Verify JavaScript detection when .js/.jsx files dominate."""
        project = tmp_path / "js_project"
        project.mkdir()
        (project / "index.js").write_text("console.log('test')")
        (project / "app.jsx").write_text("export default App")
        (project / "utils.js").write_text("module.exports = {}")

        result = detect_primary_language(str(project))
        assert result == "javascript"

    def test_detect_typescript_primary(self, tmp_path):
        """Verify TypeScript detection when .ts/.tsx files dominate."""
        project = tmp_path / "ts_project"
        project.mkdir()
        (project / "index.ts").write_text("const a: number = 1;")
        (project / "app.tsx").write_text("export default App")
        (project / "types.ts").write_text("interface Foo {}")
        (project / "config.ts").write_text("export const cfg = {};")

        result = detect_primary_language(str(project))
        assert result == "typescript"

    def test_detect_java_primary(self, tmp_path):
        """Verify Java detection when .java files dominate."""
        project = tmp_path / "java_project"
        project.mkdir()
        src_dir = project / "src" / "main" / "java"
        src_dir.mkdir(parents=True)
        (src_dir / "App.java").write_text("public class App {}")
        (src_dir / "Service.java").write_text("public class Service {}")

        result = detect_primary_language(str(project))
        assert result == "java"

    def test_detect_go_primary(self, tmp_path):
        """Verify Go detection when .go files dominate."""
        project = tmp_path / "go_project"
        project.mkdir()
        (project / "main.go").write_text('package main\nfunc main() {}')
        (project / "server.go").write_text("package main")

        result = detect_primary_language(str(project))
        assert result == "go"

    def test_detect_rust_primary(self, tmp_path):
        """Verify Rust detection when .rs files dominate."""
        project = tmp_path / "rust_project"
        project.mkdir()
        (project / "main.rs").write_text("fn main() {}")
        (project / "lib.rs").write_text("pub fn hello() {}")

        result = detect_primary_language(str(project))
        assert result == "rust"

    def test_detect_csharp_primary(self, tmp_path):
        """Verify C# detection when .cs files dominate."""
        project = tmp_path / "csharp_project"
        project.mkdir()
        (project / "Program.cs").write_text("using System;")
        (project / "Startup.cs").write_text("public class Startup {}")

        result = detect_primary_language(str(project))
        assert result == "csharp"

    def test_detect_ruby_primary(self, tmp_path):
        """Verify Ruby detection when .rb files dominate."""
        project = tmp_path / "ruby_project"
        project.mkdir()
        (project / "app.rb").write_text("puts 'hello'")
        (project / "config.rb").write_text("Config.setup")

        result = detect_primary_language(str(project))
        assert result == "ruby"

    def test_detect_php_primary(self, tmp_path):
        """Verify PHP detection when .php files dominate."""
        project = tmp_path / "php_project"
        project.mkdir()
        (project / "index.php").write_text("<?php echo 'hello'; ?>")
        (project / "router.php").write_text("<?php // router ?>")

        result = detect_primary_language(str(project))
        assert result == "php"

    def test_detect_cpp_primary(self, tmp_path):
        """Verify C++ detection when .cpp/.cc files dominate."""
        project = tmp_path / "cpp_project"
        project.mkdir()
        (project / "main.cpp").write_text("#include <iostream>")
        (project / "utils.cc").write_text("void helper() {}")

        result = detect_primary_language(str(project))
        assert result == "cpp"

    def test_detect_c_primary(self, tmp_path):
        """Verify C detection when .c files dominate."""
        project = tmp_path / "c_project"
        project.mkdir()
        (project / "main.c").write_text("#include <stdio.h>")
        (project / "lib.c").write_text("int add(int a, int b) { return a+b; }")

        result = detect_primary_language(str(project))
        assert result == "c"


# =========================================================
# LANGUAGE DETECTOR — EDGE CASES
# =========================================================

class TestLanguageDetectorEdgeCases:
    """Tests for edge cases and boundary scenarios in language detection."""

    def test_empty_directory_returns_python(self, tmp_path):
        """Verify fallback to Python when directory is empty."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = detect_primary_language(str(empty_dir))
        assert result == "python"

    def test_nonexistent_directory_returns_python(self, tmp_path):
        """Verify fallback to Python when directory does not exist."""
        result = detect_primary_language(str(tmp_path / "nonexistent"))
        assert result == "python"

    def test_only_non_source_files_returns_python(self, tmp_path):
        """Verify fallback to Python when only non-source files are present."""
        project = tmp_path / "docs_only"
        project.mkdir()
        (project / "README.md").write_text("# README")
        (project / "LICENSE").write_text("MIT")
        (project / "config.yml").write_text("key: value")
        (project / "data.json").write_text("{}")

        result = detect_primary_language(str(project))
        assert result == "python"

    def test_ignores_node_modules(self, tmp_path):
        """Verify that node_modules directories are excluded from scanning."""
        project = tmp_path / "mixed"
        project.mkdir()
        (project / "app.py").write_text("print('python')")

        nm_dir = project / "node_modules" / "express"
        nm_dir.mkdir(parents=True)
        # Create 100 JS files in node_modules (should be ignored)
        for i in range(100):
            (nm_dir / f"module_{i}.js").write_text(f"// module {i}")

        result = detect_primary_language(str(project))
        assert result == "python"

    def test_ignores_venv_directories(self, tmp_path):
        """Verify that venv/.venv directories are excluded from scanning."""
        project = tmp_path / "venv_project"
        project.mkdir()
        (project / "main.js").write_text("console.log('primary')")

        venv_dir = project / ".venv" / "lib" / "python3.12"
        venv_dir.mkdir(parents=True)
        for i in range(50):
            (venv_dir / f"module_{i}.py").write_text(f"# module {i}")

        result = detect_primary_language(str(project))
        assert result == "javascript"

    def test_ignores_hidden_directories(self, tmp_path):
        """Verify that hidden directories (starting with .) are excluded."""
        project = tmp_path / "hidden_dirs"
        project.mkdir()
        (project / "app.py").write_text("print('main')")

        git_dir = project / ".git" / "objects"
        git_dir.mkdir(parents=True)
        for i in range(20):
            (git_dir / f"pack_{i}.c").write_text("// git internal")

        result = detect_primary_language(str(project))
        assert result == "python"

    def test_tie_breaking_uses_first_max(self, tmp_path):
        """Verify that when file counts are tied, max() returns a consistent winner."""
        project = tmp_path / "tied"
        project.mkdir()
        (project / "a.py").write_text("print('py')")
        (project / "b.js").write_text("console.log('js')")

        result = detect_primary_language(str(project))
        # With tied counts, max() returns the first key inserted with max value
        # Both are valid since it's implementation-defined
        assert result in ("python", "javascript")

    def test_nested_source_files_counted(self, tmp_path):
        """Verify that deeply nested source files are counted correctly."""
        project = tmp_path / "nested"
        project.mkdir()

        deep_dir = project / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)
        (deep_dir / "core.py").write_text("# deep module")
        (project / "main.py").write_text("# entry")
        (project / "index.js").write_text("// one JS file")

        result = detect_primary_language(str(project))
        assert result == "python"  # 2 py vs 1 js

    def test_case_insensitive_extensions(self, tmp_path):
        """Verify extensions are compared case-insensitively."""
        project = tmp_path / "case_test"
        project.mkdir()
        (project / "App.PY").write_text("print('upper')")
        (project / "Utils.Py").write_text("print('mixed')")

        result = detect_primary_language(str(project))
        assert result == "python"


# =========================================================
# LANGUAGE DETECTOR — MULTI-LANGUAGE PROJECTS
# =========================================================

class TestLanguageDetectorMultiLanguage:
    """Tests for projects with mixed languages."""

    def test_python_dominant_over_js(self, tmp_path):
        """Verify Python wins when it has more files than JavaScript."""
        project = tmp_path / "multi_1"
        project.mkdir()
        (project / "app.py").write_text("print('a')")
        (project / "models.py").write_text("class M: pass")
        (project / "views.py").write_text("def v(): pass")
        (project / "index.js").write_text("console.log()")

        result = detect_primary_language(str(project))
        assert result == "python"

    def test_js_dominant_over_python(self, tmp_path):
        """Verify JavaScript wins when it has more files than Python."""
        project = tmp_path / "multi_2"
        project.mkdir()
        (project / "app.py").write_text("print('a')")
        (project / "index.js").write_text("console.log()")
        (project / "app.js").write_text("module.exports = {}")
        (project / "utils.js").write_text("function foo() {}")

        result = detect_primary_language(str(project))
        assert result == "javascript"

    def test_java_dominant_in_maven_project(self, sample_java_project):
        """Verify Java detection in a Maven project structure."""
        result = detect_primary_language(str(sample_java_project))
        assert result == "java"

    def test_node_project_language(self, sample_node_project):
        """Verify JavaScript detection in a Node.js project."""
        result = detect_primary_language(str(sample_node_project))
        assert result == "javascript"

    def test_python_project_language(self, sample_python_project):
        """Verify Python detection in a Flask project."""
        result = detect_primary_language(str(sample_python_project))
        assert result == "python"
