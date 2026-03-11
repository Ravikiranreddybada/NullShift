"""
GenerateUnitTests
=================
Takes the list of untested functions produced by ``DetectUntestedFunctions``
and calls an LLM to generate ``pytest``-compatible unit tests for each one.

The step renders a prompt for each function, calls the OpenAI-compatible
endpoint, and returns the generated test source strings grouped by file.

Inputs (TypedDict)
------------------
- ``untested_functions`` : list[dict]  – from DetectUntestedFunctions
- ``openai_api_key``     : str         – OpenAI (or compatible) API key
- ``model``              : str         – model name (default: gpt-4o-mini)
- ``client_base_url``    : str         – optional custom endpoint
- ``max_tokens``         : int         – max tokens per LLM call (default 2048)

Outputs (TypedDict)
-------------------
- ``generated_tests``    : list[dict]  – each entry:
    - ``source_file``    : original source file (repo-relative)
    - ``test_file``      : suggested test file path
    - ``test_source``    : generated pytest source code
    - ``function_name``  : name of the function under test
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Dict, List, Optional

from typing_extensions import TypedDict

from patchwork.common.constants import DEFAULT_BASE_URL, DEFAULT_MAX_TOKENS, DEFAULT_MODEL
from patchwork.step import Step, StepStatus

# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------


class GenerateUnitTestsInputs(TypedDict, total=False):
    untested_functions: List[Dict]
    openai_api_key: str
    model: str
    client_base_url: str
    max_tokens: int


class GenerateUnitTestsOutputs(TypedDict):
    generated_tests: List[Dict]


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = textwrap.dedent(
    """\
    You are an expert Python software engineer specialising in test-driven
    development.  Your task is to write comprehensive ``pytest`` unit tests.

    Rules:
    - Use pytest fixtures and parametrize where appropriate.
    - Mock external dependencies (network, filesystem, databases) with
      ``unittest.mock`` or ``pytest-mock``.
    - Cover: happy path, edge cases, and expected exceptions.
    - Output ONLY valid Python source code – no markdown fences, no prose.
    - Start with the required imports, then the test functions.
    - Each test function name must start with ``test_``.
    """
)

_USER_PROMPT_TEMPLATE = textwrap.dedent(
    """\
    Generate pytest unit tests for the following Python function.

    File: {file}
    {class_context}
    Function source:
    ```python
    {source}
    ```

    Write thorough tests.  Output only Python code.
    """
)


def _build_user_prompt(func_info: Dict) -> str:
    class_context = (
        f"Class: {func_info['class_name']}" if func_info.get("class_name") else ""
    )
    return _USER_PROMPT_TEMPLATE.format(
        file=func_info["file"],
        class_context=class_context,
        source=func_info["source"],
    )


def _suggest_test_file(source_file: str) -> str:
    """Convert ``patchwork/steps/foo.py`` → ``tests/steps/test_foo.py``."""
    p = Path(source_file)
    parts = list(p.parts)
    # strip leading src/package dir if present
    test_name = f"test_{p.stem}.py"
    if len(parts) > 1:
        return str(Path("tests") / Path(*parts[1:-1]) / test_name)
    return str(Path("tests") / test_name)


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------


class GenerateUnitTests(
    Step,
    input_class=GenerateUnitTestsInputs,
    output_class=GenerateUnitTestsOutputs,
):
    """
    Calls an LLM to generate pytest unit tests for each untested function.
    """

    def __init__(self, inputs: Dict):
        super().__init__(inputs)
        self.untested_functions: List[Dict] = inputs.get("untested_functions", [])
        self.api_key: Optional[str] = inputs.get("openai_api_key")
        self.model: str = inputs.get("model", DEFAULT_MODEL)
        self.base_url: Optional[str] = inputs.get("client_base_url", DEFAULT_BASE_URL)
        self.max_tokens: int = int(inputs.get("max_tokens", DEFAULT_MAX_TOKENS))

    def _call_llm(self, user_prompt: str) -> str:
        """Call the OpenAI-compatible API and return the response text."""
        from openai import OpenAI

        kwargs: Dict = {"api_key": self.api_key or "no-key"}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        client = OpenAI(**kwargs)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    def run(self) -> Dict:
        from patchwork.logger import logger

        if not self.untested_functions:
            self.set_status(StepStatus.SKIPPED, "No untested functions to generate tests for.")
            return {"generated_tests": []}

        generated: List[Dict] = []

        for func_info in self.untested_functions:
            func_name = func_info["name"]
            logger.info(f"Generating tests for: {func_name} ({func_info['file']})")

            try:
                prompt = _build_user_prompt(func_info)
                test_source = self._call_llm(prompt)

                # Strip accidental markdown fences
                if test_source.startswith("```"):
                    lines = test_source.splitlines()
                    test_source = "\n".join(
                        l for l in lines if not l.startswith("```")
                    )

                generated.append(
                    {
                        "source_file": func_info["file"],
                        "test_file": _suggest_test_file(func_info["file"]),
                        "test_source": test_source.strip(),
                        "function_name": func_name,
                        "class_name": func_info.get("class_name"),
                    }
                )
                logger.info(f"  ✓ Tests generated for {func_name}")

            except Exception as exc:
                logger.warning(f"  ✗ Failed to generate tests for {func_name}: {exc}")
                self.set_status(StepStatus.WARNING, str(exc))

        logger.info(f"GenerateUnitTests: generated tests for {len(generated)} function(s).")
        return {"generated_tests": generated}
