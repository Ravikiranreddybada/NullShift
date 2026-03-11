"""
GenerateUnitTests
=================
For every untested function detected by ``DetectUntestedFunctions``, calls the
Groq-compatible LLM and produces a pytest test file.

Inputs
------
untested_functions : list[dict]
    Output from DetectUntestedFunctions.
groq_api_key : str
    Groq API key (``gsk_...``).  Can be any valid OpenAI-compatible key when
    combined with a custom ``client_base_url``.
model : str, optional
    LLM model name.  Defaults to ``llama-3.3-70b-versatile``.
client_base_url : str, optional
    Base URL for the OpenAI-compatible endpoint.
    Defaults to ``https://api.groq.com/openai/v1``.

Outputs
-------
generated_tests : list[dict]
    Each entry has keys: ``source_file``, ``test_file``, ``test_source``,
    ``function_name``, ``class_name``.
"""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import List, Optional

from openai import OpenAI
from typing_extensions import TypedDict

from patchwork.logger import logger
from patchwork.step import Step

# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------


class _Inputs(TypedDict, total=False):
    model: str
    client_base_url: str


class _Required(TypedDict):
    untested_functions: List[dict]
    groq_api_key: str


class Inputs(_Required, _Inputs):
    pass


class Outputs(TypedDict):
    generated_tests: List[dict]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert Python test engineer. Given a Python function, write a \
comprehensive pytest test suite for it.

Rules:
- Output ONLY valid Python code — no markdown fences, no explanations.
- Start with necessary imports (e.g. ``import pytest`` and the module import).
- Cover happy-path, edge cases, and error cases where applicable.
- Use descriptive test function names prefixed with ``test_``.
- Do NOT import from __future__ at the top-level unless strictly required.
"""

_USER_TEMPLATE = """\
Generate pytest unit tests for the following Python function.

File: {file_path}
{class_context}
Function source:
```python
{source}
```

Produce a complete, self-contained test file.
"""


def _derive_test_path(source_file: str) -> str:
    """Convert e.g. ``patchwork/utils.py`` → ``tests/test_utils.py``."""
    parts = PurePosixPath(source_file).parts
    # Drop first directory if it looks like a package root
    stem = PurePosixPath(source_file).stem
    return f"tests/test_{stem}.py"


def _strip_code_fences(text: str) -> str:
    """Remove ```python … ``` or plain ``` … ``` wrapping if present."""
    text = text.strip()
    text = re.sub(r"^```(?:python)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------


class GenerateUnitTests(Step, input_class=Inputs, output_class=Outputs):
    """Call an LLM to write pytest tests for each untested function."""

    def __init__(self, inputs: dict):
        super().__init__(inputs)
        self._functions: list[dict] = inputs["untested_functions"]
        self._model: str = inputs.get("model", "llama-3.3-70b-versatile")
        base_url: str = inputs.get("client_base_url", "https://api.groq.com/openai/v1")
        self._client = OpenAI(
            api_key=inputs["groq_api_key"],
            base_url=base_url,
        )

    def run(self) -> dict:
        if not self._functions:
            logger.info("GenerateUnitTests: no functions to process.")
            return {"generated_tests": []}

        generated: list[dict] = []
        # Group by (source_file, test_file) so we can merge multiple functions into one file
        file_groups: dict[tuple[str, str], list[dict]] = {}
        for fn in self._functions:
            test_path = _derive_test_path(fn["file"])
            key = (fn["file"], test_path)
            file_groups.setdefault(key, []).append(fn)

        for (source_file, test_file), functions in file_groups.items():
            logger.info(f"GenerateUnitTests: generating tests for {source_file} ({len(functions)} function(s)) …")
            combined_sources: list[str] = []
            for fn in functions:
                class_ctx = f"Class: {fn['class_name']}\n" if fn.get("class_name") else ""
                combined_sources.append(
                    _USER_TEMPLATE.format(
                        file_path=source_file,
                        class_context=class_ctx,
                        source=fn["source"],
                    )
                )

            prompt = "\n\n---\n\n".join(combined_sources)
            if len(functions) > 1:
                prompt += "\n\nGenerate a single unified test file covering ALL functions above."

            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=2048,
                )
                raw = response.choices[0].message.content or ""
                test_source = _strip_code_fences(raw)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"  LLM call failed for {source_file}: {exc}")
                continue

            for fn in functions:
                generated.append(
                    {
                        "source_file": source_file,
                        "test_file": test_file,
                        "test_source": test_source,
                        "function_name": fn["name"],
                        "class_name": fn.get("class_name"),
                    }
                )

        logger.info(f"GenerateUnitTests: produced {len(generated)} test record(s).")
        return {"generated_tests": generated}
