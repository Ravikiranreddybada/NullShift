"""
Tests for patchwork.steps.DetectUntestedFunctions
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from patchwork.steps.DetectUntestedFunctions.DetectUntestedFunctions import (
    DetectUntestedFunctions,
    _collect_function_names_from_diff,
    _collect_tested_names,
    _extract_changed_files,
    _parse_functions_from_file,
)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestExtractChangedFiles:
    def test_extracts_py_file(self, simple_diff):
        files = _extract_changed_files(simple_diff)
        assert "patchwork/utils.py" in files

    def test_ignores_non_python(self):
        diff = "+++ b/README.md\n"
        assert _extract_changed_files(diff) == []

    def test_empty_diff(self):
        assert _extract_changed_files("") == []

    def test_multiple_files(self, multi_function_diff):
        files = _extract_changed_files(multi_function_diff)
        assert len(files) >= 1


class TestCollectFunctionNamesFromDiff:
    def test_finds_added_function(self, simple_diff):
        names = _collect_function_names_from_diff(simple_diff)
        assert "add" in names

    def test_finds_multiple_functions(self, multi_function_diff):
        names = _collect_function_names_from_diff(multi_function_diff)
        assert "multiply" in names
        assert "divide" in names

    def test_empty_diff_returns_empty_set(self):
        assert _collect_function_names_from_diff("") == set()

    def test_ignores_removed_lines(self):
        diff = "-def old_function():\n-    pass\n"
        names = _collect_function_names_from_diff(diff)
        assert "old_function" not in names

    def test_ignores_context_lines(self):
        diff = " def context_function():\n     pass\n"
        names = _collect_function_names_from_diff(diff)
        assert "context_function" not in names


class TestParseFunctionsFromFile:
    def test_parses_simple_function(self, tmp_path):
        f = tmp_path / "utils.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        funcs = _parse_functions_from_file(f)
        assert len(funcs) == 1
        assert funcs[0]["name"] == "add"
        assert funcs[0]["lineno"] == 1

    def test_parses_method_with_class_name(self, tmp_path):
        f = tmp_path / "cls.py"
        f.write_text(
            textwrap.dedent(
                """\
                class MyClass:
                    def my_method(self):
                        pass
                """
            )
        )
        funcs = _parse_functions_from_file(f)
        names = [fn["name"] for fn in funcs]
        assert "my_method" in names

    def test_returns_empty_on_syntax_error(self, tmp_path):
        f = tmp_path / "broken.py"
        f.write_text("def broken(\n")
        assert _parse_functions_from_file(f) == []

    def test_includes_source_snippet(self, tmp_path):
        f = tmp_path / "utils.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        funcs = _parse_functions_from_file(f)
        assert "return a + b" in funcs[0]["source"]


class TestCollectTestedNames:
    def test_finds_referenced_name(self, repo_with_tests):
        tested = _collect_tested_names(repo_with_tests, ["tests"])
        assert "add" in tested

    def test_returns_empty_when_no_test_dir(self, tmp_path):
        tested = _collect_tested_names(tmp_path, ["tests"])
        assert tested == set()

    def test_collects_method_attributes(self, tmp_path):
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_x.py").write_text("obj.my_method()\n")
        tested = _collect_tested_names(tmp_path, ["tests"])
        assert "my_method" in tested


# ---------------------------------------------------------------------------
# Integration tests for DetectUntestedFunctions step
# ---------------------------------------------------------------------------


class TestDetectUntestedFunctionsStep:
    def test_detects_untested_function(self, repo_with_source, simple_diff):
        step = DetectUntestedFunctions(
            {
                "repo_path": str(repo_with_source),
                "pr_diff": simple_diff,
            }
        )
        output = step.run()
        names = [f["name"] for f in output["untested_functions"]]
        assert "add" in names

    def test_skips_already_tested_function(self, repo_with_tests, simple_diff):
        step = DetectUntestedFunctions(
            {
                "repo_path": str(repo_with_tests),
                "pr_diff": simple_diff,
            }
        )
        output = step.run()
        names = [f["name"] for f in output["untested_functions"]]
        assert "add" not in names

    def test_empty_diff_returns_empty_list(self, repo_with_source):
        step = DetectUntestedFunctions(
            {
                "repo_path": str(repo_with_source),
                "pr_diff": "",
            }
        )
        output = step.run()
        assert output["untested_functions"] == []

    def test_output_contains_required_keys(self, repo_with_source, simple_diff):
        step = DetectUntestedFunctions(
            {
                "repo_path": str(repo_with_source),
                "pr_diff": simple_diff,
            }
        )
        output = step.run()
        for func in output["untested_functions"]:
            assert "name" in func
            assert "file" in func
            assert "lineno" in func
            assert "source" in func

    def test_custom_test_directory(self, tmp_path, simple_diff):
        src = tmp_path / "patchwork"
        src.mkdir()
        (src / "utils.py").write_text("def add(a, b):\n    return a + b\n")
        custom_tests = tmp_path / "spec"
        custom_tests.mkdir()
        (custom_tests / "test_utils.py").write_text("add(1, 2)\n")

        step = DetectUntestedFunctions(
            {
                "repo_path": str(tmp_path),
                "pr_diff": simple_diff,
                "test_directories": ["spec"],
            }
        )
        output = step.run()
        # `add` is referenced in `spec/`, so should not appear as untested
        names = [f["name"] for f in output["untested_functions"]]
        assert "add" not in names
