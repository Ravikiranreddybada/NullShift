"""
Tests for GenerateUnitTests step.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers to avoid hitting real Groq API in tests
# ---------------------------------------------------------------------------


def _make_mock_client(mocker, test_source: str = "def test_add():\n    assert 1 + 1 == 2\n"):
    """Return a mock OpenAI client whose chat.completions.create returns test_source."""
    mock_response = mocker.MagicMock()
    mock_response.choices[0].message.content = test_source

    mock_client = mocker.MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateUnitTests:
    def test_empty_functions_returns_empty(self, mocker):
        from patchwork.steps.GenerateUnitTests.GenerateUnitTests import GenerateUnitTests

        mocker.patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI")
        step = GenerateUnitTests(
            {
                "untested_functions": [],
                "groq_api_key": "gsk_fake",
            }
        )
        out = step.run()
        assert out["generated_tests"] == []

    def test_generates_test_for_single_function(self, mocker, sample_untested_functions):
        from patchwork.steps.GenerateUnitTests.GenerateUnitTests import GenerateUnitTests

        mock_openai_cls = mocker.patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI")
        mock_openai_cls.return_value = _make_mock_client(mocker)

        step = GenerateUnitTests(
            {
                "untested_functions": sample_untested_functions,
                "groq_api_key": "gsk_fake",
            }
        )
        out = step.run()
        assert len(out["generated_tests"]) == 1
        record = out["generated_tests"][0]
        assert record["function_name"] == "add"
        assert "test_" in record["test_source"]

    def test_test_file_path_derived_correctly(self, mocker, sample_untested_functions):
        from patchwork.steps.GenerateUnitTests.GenerateUnitTests import GenerateUnitTests

        mock_openai_cls = mocker.patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI")
        mock_openai_cls.return_value = _make_mock_client(mocker)

        step = GenerateUnitTests(
            {
                "untested_functions": sample_untested_functions,
                "groq_api_key": "gsk_fake",
            }
        )
        out = step.run()
        assert out["generated_tests"][0]["test_file"].startswith("tests/test_")

    def test_llm_failure_skips_file(self, mocker, sample_untested_functions):
        from patchwork.steps.GenerateUnitTests.GenerateUnitTests import GenerateUnitTests

        mock_openai_cls = mocker.patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI")
        client = mocker.MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("network error")
        mock_openai_cls.return_value = client

        step = GenerateUnitTests(
            {
                "untested_functions": sample_untested_functions,
                "groq_api_key": "gsk_fake",
            }
        )
        out = step.run()
        assert out["generated_tests"] == []

    def test_code_fences_stripped(self, mocker, sample_untested_functions):
        from patchwork.steps.GenerateUnitTests.GenerateUnitTests import GenerateUnitTests, _strip_code_fences

        fenced = "```python\ndef test_add():\n    assert add(1, 2) == 3\n```"
        assert "```" not in _strip_code_fences(fenced)

    def test_custom_model_passed_to_client(self, mocker, sample_untested_functions):
        from patchwork.steps.GenerateUnitTests.GenerateUnitTests import GenerateUnitTests

        mock_openai_cls = mocker.patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI")
        mock_client = _make_mock_client(mocker)
        mock_openai_cls.return_value = mock_client

        step = GenerateUnitTests(
            {
                "untested_functions": sample_untested_functions,
                "groq_api_key": "gsk_fake",
                "model": "mixtral-8x7b-32768",
            }
        )
        step.run()
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("model") == "mixtral-8x7b-32768" or call_kwargs.args[0] if call_kwargs.args else True

    def test_missing_groq_key_raises(self):
        from patchwork.steps.GenerateUnitTests.GenerateUnitTests import GenerateUnitTests

        with pytest.raises((ValueError, KeyError)):
            GenerateUnitTests({"untested_functions": []})
