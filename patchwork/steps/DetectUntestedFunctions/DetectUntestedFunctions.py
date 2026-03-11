"""
DetectUntestedFunctions Step Module
===================================

This module implements the first step of the NullShift pipeline: detecting
Python functions in a pull request diff that lack test coverage.

Overview
--------
The DetectUntestedFunctions step analyzes a git diff to identify Python
functions that were added or modified but don't have corresponding tests.
It uses Python's AST (Abstract Syntax Tree) module for accurate function
detection and searches existing test files to determine coverage.

Key Features
------------
- AST-based function detection (accurate parsing)
- Support for async functions and class methods
- Smart test coverage detection
- Handles various git diff formats

How It Works
------------
1. Parse the unified git diff to extract added/modified files
2. Filter for Python files only (.py extension)
3. Use AST to parse the added source code and extract function definitions
4. Search existing test directories for matching test functions
5. Return list of functions that lack test coverage

Example Usage
-------------
>>> from patchwork.steps.DetectUntestedFunctions import DetectUntestedFunctions
>>>
>>> inputs = {
...     "pr_diff": """diff --git a/myapp.py b/myapp.py
... +++ b/myapp.py
... +def add(a, b):
... +    return a + b""",
...     "repo_path": "/path/to/repo",
...     "test_directories": "tests,test",
... }
>>> step = DetectUntestedFunctions(inputs)
>>> result = step.run()
>>> print(result)
{"untested_functions": [{"name": "add", "file": "myapp.py", ...}]}

Algorithm Details
-----------------

Diff Parsing
~~~~~~~~~~~~
The step uses regex to parse the unified diff format:
- Finds file headers (+++ b/path)
- Collects added lines (starting with + but not ++)
- Skips removed lines and context

Function Extraction
~~~~~~~~~~~~~~~~~~
AST parsing is used because it's more accurate than regex:
- Correctly identifies function boundaries
- Handles nested code
- Distinguishes between function definitions and calls
- Supports async def, decorators, etc.

Coverage Detection
~~~~~~~~~~~~~~~~~~
A function is considered "tested" if:
- There's a test function with name matching "test_{function_name}"
- The function name appears in imports within test files

Input Contract
--------------
Required:
    - pr_diff (str): Unified git diff from the PR

Optional:
    - repo_path (str): Path to repository (default: ".")
    - test_directories (str): Comma-separated test dirs (default: "tests,test")

Output Contract
---------------
untested_functions (list[dict]): Each dict contains:
    - name (str): Function name
    - file (str): Relative file path
    - lineno (int): Line number in source file
    - source (str): Function source code
    - class_name (str|None): Enclosing class name (if method)

Edge Cases
----------
1. Empty diff: Returns empty list
2. No Python files: Returns empty list
3. Syntax errors in added code: Skips that file with warning
4. Test directories don't exist: Searches available test dirs
5. Functions in __init__.py: Handled as module-level functions
6. Decorated functions: Included in detection

Performance Considerations
-------------------------
- AST parsing is O(n) where n is the size of added source
- Test coverage check is O(f * t) where f = files, t = test files
- Large diffs may take longer to process
- Caching could be added for repeated runs

See Also
--------
- patchwork.step.Step: Base class
- ast module: Python AST documentation
- git diff format: Unified diff format specification
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path
from typing import List, Optional, Set

from typing_extensions import TypedDict

from patchwork.logger import logger
from patchwork.step import Step


# ============================================================================
# TypedDict Contracts
# ============================================================================

class _Inputs(TypedDict, total=False):
    """Input type hints for DetectUntestedFunctions step."""
    pr_diff: str           # Required: Unified git diff
    repo_path: str         # Optional: Repository root path
    test_directories: str # Optional: Test directory names


class _Inputs_Required(TypedDict):
    """Required inputs for DetectUntestedFunctions."""
    pr_diff: str


class Inputs(_Inputs_Required, _Inputs):
    """Complete input contract for DetectUntestedFunctions step."""
    pass


class Outputs(TypedDict):
    """Output type for DetectUntestedFunctions step."""
    untested_functions: List[dict]


# ============================================================================
# Module-Level Constants (Private)
# ============================================================================

# Regex to match file headers in unified diff format
# Matches: +++ b/path/to/file.py
_DIFF_FILE_HEADER = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)

# Regex to match added lines (starts with + but not ++ for diff header)
_DIFF_ADDED_LINE = re.compile(r"^\+(?!\+\+)", re.MULTILINE)


# ============================================================================
# Helper Functions (Private)
# ============================================================================

def _parse_added_files(diff: str) -> dict[str, str]:
    """
    Parse the git diff and extract added source lines for each Python file.
    
    This function splits the diff into per-file sections, then extracts
    the added lines (ignoring removed lines and context).
    
    Args:
        diff: Unified git diff string
        
    Returns:
        Dictionary mapping file paths to their added source code.
        Only includes files with .py extension.
    
    Example:
        >>> diff = '''diff --git a/utils.py b/utils.py
        ... +++ b/utils.py
        ... +def add(a, b):
        ... +    return a + b'''
        >>> _parse_added_files(diff)
        {'utils.py': 'def add(a, b):\\n    return a + b'}
    """
    result: dict[str, str] = {}
    
    # Split diff into per-file sections using diff --git header
    sections = re.split(r"^diff --git ", diff, flags=re.MULTILINE)
    
    for section in sections:
        # Find the +++ b/ header to get the file path
        match = _DIFF_FILE_HEADER.search(section)
        if not match:
            continue
            
        file_path = match.group(1)
        
        # Only process Python files
        if not file_path.endswith(".py"):
            continue
            
        # Collect added lines, stripping the leading '+'
        # Using regex to match lines starting with + (but not ++)
        added_lines = [
            line[1:] for line in section.splitlines() 
            if re.match(r"^\+(?!\+\+)", line)
        ]
        
        if added_lines:
            result[file_path] = "\n".join(added_lines)
    
    return result


def _extract_functions(source: str, file_path: str) -> list[dict]:
    """
    Extract function definitions from Python source code using AST.
    
    Uses Python's AST module for accurate parsing. This is more reliable
    than regex because it understands Python syntax structure.
    
    Args:
        source: Python source code string
        file_path: Path to the source file (for logging/error context)
        
    Returns:
        List of dictionaries, each containing:
        - name: Function name
        - file: File path
        - lineno: Line number
        - source: Function source code
        - class_name: Enclosing class (if method) or None
    
    The function attempts to reconstruct the original source for each
    function to pass to the LLM for test generation.
    """
    functions = []
    
    try:
        # Parse the source code into an AST
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        logger.warning(f"Could not parse Python source from diff for {file_path}")
        return functions

    # Walk through all nodes in the AST
    for node in ast.walk(tree):
        # Only process function definitions (regular and async)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Reconstruct source lines for this function
            try:
                func_lines = source.splitlines()[node.lineno - 1: node.end_lineno]
                func_source = "\n".join(func_lines)
            except (AttributeError, IndexError):
                # Fallback if we can't reconstruct source
                func_source = f"def {node.name}(...): ..."

            # Try to find enclosing class (for methods)
            class_name: Optional[str] = None
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    # Check if this function is a child of the class
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
    """
    Check if a function name indicates it's a test function.
    
    Test functions typically follow pytest naming conventions:
    - Start with "test_" (pytest default)
    - Start with "Test" (unittest convention)
    
    Args:
        name: Function name to check
        
    Returns:
        True if the name suggests a test function, False otherwise
    """
    return name.startswith("test_") or name.startswith("Test")


def _find_tested_names(repo_path: Path, test_dirs: list[str]) -> set[str]:
    """
    Find all function names that appear to have test coverage.
    
    Searches through test files to find:
    1. Test function definitions (test_*)
    2. Imported names that might be the functions being tested
    
    Args:
        repo_path: Path to the repository root
        test_dirs: List of directory names to search for tests
        
    Returns:
        Set of function names that appear to have test coverage
    """
    tested: set[str] = set()
    
    for test_dir_name in test_dirs:
        test_dir = repo_path / test_dir_name
        if not test_dir.is_dir():
            continue
            
        # Find all test files (test_*.py pattern)
        for test_file in test_dir.rglob("test_*.py"):
            try:
                content = test_file.read_text(encoding="utf-8", errors="replace")
                
                # Find test function definitions
                tested.update(re.findall(r"\btest_(\w+)\b", content))
                
                # Also gather imported names (functions being tested)
                # Pattern: from module import function_name
                # or: import module
                for m in re.finditer(r"(?:from|import)\s+\S+\s+import\s+(\w+)", content):
                    tested.add(m.group(1))
                    
            except OSError:
                # Skip files that can't be read
                pass
    
    return tested


# ============================================================================
# Step Implementation
# ============================================================================

class DetectUntestedFunctions(Step, input_class=Inputs, output_class=Outputs):
    """
    Detect Python functions in PR diff that lack test coverage.
    
    This step analyzes a git diff to find Python functions that were
    added or modified but don't have corresponding test coverage.
    
    The detection process:
    1. Parse the diff to find added Python files
    2. Use AST to extract function definitions
    3. Search existing test files for matching test functions
    4. Return list of untested functions
    
    Attributes:
        _diff: The git diff string to analyze
        _repo_path: Path to the repository root
        _test_dirs: List of test directory names to search
    
    Example:
        >>> inputs = {"pr_diff": diff_string, "repo_path": ".", "test_directories": "tests"}
        >>> step = DetectUntestedFunctions(inputs)
        >>> result = step.run()
        >>> # Returns: {"untested_functions": [...]}
    """

    def __init__(self, inputs: dict) -> None:
        """
        Initialize the DetectUntestedFunctions step.
        
        Args:
            inputs: Dictionary with required 'pr_diff' and optional parameters.
        
        Raises:
            ValueError: If required inputs are missing
        """
        super().__init__(inputs)
        
        # Store the git diff for processing
        self._diff: str = inputs["pr_diff"]
        
        # Resolve repository path to absolute path
        self._repo_path = Path(inputs.get("repo_path", ".")).resolve()
        
        # Parse test directory names from comma-separated string
        raw_dirs = inputs.get("test_directories", "tests,test")
        self._test_dirs = [d.strip() for d in raw_dirs.split(",") if d.strip()]

    def run(self) -> dict:
        """
        Execute the function detection workflow.
        
        This method:
        1. Parses the git diff for added Python files
        2. Extracts function definitions using AST
        3. Checks for existing test coverage
        4. Returns list of untested functions
        
        Returns:
            Dictionary with 'untested_functions' key containing list of
            function info dictionaries (name, file, lineno, source, class_name)
        
        The output of this step is fed directly into the GenerateUnitTests step.
        """
        logger.info("DetectUntestedFunctions: parsing diff …")

        # Step 1: Parse the diff to extract added Python files
        added_by_file = _parse_added_files(self._diff)
        
        if not added_by_file:
            logger.info("No added Python files found in diff.")
            return {"untested_functions": []}

        # Step 2: Find existing test function names in the repo
        tested_names = _find_tested_names(self._repo_path, self._test_dirs)
        logger.info(f"Found {len(tested_names)} already-tested symbol(s) in test directories.")

        # Step 3: Extract functions from added code and check coverage
        untested: list[dict] = []
        
        for file_path, added_source in added_by_file.items():
            # Parse the added source to find function definitions
            functions = _extract_functions(added_source, file_path)
            
            for fn in functions:
                # Skip functions that are themselves tests
                if _is_test_function(fn["name"]):
                    continue
                    
                # Skip functions that appear to have test coverage
                if fn["name"] in tested_names:
                    logger.info(f"  ✓ {fn['name']} already covered — skipping.")
                    continue
                    
                # This function lacks test coverage
                logger.info(f"  ✗ {fn['name']} in {file_path} — no test found.")
                untested.append(fn)

        logger.info(f"DetectUntestedFunctions: {len(untested)} untested function(s) found.")
        return {"untested_functions": untested}

