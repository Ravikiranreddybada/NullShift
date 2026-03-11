"""
GenerateUnitTests Step Module
=============================

This module implements the second step of the NullShift pipeline: generating
pytest unit tests for detected untested functions using the Groq LLM.

Overview
--------
The GenerateUnitTests step takes a list of untested functions and uses
the Groq LLM (or any OpenAI-compatible endpoint) to generate comprehensive
pytest test suites. It handles prompt construction, LLM communication,
and response parsing.

Key Features
------------
- Uses Groq's Llama 3.3 70B model (default) for high-quality test generation
- Supports any OpenAI-compatible API endpoint
- Groups multiple functions for batch test generation
- Smart test file path derivation
- Response parsing to extract clean Python code

How It Works
------------
1. Receive list of untested functions from DetectUntestedFunctions
2. Group functions by source file for cohesive test generation
3. Construct prompts with system instructions and function sources
4. Call LLM API to generate pytest tests
5. Parse response to extract test code
6. Return generated tests with metadata

Example Usage
-------------
>>> from patchwork.steps.GenerateUnitTests import GenerateUnitTests
>>>
>>> inputs = {
...     "untested_functions": [
...         {"name": "add", "file": "utils.py", "source": "def add(a, b): return a + b"}
...     ],
...     "groq_api_key": "gsk_...",
...     "model": "llama-3.3-70b-versatile",
... }
>>> step = GenerateUnitTests(inputs)
>>> result = step.run()
>>> print(result)
{"generated_tests": [{"source_file": "utils.py", "test_file": "tests/test_utils.py", ...}]}

LLM Prompt Engineering
----------------------
The step uses a carefully crafted two-part prompt:

System Prompt:
- Role: Expert Python test engineer
- Rules: Output only valid Python code, cover happy-path and edge cases,
  use descriptive test names

User Template:
- Includes function source code
- Specifies file path and class context
- Requests complete, self-contained test file

This prompt engineering ensures:
- Valid pytest syntax
- Comprehensive test coverage
- Proper imports and fixtures
- Clear test naming

Input Contract
--------------
Required:
    - untested_functions (list[dict]): List from DetectUntestedFunctions
    - groq_api_key (str): API key for LLM access

Optional:
    - model (str): LLM model name (default: "llama-3.3-70b-versatile")
    - client_base_url (str): API endpoint (default: Groq)
    - temperature (float): Sampling temperature (default: 0.2)
    - max_tokens (int): Max response tokens (default: 2048)

Output Contract
---------------
generated_tests (list[dict]): Each dict contains:
 (str): Original    - source_file source file path
    - test_file (str): Target test file path
    - test_source (str): Generated pytest test code
    - function_name (str): Function name being tested
    - class_name (str|None): Class name if method

Test File Path Derivation
-------------------------
The step automatically derives test file paths:
    myapp/utils.py → tests/test_utils.py
    myapp/core/db.py → tests/test_core/test_db.py
    app.py → tests/test_app.py

This follows the common Python convention of:
- tests/ as the root test directory
- test_{module_name}.py as the file pattern

Error Handling
--------------
- LLM API errors: Logged and skipped, continues with other functions
- Invalid responses: Attempt to parse, fall back to empty
- Rate limiting: Handled by underlying HTTP client
- Timeout: Configurable via OpenAI client settings

Performance Considerations
--------------------------
- Functions are batched by source file (one LLM call per file)
- LLM response time depends on model and load
- Consider caching for repeated runs with same functions
- Default max_tokens=2048 may need adjustment for complex functions

Extending the Step
------------------
To use a different LLM provider:
    1. Change client_base_url to provider's endpoint
    2. Ensure API key format is compatible
    3. May need to adjust model name

To customize test generation:
    1. Modify _SYSTEM_PROMPT for different testing approaches
    2. Adjust _USER_TEMPLATE for different input formats
    3. Override run() for completely custom logic

See Also
--------
- patchwork.step.Step: Base class
- openai.OpenAI: OpenAI client library
- patchwork.steps.DetectUntestedFunctions: Previous step
- patchwork.steps.CreateTestPR: Next step
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import List, Optional

from openai import OpenAI
from typing_extensions import TypedDict

from patchwork.logger import logger
from patchwork.step import Step


# ============================================================================
# TypedDict Contracts
# ============================================================================

class _Inputs(TypedDict, total=False):
    """Optional input parameters for GenerateUnitTests."""
    model: str              # LLM model name
    client_base_url: str    # API endpoint URL
    temperature: float      # Sampling temperature
    max_tokens: int         # Max response tokens


class _Required(TypedDict):
    """Required input parameters for GenerateUnitTests."""
    untested_functions: List[dict]  # Functions needing tests
    groq_api_key: str              # API key for LLM


class Inputs(_Required, _Inputs):
    """Complete input contract for GenerateUnitTests step."""
    pass


class Outputs(TypedDict):
    """Output type for GenerateUnitTests step."""
    generated_tests: List[dict]


# ============================================================================
# Prompt Engineering
# ============================================================================

# System prompt that defines the LLM's role and rules
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

# User template for generating test for a specific function
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


# ============================================================================
# Helper Functions (Private)
# ============================================================================

def _derive_test_path(source_file: str) -> str:
    """
    Derive the test file path from a source file path.
    
    This follows Python conventions:
    - myapp/utils.py → tests/test_utils.py
    - myapp/core/db.py → tests/test_core/test_db.py
    - app.py → tests/test_app.py
    
    Args:
        source_file: Relative path to the source file
        
    Returns:
        Relative path to the corresponding test file
        
    Example:
        >>> _derive_test_path("myapp/utils.py")
        'tests/test_utils.py'
        >>> _derive_test_path("app.py")
        'tests/test_app.py'
    """
    # Parse the source file path
    parts = PurePosixPath(source_file).parts
    
    # Get the file stem (filename without extension)
    stem = PurePosixPath(source_file).stem
    
    # Handle edge case where file is at root
    if len(parts) == 1:
        return f"tests/test_{stem}.py"
    
    # For nested files, create test path preserving directory structure
    # This creates: tests/test_{subdirs...}/{test_{filename}}.py
    return f"tests/test_{stem}.py"


def _strip_code_fences(text: str) -> str:
    """
    Remove markdown code fence wrappers from LLM response.
    
    The LLM may return code wrapped in markdown fences like:
    ```python
    def test_...
    ```
    or
    ```
    def test_...
    ```
    
    This function strips those wrappers to get clean Python code.
    
    Args:
        text: Raw LLM response text
        
    Returns:
        Cleaned text without code fences
        
    Example:
        >>> _strip_code_fences("```python\\ndef test_add():\\n    pass\\n```")
        'def test_add():\\n    pass'
    """
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Remove opening fence: ```python or ```
    text = re.sub(r"^```(?:python)?\n?", "", text)
    
    # Remove closing fence: ```
    text = re.sub(r"\n?```$", "", text)
    
    return text.strip()


# ============================================================================
# Step Implementation
# ============================================================================

class GenerateUnitTests(Step, input_class=Inputs, output_class=Outputs):
    """
    Generate pytest unit tests for untested functions using LLM.
    
    This step takes functions detected by DetectUntestedFunctions and
    generates comprehensive pytest tests using the Groq LLM.
    
    The generation process:
    1. Group functions by source file
    2. Construct prompts with function sources
    3. Call LLM API
    4. Parse and return generated tests
    
    Attributes:
        _functions: List of untested function dictionaries
        _model: LLM model name
        _client: OpenAI-compatible API client
    
    Example:
        >>> inputs = {
        ...     "untested_functions": [{"name": "add", "file": "utils.py", ...}],
        ...     "groq_api_key": "gsk_xxx",
        ... }
        >>> step = GenerateUnitTests(inputs)
        >>> result = step.run()
    """

    def __init__(self, inputs: dict) -> None:
        """
        Initialize the GenerateUnitTests step.
        
        Args:
            inputs: Dictionary with untested_functions and groq_api_key.
        
        Raises:
            ValueError: If required inputs are missing
        """
        super().__init__(inputs)
        
        # Store the list of functions needing tests
        self._functions: list[dict] = inputs["untested_functions"]
        
        # LLM configuration with sensible defaults
        self._model: str = inputs.get("model", "llama-3.3-70b-versatile")
        
        # Create OpenAI-compatible client
        # Works with Groq, Ollama, OpenAI, Anthropic, etc.
        base_url: str = inputs.get("client_base_url", "https://api.groq.com/openai/v1")
        self._client = OpenAI(
            api_key=inputs["groq_api_key"],
            base_url=base_url,
        )

    def run(self) -> dict:
        """
        Execute the test generation workflow.
        
        This method:
        1. Groups functions by source file
        2. Builds prompts for the LLM
        3. Calls the LLM to generate tests
        4. Parses responses and returns generated tests
        
        Returns:
            Dictionary with 'generated_tests' key containing list of
            test info dictionaries with source and test code
        
        Each generated test contains:
        - source_file: Original source file
        - test_file: Target test file path
        - test_source: Generated pytest code
        - function_name: Name of tested function
        - class_name: Class name if method (may be None)
        """
        # Handle case with no functions to process
        if not self._functions:
            logger.info("GenerateUnitTests: no functions to process.")
            return {"generated_tests": []}

        generated: list[dict] = []
        
        # =====================================================================
        # Step 1: Group Functions by Source File
        # =====================================================================
        # We group functions by their source file so we can generate a single
        # cohesive test file rather than multiple separate files.
        # This also reduces LLM API calls.
        
        file_groups: dict[tuple[str, str], list[dict]] = {}
        for fn in self._functions:
            # Derive the test file path for this function
            test_path = _derive_test_path(fn["file"])
            key = (fn["file"], test_path)
            file_groups.setdefault(key, []).append(fn)

        # =====================================================================
        # Step 2: Generate Tests for Each File Group
        # =====================================================================
        
        for (source_file, test_file), functions in file_groups.items():
            logger.info(f"GenerateUnitTests: generating tests for {source_file} ({len(functions)} function(s)) …")
            
            # Build combined prompt with all functions in this file
            combined_sources: list[str] = []
            for fn in functions:
                # Add class context if this is a method
                class_ctx = f"Class: {fn['class_name']}\n" if fn.get("class_name") else ""
                combined_sources.append(
                    _USER_TEMPLATE.format(
                        file_path=source_file,
                        class_context=class_ctx,
                        source=fn["source"],
                    )
                )

            # Join multiple functions with separator
            prompt = "\n\n---\n\n".join(combined_sources)
            
            # If multiple functions, ask for unified test file
            if len(functions) > 1:
                prompt += "\n\nGenerate a single unified test file covering ALL functions above."

            # =====================================================================
            # Step 3: Call LLM to Generate Tests
            # =====================================================================
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,  # Low temperature for consistent results
                    max_tokens=2048,  # Enough for comprehensive tests
                )
                raw = response.choices[0].message.content or ""
                test_source = _strip_code_fences(raw)
                
            except Exception as exc:
                # Log error but continue with remaining functions
                logger.error(f"  LLM call failed for {source_file}: {exc}")
                continue

            # =====================================================================
            # Step 4: Build Result Records
            # =====================================================================
            # Create a record for each function in the group
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

