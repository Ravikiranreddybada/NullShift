"""
NullShift patchflow
===================
Orchestrates three steps end-to-end:

1. DetectUntestedFunctions — find Python functions in the PR diff with no tests.
2. GenerateUnitTests       — call Groq LLM to write pytest suites.
3. CreateTestPR            — write files and open a GitHub pull request.
"""
from __future__ import annotations

from typing_extensions import Any

from patchwork.logger import logger
from patchwork.steps.CreateTestPR import CreateTestPR
from patchwork.steps.DetectUntestedFunctions import DetectUntestedFunctions
from patchwork.steps.GenerateUnitTests import GenerateUnitTests


class NullShift:
    """Top-level patchflow: detect → generate → PR."""

    def __init__(self, inputs: dict[str, Any]):
        self.inputs = inputs

    def run(self) -> dict[str, Any]:
        logger.info("━━━ NullShift: starting ━━━")

        # Step 1 — Detect
        detect = DetectUntestedFunctions(self.inputs)
        detect_out = detect.run()
        untested = detect_out.get("untested_functions", [])

        if not untested:
            logger.info("NullShift: no untested functions detected — nothing to do.")
            return {
                "untested_functions": [],
                "generated_tests": [],
                "pr_url": "",
                "written_files": [],
            }

        logger.info(f"NullShift: {len(untested)} function(s) need tests.")

        # Step 2 — Generate
        generate_inputs = {**self.inputs, "untested_functions": untested}
        generate = GenerateUnitTests(generate_inputs)
        generate_out = generate.run()
        generated = generate_out.get("generated_tests", [])

        # Step 3 — PR
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
