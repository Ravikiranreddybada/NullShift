"""
End-to-end integration test for the NullShift patchflow.

The LLM call is mocked so no real API key is needed.
Git/GitHub operations are stubbed via dry_run=True.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from patchwork.patchflows.NullShift.NullShift import NullShift


@pytest.fixture()
def e2e_repo(tmp_path: Path) -> Path:
    """Create a repo with a new function that has no test coverage."""
    src = tmp_path / "patchwork"
    src.mkdir()
    (src / "calculator.py").write_text(
        textwrap.dedent(
            """\
            def multiply(a, b):
                \"\"\"Multiply two numbers.\"\"\"
                return a * b
            """
        )
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    return tmp_path


@pytest.fixture()
def e2e_diff() -> str:
    return textwrap.dedent(
        """\
        diff --git a/patchwork/calculator.py b/patchwork/calculator.py
        index 0000000..abcdef1 100644
        --- a/patchwork/calculator.py
        +++ b/patchwork/calculator.py
        @@ -0,0 +1,3 @@
        +def multiply(a, b):
        +    \"\"\"Multiply two numbers.\"\"\"
        +    return a * b
        """
    )


def _mock_llm_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestNullShiftPatchflow:
    def test_full_pipeline_dry_run(self, e2e_repo, e2e_diff):
        fake_tests = (
            "import pytest\n"
            "from patchwork.calculator import multiply\n\n"
            "def test_multiply():\n"
            "    assert multiply(2, 3) == 6\n"
            "    assert multiply(0, 5) == 0\n"
        )

        with patch(
            "patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI"
        ) as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.return_value = _mock_llm_response(fake_tests)

            patchflow = NullShift(
                {
                    "repo_path": str(e2e_repo),
                    "pr_diff": e2e_diff,
                    "openai_api_key": "sk-test",
                    "github_api_key": "ghp_test",
                    "dry_run": True,
                }
            )
            output = patchflow.run()

        # 1. Detection worked
        assert len(output["untested_functions"]) >= 1
        assert output["untested_functions"][0]["name"] == "multiply"

        # 2. Generation worked
        assert len(output["generated_tests"]) >= 1
        assert "test_multiply" in output["generated_tests"][0]["test_source"]

        # 3. Test file was written to disk
        assert len(output["test_files_written"]) >= 1
        written = e2e_repo / output["test_files_written"][0]
        assert written.exists()

        # 4. PR skipped because dry_run
        assert output["pr_url"] == ""

    def test_pipeline_no_changes_returns_empty(self, e2e_repo):
        patchflow = NullShift(
            {
                "repo_path": str(e2e_repo),
                "pr_diff": "",  # empty diff
                "openai_api_key": "sk-test",
                "github_api_key": "ghp_test",
                "dry_run": True,
            }
        )
        output = patchflow.run()

        assert output["untested_functions"] == []
        assert output["generated_tests"] == []
        assert output["test_files_written"] == []

    def test_pipeline_already_tested_skips_generation(self, tmp_path, e2e_diff):
        """If all changed functions are already tested, LLM should not be called."""
        src = tmp_path / "patchwork"
        src.mkdir()
        (src / "calculator.py").write_text("def multiply(a, b):\n    return a * b\n")
        tests = tmp_path / "tests"
        tests.mkdir()
        # Reference `multiply` in test file → it's "tested"
        (tests / "test_calculator.py").write_text(
            "from patchwork.calculator import multiply\ndef test_multiply(): assert multiply(2,3)==6\n"
        )

        with patch(
            "patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI"
        ) as MockOpenAI:
            patchflow = NullShift(
                {
                    "repo_path": str(tmp_path),
                    "pr_diff": e2e_diff,
                    "openai_api_key": "sk-test",
                    "github_api_key": "ghp_test",
                    "dry_run": True,
                }
            )
            output = patchflow.run()

        MockOpenAI.return_value.chat.completions.create.assert_not_called()
        assert output["generated_tests"] == []
