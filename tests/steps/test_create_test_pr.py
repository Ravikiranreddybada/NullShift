"""
Tests for CreateTestPR step.
"""
from __future__ import annotations

from pathlib import Path

import pytest


class TestCreateTestPR:
    def test_dry_run_writes_files(self, tmp_path, sample_generated_tests):
        from patchwork.steps.CreateTestPR.CreateTestPR import CreateTestPR

        step = CreateTestPR(
            {
                "generated_tests": sample_generated_tests,
                "repo_path": str(tmp_path),
                "dry_run": True,
            }
        )
        out = step.run()
        assert out["pr_url"] == "dry_run"
        assert len(out["written_files"]) == 1
        written_path = tmp_path / out["written_files"][0]
        assert written_path.exists()
        assert "test_add" in written_path.read_text()

    def test_empty_tests_returns_empty(self, tmp_path):
        from patchwork.steps.CreateTestPR.CreateTestPR import CreateTestPR

        step = CreateTestPR(
            {
                "generated_tests": [],
                "repo_path": str(tmp_path),
                "dry_run": True,
            }
        )
        out = step.run()
        assert out["pr_url"] == ""
        assert out["written_files"] == []

    def test_test_directory_created(self, tmp_path, sample_generated_tests):
        from patchwork.steps.CreateTestPR.CreateTestPR import CreateTestPR

        step = CreateTestPR(
            {
                "generated_tests": sample_generated_tests,
                "repo_path": str(tmp_path),
                "dry_run": True,
            }
        )
        step.run()
        tests_dir = tmp_path / "tests"
        assert tests_dir.is_dir()

    def test_no_github_key_raises_when_not_dry_run(self, tmp_path, sample_generated_tests):
        from patchwork.steps.CreateTestPR.CreateTestPR import CreateTestPR

        step = CreateTestPR(
            {
                "generated_tests": sample_generated_tests,
                "repo_path": str(tmp_path),
                "dry_run": False,
            }
        )
        with pytest.raises(ValueError, match="github_api_key"):
            step.run()

    def test_multiple_functions_same_file_written_once(self, tmp_path):
        from patchwork.steps.CreateTestPR.CreateTestPR import CreateTestPR

        tests = [
            {
                "source_file": "patchwork/utils.py",
                "test_file": "tests/test_utils.py",
                "test_source": "def test_add(): assert 1+1==2\n",
                "function_name": "add",
                "class_name": None,
            },
            {
                "source_file": "patchwork/utils.py",
                "test_file": "tests/test_utils.py",
                "test_source": "def test_add(): assert 1+1==2\ndef test_sub(): assert 2-1==1\n",
                "function_name": "sub",
                "class_name": None,
            },
        ]
        step = CreateTestPR(
            {
                "generated_tests": tests,
                "repo_path": str(tmp_path),
                "dry_run": True,
            }
        )
        out = step.run()
        # Should only write one file, not two
        assert len(out["written_files"]) == 1
