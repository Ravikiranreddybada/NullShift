"""
Tests for DetectUntestedFunctions step.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from patchwork.steps.DetectUntestedFunctions.DetectUntestedFunctions import (
    DetectUntestedFunctions,
    _extract_functions,
    _find_tested_names,
    _parse_added_files,
)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


class TestParseAddedFiles:
    def test_extracts_python_file(self, simple_diff):
        result = _parse_added_files(simple_diff)
        assert "patchwork/utils.py" in result

    def test_ignores_non_python_files(self):
        diff = textwrap.dedent(
            """\
            diff --git a/README.md b/README.md
            index 0000000..1111111 100644
            --- a/README.md
            +++ b/README.md
            @@ -0,0 +1,2 @@
            +# Hello
            +World
            """
        )
        assert _parse_added_files(diff) == {}

    def test_empty_diff_returns_empty(self):
        assert _parse_added_files("") == {}

    def test_multiple_files(self, multi_function_diff):
        result = _parse_added_files(multi_function_diff)
        assert "patchwork/math_utils.py" in result


class TestExtractFunctions:
    def test_simple_function(self):
        source = "def add(a, b):\n    return a + b\n"
        fns = _extract_functions(source, "utils.py")
        assert len(fns) == 1
        assert fns[0]["name"] == "add"
        assert fns[0]["file"] == "utils.py"

    def test_multiple_functions(self):
        source = textwrap.dedent(
            """\
            def foo():
                pass

            def bar():
                pass
            """
        )
        fns = _extract_functions(source, "f.py")
        names = {f["name"] for f in fns}
        assert "foo" in names
        assert "bar" in names

    def test_invalid_syntax_returns_empty(self):
        fns = _extract_functions("def broken(:", "bad.py")
        assert fns == []

    def test_lineno_populated(self):
        source = "def add(a, b):\n    return a + b\n"
        fns = _extract_functions(source, "utils.py")
        assert fns[0]["lineno"] == 1


class TestFindTestedNames:
    def test_finds_tested_symbol(self, repo_with_tests: Path):
        names = _find_tested_names(repo_with_tests, ["tests"])
        assert "add" in names

    def test_no_tests_empty_set(self, tmp_path: Path):
        names = _find_tested_names(tmp_path, ["tests"])
        assert names == set()

    def test_missing_test_dir_returns_empty(self, tmp_path: Path):
        names = _find_tested_names(tmp_path, ["nonexistent"])
        assert names == set()


# ---------------------------------------------------------------------------
# Integration-style tests for the step itself
# ---------------------------------------------------------------------------


class TestDetectUntestedFunctions:
    def test_detects_untested_function(self, simple_diff, repo_with_source):
        step = DetectUntestedFunctions(
            {"pr_diff": simple_diff, "repo_path": str(repo_with_source)}
        )
        out = step.run()
        names = [f["name"] for f in out["untested_functions"]]
        assert "add" in names

    def test_skips_already_tested(self, simple_diff, repo_with_tests):
        step = DetectUntestedFunctions(
            {"pr_diff": simple_diff, "repo_path": str(repo_with_tests)}
        )
        out = step.run()
        # 'add' is already tested in repo_with_tests
        names = [f["name"] for f in out["untested_functions"]]
        assert "add" not in names

    def test_empty_diff_returns_empty(self, repo_with_source):
        step = DetectUntestedFunctions(
            {"pr_diff": "", "repo_path": str(repo_with_source)}
        )
        out = step.run()
        assert out["untested_functions"] == []

    def test_custom_test_directories(self, simple_diff, tmp_path):
        # Create a repo with test in a custom 'spec' directory
        src = tmp_path / "patchwork"
        src.mkdir()
        (src / "utils.py").write_text("def add(a, b):\n    return a + b\n")
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "test_utils.py").write_text("from patchwork.utils import add\ndef test_add(): assert add(1,2)==3\n")

        step = DetectUntestedFunctions(
            {"pr_diff": simple_diff, "repo_path": str(tmp_path), "test_directories": "spec"}
        )
        out = step.run()
        names = [f["name"] for f in out["untested_functions"]]
        assert "add" not in names

    def test_missing_required_key_raises(self):
        with pytest.raises((ValueError, KeyError)):
            DetectUntestedFunctions({})

    def test_multi_function_diff(self, multi_function_diff, tmp_path):
        step = DetectUntestedFunctions(
            {"pr_diff": multi_function_diff, "repo_path": str(tmp_path)}
        )
        out = step.run()
        names = [f["name"] for f in out["untested_functions"]]
        assert "multiply" in names
        assert "divide" in names
