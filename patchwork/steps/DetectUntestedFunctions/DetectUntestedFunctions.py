"""
DetectUntestedFunctions
=======================
Parses a unified git diff and identifies Python functions that were added or
modified but have **no corresponding test coverage** in the repository.

Inputs
------
pr_diff : str
    Unified diff produced by ``git diff origin/main``.
repo_path : str, optional
    Absolute (or relative) path to the local repository root.  Defaults to
    the current working directory (``"."``).
test_directories : str, optional
    Comma-separated list of folder names that are considered test roots.
    Defaults to ``"tests,test"``.

Outputs
-------
untested_functions : list[dict]
    Each entry has keys: ``name``, ``file``, ``lineno``, ``source``,
    ``class_name`` (may be ``None``).
"""
from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path
from typing import List, Optional

from typing_extensions import TypedDict

from patchwork.logger import logger
from patchwork.step import Step


# ---------------------------------------------------------------------------
# TypedDict contracts
# ---------------------------------------------------------------------------

class _Inputs(TypedDict, total=False):
    pr_diff: str           # required
    repo_path: str         # optional
    test_directories: str  # optional


class _Inputs_Required(TypedDict):
    pr_diff: str


class Inputs(_Inputs_Required, _Inputs):
    pass


class Outputs(TypedDict):
    untested_functions: List[dict]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIFF_FILE_HEADER = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
_DIFF_ADDED_LINE = re.compile(r"^\+(?!\+\+)", re.MULTILINE)


def _parse_added_files(diff: str) -> dict[str, str]:
    """Return {relative_path: added_lines_as_source} for every .py file in the diff."""
    result: dict[str, str] = {}
    # Split diff into per-file sections
    sections = re.split(r"^diff --git ", diff, flags=re.MULTILINE)
    for section in sections:
        # Find the +++ b/... header
        match = _DIFF_FILE_HEADER.search(section)
        if not match:
            continue
        file_path = match.group(1)
        if not file_path.endswith(".py"):
            continue
        # Collect added lines (strip the leading '+')
        added_lines = [line[1:] for line in section.splitlines() if re.match(r"^\+(?!\+\+)", line)]
        if added_lines:
            result[file_path] = "\n".join(added_lines)
    return result


def _extract_functions(source: str, file_path: str) -> list[dict]:
    """Parse *source* and return a list of function-info dicts."""
    functions = []
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        logger.warning(f"Could not parse Python source from diff for {file_path}")
        return functions

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Reconstruct source lines
            try:
                func_lines = source.splitlines()[node.lineno - 1: node.end_lineno]
                func_source = "\n".join(func_lines)
            except (AttributeError, IndexError):
                func_source = f"def {node.name}(...): ..."

            # Try to find enclosing class
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
                    "file": file_path,
                    "lineno": node.lineno,
                    "source": func_source,
                    "class_name": class_name,
                }
            )
    return functions


def _is_test_function(name: str) -> bool:
    return name.startswith("test_") or name.startswith("Test")


def _find_tested_names(repo_path: Path, test_dirs: list[str]) -> set[str]:
    """Collect all function names that appear in existing test files."""
    tested: set[str] = set()
    for test_dir_name in test_dirs:
        test_dir = repo_path / test_dir_name
        if not test_dir.is_dir():
            continue
        for test_file in test_dir.rglob("test_*.py"):
            try:
                content = test_file.read_text(encoding="utf-8", errors="replace")
                tested.update(re.findall(r"\btest_(\w+)\b", content))
                # Also gather all identifiers that appear in import statements
                for m in re.finditer(r"(?:from|import)\s+\S+\s+import\s+(\w+)", content):
                    tested.add(m.group(1))
            except OSError:
                pass
    return tested


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------

class DetectUntestedFunctions(Step, input_class=Inputs, output_class=Outputs):
    """Detect Python functions added/modified in a PR diff that lack test coverage."""

    def __init__(self, inputs: dict):
        super().__init__(inputs)
        self._diff: str = inputs["pr_diff"]
        self._repo_path = Path(inputs.get("repo_path", ".")).resolve()
        raw_dirs = inputs.get("test_directories", "tests,test")
        self._test_dirs = [d.strip() for d in raw_dirs.split(",") if d.strip()]

    def run(self) -> dict:
        logger.info("DetectUntestedFunctions: parsing diff …")

        added_by_file = _parse_added_files(self._diff)
        if not added_by_file:
            logger.info("No added Python files found in diff.")
            return {"untested_functions": []}

        tested_names = _find_tested_names(self._repo_path, self._test_dirs)
        logger.info(f"Found {len(tested_names)} already-tested symbol(s) in test directories.")

        untested: list[dict] = []
        for file_path, added_source in added_by_file.items():
            functions = _extract_functions(added_source, file_path)
            for fn in functions:
                if _is_test_function(fn["name"]):
                    continue  # skip functions that are themselves tests
                if fn["name"] in tested_names:
                    logger.info(f"  ✓ {fn['name']} already covered — skipping.")
                    continue
                logger.info(f"  ✗ {fn['name']} in {file_path} — no test found.")
                untested.append(fn)

        logger.info(f"DetectUntestedFunctions: {len(untested)} untested function(s) found.")
        return {"untested_functions": untested}
