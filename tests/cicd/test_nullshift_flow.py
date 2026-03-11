"""
End-to-end / CI integration tests for the NullShift patchflow.
All external I/O (LLM, GitHub, git) is mocked so these run offline.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestNullShiftPatchflow:
    def _make_llm_response(self, text: str = "def test_add():\n    assert 1+1==2\n"):
        resp = MagicMock()
        resp.choices[0].message.content = text
        return resp

    def test_full_flow_dry_run(self, tmp_path, simple_diff, mocker):
        """Full dry-run: detect → generate → write files (no git/GitHub)."""
        from patchwork.patchflows.NullShift.NullShift import NullShift

        # Patch OpenAI so we don't hit Groq
        mock_openai_cls = mocker.patch(
            "patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI"
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._make_llm_response()
        mock_openai_cls.return_value = mock_client

        inputs = {
            "pr_diff": simple_diff,
            "repo_path": str(tmp_path),
            "groq_api_key": "gsk_fake",
            "dry_run": True,
        }
        flow = NullShift(inputs)
        out = flow.run()

        assert isinstance(out["untested_functions"], list)
        assert out["pr_url"] == "dry_run" or out["pr_url"] == ""
        assert isinstance(out["written_files"], list)

    def test_no_functions_in_diff(self, tmp_path, mocker):
        """If the diff has no Python functions, no tests are generated."""
        from patchwork.patchflows.NullShift.NullShift import NullShift

        empty_diff = ""
        flow = NullShift(
            {
                "pr_diff": empty_diff,
                "repo_path": str(tmp_path),
                "groq_api_key": "gsk_fake",
                "dry_run": True,
            }
        )
        out = flow.run()
        assert out["untested_functions"] == []
        assert out["generated_tests"] == []
        assert out["written_files"] == []

    def test_already_tested_no_pr(self, tmp_path, simple_diff, repo_with_tests, mocker):
        """Functions with existing coverage should produce no output."""
        from patchwork.patchflows.NullShift.NullShift import NullShift

        flow = NullShift(
            {
                "pr_diff": simple_diff,
                "repo_path": str(repo_with_tests),
                "groq_api_key": "gsk_fake",
                "dry_run": True,
            }
        )
        out = flow.run()
        assert out["untested_functions"] == []
        assert out["pr_url"] == ""
