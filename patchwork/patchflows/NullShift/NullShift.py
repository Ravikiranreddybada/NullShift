"""
NullShift Patchflow
===================
End-to-end pipeline that:
  1. Detects untested Python functions in a PR diff.
  2. Generates pytest unit tests for each one via an LLM.
  3. Commits the tests and opens a GitHub PR.

Quick start
-----------
Run against the current repo, providing a Groq key and a diff:

    nullshift NullShift \\
        openai_api_key=gsk_... \\
        github_api_key=ghp_... \\
        pr_diff="$(git diff origin/main)"

To try without creating a real PR (local dry-run):

    nullshift NullShift openai_api_key=gsk_... pr_diff="$(git diff)" dry_run
"""
from __future__ import annotations

from typing import Any, Dict

from patchwork.steps.CreateTestPR.CreateTestPR import CreateTestPR
from patchwork.steps.DetectUntestedFunctions.DetectUntestedFunctions import (
    DetectUntestedFunctions,
)
from patchwork.steps.GenerateUnitTests.GenerateUnitTests import GenerateUnitTests


class NullShift:
    """
    AI-powered patchflow that detects untested functions on PRs and
    autonomously generates unit tests.
    """

    def __init__(self, inputs: Dict[str, Any]):
        self.inputs = inputs

    def run(self) -> Dict[str, Any]:
        # ── Step 1: Detect untested functions ────────────────────────────
        detect = DetectUntestedFunctions(self.inputs)
        detect_output = detect.run()

        # ── Step 2: Generate unit tests via LLM ──────────────────────────
        generate_inputs = {**self.inputs, **detect_output}
        generate = GenerateUnitTests(generate_inputs)
        generate_output = generate.run()

        # ── Step 3: Commit tests and open PR ─────────────────────────────
        pr_inputs = {**self.inputs, **generate_output}
        create_pr = CreateTestPR(pr_inputs)
        pr_output = create_pr.run()

        return {
            **detect_output,
            **generate_output,
            **pr_output,
        }
