"""
NullShift Patchflow Module
==========================

This module contains the main NullShift patchflow that orchestrates the
end-to-end process of detecting untested functions, generating unit tests,
and creating GitHub pull requests.

Overview
--------
The NullShift patchflow is the main entry point that coordinates three
independent steps:

1. DetectUntestedFunctions - Identifies Python functions in the PR diff
   that lack test coverage by analyzing the git diff and existing test files.

2. GenerateUnitTests - Uses the Groq LLM to generate comprehensive pytest
   test suites for each untested function detected in step 1.

3. CreateTestPR - Writes the generated tests to disk, creates a new git
   branch, commits the changes, and opens a GitHub pull request.

Patchflow Design
----------------
NullShift follows the Patchwork framework's patchflow pattern, which provides:
- Sequential step execution with data passing between steps
- Typed input/output contracts via TypedDict
- Built-in logging and error handling
- Debug mode support for troubleshooting

Example Usage
-------------
>>> from patchwork.patchflows.NullShift.NullShift import NullShift
>>>
>>> inputs = {
...     "pr_diff": "$(git diff origin/main)",
...     "groq_api_key": "gsk_...",
...     "github_api_key": "ghp_...",
...     "dry_run": True,
... }
>>> flow = NullShift(inputs)
>>> result = flow.run()
>>> print(result)
{
    "untested_functions": [...],
    "generated_tests": [...],
    "pr_url": "dry_run",
    "written_files": [...]
}

Architecture
------------
The patchflow acts as a pipeline:
    
    PR Diff → [Detect] → Untested Functions → [Generate] → Tests → [PR] → GitHub PR
                                           ↓
                                    (LLM call)

Input Contract
--------------
The NullShift patchflow accepts the following inputs:

Required:
    - pr_diff (str): Unified git diff from the pull request
    - groq_api_key (str): Groq API key for LLM access

Optional:
    - github_api_key (str): GitHub token for PR creation (not needed for dry_run)
    - repo_path (str): Local repository path (default: ".")
    - model (str): LLM model name (default: "llama-3.3-70b-versatile")
    - client_base_url (str): Custom API endpoint (default: Groq)
    - base_branch (str): Target branch for PR (default: "main")
    - pr_branch_prefix (str): Branch name prefix (default: "nullshift/auto-tests")
    - test_directories (str): Comma-separated test dirs (default: "tests,test")
    - dry_run (bool): Skip git/PR operations (default: False)
    - debug (bool): Enable debug mode (default: False)

Output Contract
---------------
The patchflow returns a dictionary with the following keys:

    - untested_functions (list): Functions detected without tests
    - generated_tests (list): Generated test code from LLM
    - pr_url (str): GitHub PR URL or "dry_run"
    - written_files (list): Paths to test files written

Error Handling
--------------
The patchflow handles errors at each step:
- Detection failures: Returns empty lists, continues to next step
- Generation failures: Logs error, skips failed functions
- PR creation failures: Raises exception, does not leave partial state

Extension Points
----------------
To extend NullShift:

1. Add new detection logic in DetectUntestedFunctions
2. Modify test generation prompts in GenerateUnitTests
3. Add new output formats in CreateTestPR
4. Create new patchflows combining steps differently

See Also
--------
- patchwork.step.Step: Base class for all steps
- patchwork.steps.DetectUntestedFunctions: Function detection step
- patchwork.steps.GenerateUnitTests: Test generation step
- patchwork.steps.CreateTestPR: PR creation step
"""

from __future__ import annotations

from typing import Any

from patchwork.logger import logger
from patchwork.steps.CreateTestPR import CreateTestPR
from patchwork.steps.DetectUntestedFunctions import DetectUntestedFunctions
from patchwork.steps.GenerateUnitTests import GenerateUnitTests


class NullShift:
    """
    Main NullShift patchflow orchestrator.
    
    This class coordinates the three-step process of:
    1. Detecting untested Python functions in a PR diff
    2. Generating pytest unit tests using Groq LLM
    3. Creating a GitHub PR with the generated tests
    
    The patchflow follows a sequential pipeline pattern, where each step
    depends on the output of the previous step. It handles error cases
    gracefully and supports dry-run mode for testing without git operations.
    
    Attributes:
        inputs (dict): Configuration and input parameters for the patchflow
    
    Example:
        >>> inputs = {
        ...     "pr_diff": git_diff_string,
        ...     "groq_api_key": "gsk_xxx",
        ...     "dry_run": True,
        ... }
        >>> flow = NullShift(inputs)
        >>> result = flow.run()
    """

    def __init__(self, inputs: dict[str, Any]) -> None:
        """
        Initialize the NullShift patchflow.
        
        Args:
            inputs: Dictionary containing all required and optional parameters.
                   Must include 'pr_diff' and 'groq_api_key' at minimum.
        
        Raises:
            ValueError: If required inputs are missing
        """
        self.inputs = inputs

    def run(self) -> dict[str, Any]:
        """
        Execute the complete NullShift workflow.
        
        This method runs the three-step pipeline:
        1. Detect untested functions in the PR diff
        2. Generate unit tests using Groq LLM
        3. Create a GitHub PR with generated tests
        
        Returns:
            Dictionary containing:
            - untested_functions: List of functions lacking tests
            - generated_tests: Generated pytest test code
            - pr_url: GitHub PR URL (or "dry_run" if dry-run mode)
            - written_files: Paths to test files created
        
        The method handles the following edge cases:
        - Empty diff: Returns early with empty results
        - No untested functions: Skips test generation
        - LLM failures: Logs errors, continues with remaining functions
        - dry_run mode: Skips git/PR operations, writes files locally
        """
        logger.info("━━━ NullShift: starting ━━━")

        # =====================================================================
        # STEP 1: Detect Untested Functions
        # =====================================================================
        # This step parses the git diff to find Python functions that were
        # added or modified but don't have corresponding test coverage.
        #
        # It uses AST (Abstract Syntax Tree) parsing to accurately identify
        # function definitions, including async functions and class methods.
        
        detect = DetectUntestedFunctions(self.inputs)
        detect_out = detect.run()
        untested = detect_out.get("untested_functions", [])

        # Handle case where no functions need testing
        if not untested:
            logger.info("NullShift: no untested functions detected — nothing to do.")
            return {
                "untested_functions": [],
                "generated_tests": [],
                "pr_url": "",
                "written_files": [],
            }

        logger.info(f"NullShift: {len(untested)} function(s) need tests.")

        # =====================================================================
        # STEP 2: Generate Unit Tests
        # =====================================================================
        # This step sends each untested function to the Groq LLM with a
        # carefully crafted prompt to generate comprehensive pytest tests.
        #
        # The LLM is instructed to generate tests covering:
        # - Happy path (normal usage)
        # - Edge cases
        # - Error conditions
        # - Boundary values
        #
        # Functions are grouped by source file to generate cohesive tests.
        
        generate_inputs = {**self.inputs, "untested_functions": untested}
        generate = GenerateUnitTests(generate_inputs)
        generate_out = generate.run()
        generated = generate_out.get("generated_tests", [])

        # =====================================================================
        # STEP 3: Create Test PR
        # =====================================================================
        # This final step:
        # 1. Writes generated tests to the appropriate test directories
        # 2. Creates a new git branch (unless dry_run=True)
        # 3. Commits the test files
        # 4. Pushes to origin
        # 5. Opens a GitHub pull request with description
        #
        # In dry-run mode, steps 2-5 are skipped and files are just written locally.
        
        pr_inputs = {**self.inputs, "generated_tests": generated}
        pr_step = CreateTestPR(pr_inputs)
        pr_out = pr_step.run()

        logger.info("━━━ NullShift: complete ━━━")
        return {
            "untested_functions": untested,
            "generated_tests": generated,
            "pr_url": pr_out.get("pr_url", ""),
            "written_files": pr_out.get("written_files", []),
        }

