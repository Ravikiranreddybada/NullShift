"""
Tests for patchwork.steps.GenerateUnitTests
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from patchwork.steps.GenerateUnitTests.GenerateUnitTests import (
    GenerateUnitTests,
    _build_user_prompt,
    _suggest_test_file,
)


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


class TestSuggestTestFile:
    @pytest.mark.parametrize(
        "source_file, expected",
        [
            ("patchwork/utils.py", "tests/utils/test_utils.py"),
            ("utils.py", "tests/test_utils.py"),
            ("patchwork/steps/foo.py", "tests/steps/test_foo.py"),
        ],
    )
    def test_suggest_test_file(self, source_file, expected):
        result = _suggest_test_file(source_file)
        # The function name must be preserved
        assert "test_" in result
        assert result.endswith(".py")

    def test_always_under_tests_dir(self):
        result = _suggest_test_file("patchwork/app.py")
        assert result.startswith("tests/")


class TestBuildUserPrompt:
    def test_contains_function_source(self, sample_untested_functions):
        func = sample_untested_functions[0]
        prompt = _build_user_prompt(func)
        assert func["source"] in prompt

    def test_contains_file_name(self, sample_untested_functions):
        func = sample_untested_functions[0]
        prompt = _build_user_prompt(func)
        assert func["file"] in prompt

    def test_includes_class_context(self):
        func = {
            "name": "my_method",
            "file": "module.py",
            "lineno": 5,
            "source": "def my_method(self):\n    pass",
            "class_name": "MyClass",
        }
        prompt = _build_user_prompt(func)
        assert "MyClass" in prompt

    def test_no_class_context_when_none(self, sample_untested_functions):
        func = sample_untested_functions[0]
        prompt = _build_user_prompt(func)
        assert "Class:" not in prompt


# ---------------------------------------------------------------------------
# Step integration tests (LLM calls are mocked)
# ---------------------------------------------------------------------------


class TestGenerateUnitTestsStep:
    def _make_mock_response(self, content: str):
        """Build a fake OpenAI response object."""
        choice = MagicMock()
        choice.message.content = content
        response = MagicMock()
        response.choices = [choice]
        return response

    def test_generates_test_for_single_function(self, sample_untested_functions):
        fake_test_code = "import pytest\n\ndef test_add():\n    assert add(1, 2) == 3\n"

        with patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.return_value = self._make_mock_response(
                fake_test_code
            )

            step = GenerateUnitTests(
                {
                    "untested_functions": sample_untested_functions,
                    "openai_api_key": "test-key",
                }
            )
            output = step.run()

        assert len(output["generated_tests"]) == 1
        assert output["generated_tests"][0]["test_source"] == fake_test_code
        assert output["generated_tests"][0]["function_name"] == "add"

    def test_strips_markdown_fences(self, sample_untested_functions):
        fenced = "```python\ndef test_add():\n    assert True\n```"
        expected = "def test_add():\n    assert True"

        with patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.return_value = self._make_mock_response(fenced)

            step = GenerateUnitTests(
                {
                    "untested_functions": sample_untested_functions,
                    "openai_api_key": "test-key",
                }
            )
            output = step.run()

        assert output["generated_tests"][0]["test_source"] == expected

    def test_skips_when_no_untested_functions(self):
        step = GenerateUnitTests(
            {
                "untested_functions": [],
                "openai_api_key": "test-key",
            }
        )
        output = step.run()
        assert output["generated_tests"] == []

    def test_handles_llm_error_gracefully(self, sample_untested_functions):
        with patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.side_effect = RuntimeError("API error")

            step = GenerateUnitTests(
                {
                    "untested_functions": sample_untested_functions,
                    "openai_api_key": "test-key",
                }
            )
            output = step.run()

        # Should not raise; should return empty list with WARNING status
        assert output["generated_tests"] == []

    def test_uses_custom_model(self, sample_untested_functions):
        with patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.return_value = self._make_mock_response(
                "def test_add(): pass"
            )

            step = GenerateUnitTests(
                {
                    "untested_functions": sample_untested_functions,
                    "openai_api_key": "test-key",
                    "model": "gpt-4o",
                }
            )
            step.run()

            call_kwargs = instance.chat.completions.create.call_args
            assert call_kwargs.kwargs["model"] == "gpt-4o"

    def test_output_contains_required_keys(self, sample_untested_functions):
        with patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.return_value = self._make_mock_response(
                "def test_add(): pass"
            )
            step = GenerateUnitTests(
                {"untested_functions": sample_untested_functions, "openai_api_key": "k"}
            )
            output = step.run()

        for entry in output["generated_tests"]:
            assert "source_file" in entry
            assert "test_file" in entry
            assert "test_source" in entry
            assert "function_name" in entry
