"""
Tests for patchwork.steps.CreateTestPR
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from patchwork.steps.CreateTestPR.CreateTestPR import (
    CreateTestPR,
    _build_pr_body,
    _merge_test_files,
)


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


class TestBuildPrBody:
    def test_contains_function_name(self, sample_generated_tests):
        body = _build_pr_body(sample_generated_tests)
        assert "add" in body

    def test_contains_source_file(self, sample_generated_tests):
        body = _build_pr_body(sample_generated_tests)
        assert "patchwork/utils.py" in body

    def test_includes_nullshift_branding(self, sample_generated_tests):
        body = _build_pr_body(sample_generated_tests)
        assert "NullShift" in body

    def test_includes_class_prefix_when_method(self):
        tests = [
            {
                "source_file": "module.py",
                "test_file": "tests/test_module.py",
                "test_source": "def test_it(): pass",
                "function_name": "my_method",
                "class_name": "MyClass",
            }
        ]
        body = _build_pr_body(tests)
        assert "MyClass.my_method" in body


class TestMergeTestFiles:
    def test_single_entry_unchanged(self, sample_generated_tests):
        merged = _merge_test_files(sample_generated_tests)
        assert "tests/test_utils.py" in merged

    def test_two_entries_same_file_merged(self):
        tests = [
            {
                "test_file": "tests/test_utils.py",
                "test_source": "def test_add(): pass",
                "function_name": "add",
                "source_file": "patchwork/utils.py",
            },
            {
                "test_file": "tests/test_utils.py",
                "test_source": "def test_sub(): pass",
                "function_name": "sub",
                "source_file": "patchwork/utils.py",
            },
        ]
        merged = _merge_test_files(tests)
        assert len(merged) == 1
        combined = merged["tests/test_utils.py"]
        assert "test_add" in combined
        assert "test_sub" in combined

    def test_different_files_kept_separate(self):
        tests = [
            {
                "test_file": "tests/test_a.py",
                "test_source": "def test_a(): pass",
                "function_name": "a",
                "source_file": "patchwork/a.py",
            },
            {
                "test_file": "tests/test_b.py",
                "test_source": "def test_b(): pass",
                "function_name": "b",
                "source_file": "patchwork/b.py",
            },
        ]
        merged = _merge_test_files(tests)
        assert len(merged) == 2


# ---------------------------------------------------------------------------
# Step integration tests
# ---------------------------------------------------------------------------


class TestCreateTestPRStep:
    def test_writes_test_file(self, tmp_path, sample_generated_tests):
        step = CreateTestPR(
            {
                "generated_tests": sample_generated_tests,
                "repo_path": str(tmp_path),
                "github_api_key": "ghp_test",
                "dry_run": True,
            }
        )
        output = step.run()

        assert len(output["test_files_written"]) == 1
        written_path = tmp_path / output["test_files_written"][0]
        assert written_path.exists()
        assert "test_add" in written_path.read_text()

    def test_dry_run_skips_git_and_pr(self, tmp_path, sample_generated_tests):
        with patch("patchwork.steps.CreateTestPR.CreateTestPR.git") as mock_git, \
             patch("patchwork.steps.CreateTestPR.CreateTestPR.Github"):
            step = CreateTestPR(
                {
                    "generated_tests": sample_generated_tests,
                    "repo_path": str(tmp_path),
                    "github_api_key": "ghp_test",
                    "dry_run": True,
                }
            )
            output = step.run()

        mock_git.Repo.assert_not_called()
        assert output["pr_url"] == ""

    def test_skips_when_no_generated_tests(self, tmp_path):
        step = CreateTestPR(
            {
                "generated_tests": [],
                "repo_path": str(tmp_path),
                "github_api_key": "ghp_test",
                "dry_run": True,
            }
        )
        output = step.run()
        assert output["test_files_written"] == []
        assert output["pr_url"] == ""

    def test_appends_to_existing_test_file(self, tmp_path, sample_generated_tests):
        existing_tests = tmp_path / "tests"
        existing_tests.mkdir()
        existing_file = existing_tests / "test_utils.py"
        existing_file.write_text("# existing tests\ndef test_old(): pass\n")

        step = CreateTestPR(
            {
                "generated_tests": sample_generated_tests,
                "repo_path": str(tmp_path),
                "github_api_key": "ghp_test",
                "dry_run": True,
            }
        )
        step.run()

        content = existing_file.read_text()
        assert "test_old" in content
        assert "test_add" in content

    def test_branch_name_contains_prefix(self, tmp_path, sample_generated_tests):
        step = CreateTestPR(
            {
                "generated_tests": sample_generated_tests,
                "repo_path": str(tmp_path),
                "github_api_key": "ghp_test",
                "dry_run": True,
                "pr_branch_prefix": "myorg/auto-tests",
            }
        )
        output = step.run()
        assert output["branch_name"].startswith("myorg/auto-tests")

    def test_output_required_keys_present(self, tmp_path, sample_generated_tests):
        step = CreateTestPR(
            {
                "generated_tests": sample_generated_tests,
                "repo_path": str(tmp_path),
                "github_api_key": "ghp_test",
                "dry_run": True,
            }
        )
        output = step.run()
        assert "pr_url" in output
        assert "test_files_written" in output
        assert "branch_name" in output
