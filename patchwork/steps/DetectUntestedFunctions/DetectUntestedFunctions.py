"""
DetectUntestedFunctions
=======================
Parses a unified diff (from a pull-request) and identifies Python functions /
methods that were **added or modified** but have no corresponding test coverage
in the repository.

Detection strategy
------------------
1. Parse the diff to find new/changed Python function definitions using the
   ``ast`` module (no external tree-sitter dependency required at runtime).
2. Walk the repository's test files and build a set of called names.
3. Return every function whose name does not appear in any test file.

Inputs (TypedDict)
------------------
- ``repo_path``        : str  – local path to the git repository root.
- ``pr_diff``          : str  – unified diff text (output of ``git diff``).
- ``test_directories`` : list[str] (optional) – subdirectory names considered
                         test folders.  Defaults to ``["tests", "test"]``.

Outputs (TypedDict)
-------------------
- ``untested_functions``: list[dict] – each entry has keys:
    - ``name``        : function/method name
    - ``file``        : source file (repo-relative)
    - ``lineno``      : line number in source file
    - ``source``      : full source text of the function
    - ``class_name``  : enclosing class name or None
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from typing_extensions import TypedDict

from patchwork.step import Step


# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------

class DetectUntestedFunctionsInputs(TypedDict, total=False):
    repo_path: str
    pr_diff: str
    test_directories: List[str]


class DetectUntestedFunctionsOutputs(TypedDict):
    untested_functions: List[Dict]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+\.py)$", re.MULTILINE)
_DIFF_FUNC_RE = re.compile(r"^\+\s*def\s+(\w+)\s*\(", re.MULTILINE)


def _extract_changed_files(diff: str) -> List[str]:
    """Return list of Python file paths touched by the diff."""
    return _DIFF_FILE_RE.findall(diff)


def _collect_function_names_from_diff(diff: str) -> Set[str]:
    """
    Collect function names that appear as **added** lines in the diff
    (lines beginning with '+').
    """
    return set(_DIFF_FUNC_RE.findall(diff))


def _get_function_source(source: str, node: ast.FunctionDef) -> str:
    """Extract source lines for a function node."""
    lines = source.splitlines()
    # ast gives 1-based line numbers
    func_lines = lines[node.lineno - 1 : node.end_lineno]
    return "\n".join(func_lines)


def _parse_functions_from_file(filepath: Path) -> List[Dict]:
    """
    Return a list of dicts describing every top-level and method function
    defined in *filepath*.
    """
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    functions = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Determine enclosing class (if any)
            class_name: Optional[str] = None
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    for child in ast.walk(parent):
                        if child is node:
                            class_name = parent.name
                            break

            functions.append(
                {
                    "name": node.name,
                    "file": str(filepath),
                    "lineno": node.lineno,
                    "source": _get_function_source(source, node),
                    "class_name": class_name,
                }
            )

    return functions


def _collect_tested_names(repo_root: Path, test_dirs: List[str]) -> Set[str]:
    """
    Walk test directories and collect all function/method *names* that are
    referenced (called, imported, or defined) – used as a coarse proxy for
    coverage.
    """
    tested: Set[str] = set()

    for test_dir_name in test_dirs:
        test_dir = repo_root / test_dir_name
        if not test_dir.is_dir():
            continue
        for py_file in test_dir.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                # Names referenced in tests
                if isinstance(node, ast.Name):
                    tested.add(node.id)
                # Attribute calls like ``obj.my_func()``
                elif isinstance(node, ast.Attribute):
                    tested.add(node.attr)
                # Function definitions inside test files (test_* helpers)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    tested.add(node.name)

    return tested


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------

class DetectUntestedFunctions(
    Step,
    input_class=DetectUntestedFunctionsInputs,
    output_class=DetectUntestedFunctionsOutputs,
):
    """
    Analyses a PR diff to surface Python functions that lack unit tests.
    """

    def __init__(self, inputs: Dict):
        super().__init__(inputs)
        self.repo_path = Path(inputs.get("repo_path", "."))
        self.pr_diff: str = inputs["pr_diff"]
        self.test_directories: List[str] = inputs.get(
            "test_directories", ["tests", "test"]
        )

    def run(self) -> Dict:
        changed_func_names = _collect_function_names_from_diff(self.pr_diff)
        changed_files = _extract_changed_files(self.pr_diff)

        if not changed_func_names:
            from patchwork.step import StepStatus
            self.set_status(StepStatus.SKIPPED, "No Python functions added or modified in diff.")
            return {"untested_functions": []}

        tested_names = _collect_tested_names(self.repo_path, self.test_directories)

        untested: List[Dict] = []

        for rel_path in changed_files:
            abs_path = self.repo_path / rel_path
            if not abs_path.is_file():
                continue
            for func_info in _parse_functions_from_file(abs_path):
                if func_info["name"] in changed_func_names:
                    if func_info["name"] not in tested_names:
                        # Make path relative for cleaner output
                        try:
                            func_info["file"] = str(
                                Path(func_info["file"]).relative_to(self.repo_path)
                            )
                        except ValueError:
                            pass
                        untested.append(func_info)

        from patchwork.logger import logger
        logger.info(
            f"DetectUntestedFunctions: found {len(untested)} untested function(s) "
            f"out of {len(changed_func_names)} changed."
        )

        return {"untested_functions": untested}
