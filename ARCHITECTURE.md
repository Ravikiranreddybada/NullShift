# NullShift Architecture

This document provides an in-depth technical explanation of how NullShift works, its components, and how to extend it.

## 📑 Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Step System](#step-system)
6. [Patchflow System](#patchflow-system)
7. [CLI Pipeline](#cli-pipeline)
8. [Extension Points](#extension-points)
9. [Testing Strategy](#testing-strategy)

---

## Overview

NullShift is an AI-powered test generation tool that:
1. Takes a git diff as input
2. Detects Python functions without test coverage
3. Uses Groq LLM to generate pytest tests
4. Creates GitHub PRs with generated tests

### Key Design Principles

- **Modularity**: Each step is independent and reusable
- **Extensibility**: Easy to add new steps or modify existing ones
- **Testability**: All components are unit-testable with mocked dependencies
- **Type Safety**: Uses TypedDict for input/output contracts

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NULLSHIFT SYSTEM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           CLI (app.py)                               │   │
│  │  • Argument parsing                                                  │   │
│  │  • Config loading                                                    │   │
│  │  • Telemetry                                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      NullShift Patchflow                            │   │
│  │                    (patchflows/NullShift.py)                        │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │   │
│  │  │   Detect    │──►│  Generate   │──►│  CreatePR   │               │   │
│  │  │  Untested   │   │ Unit Tests  │   │             │               │   │
│  │  └─────────────┘   └─────────────┘   └─────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           Steps Layer                                │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │   │
│  │  │ DetectUntested   │  │ GenerateUnit     │  │ CreateTestPR     │   │   │
│  │  │ Functions        │  │ Tests            │  │                  │   │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      External Services                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐   │   │
│  │  │   Groq      │  │   GitHub    │  │    Git      │  │ Patched  │   │   │
│  │  │    LLM      │  │     API     │  │    Repo     │  │  API     │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Patchflow (NullShift)

**File**: `patchwork/patchflows/NullShift/NullShift.py`

The patchflow acts as the orchestrator, coordinating the execution of multiple steps in sequence.

```python
class NullShift:
    def run(self) -> dict:
        # Step 1: Detect untested functions
        detect = DetectUntestedFunctions(self.inputs)
        untested = detect.run().get("untested_functions", [])

        # Step 2: Generate unit tests
        generate = GenerateUnitTests({**self.inputs, "untested_functions": untested})
        generated = generate.run().get("generated_tests", [])

        # Step 3: Create PR
        pr_step = CreateTestPR({**self.inputs, "generated_tests": generated})
        pr_out = pr_step.run()

        return {...}
```

### 2. Step: DetectUntestedFunctions

**File**: `patchwork/steps/DetectUntestedFunctions/DetectUntestedFunctions.py`

This step parses the git diff and identifies Python functions that lack test coverage.

#### Process:
1. **Parse Diff**: Extract added/modified files from the unified diff
2. **Extract Functions**: Use Python's AST module to find function definitions
3. **Check Coverage**: Search existing test files for test functions matching the target functions
4. **Return Results**: List of functions without coverage

#### Key Functions:

```python
def _parse_added_files(diff: str) -> dict[str, str]:
    """Extract added lines from each .py file in the diff."""
    # Uses regex to find +++ b/ headers and collect added lines

def _extract_functions(source: str, file_path: str) -> list[dict]:
    """Parse source using AST and return function info."""
    # Uses ast.parse() and ast.walk() to find FunctionDef nodes

def _find_tested_names(repo_path: Path, test_dirs: list[str]) -> set[str]:
    """Find all function names that appear in existing tests."""
    # Searches test_*.py files for test function names
```

#### Input Contract:
```python
class Inputs(TypedDict):
    pr_diff: str              # Required: Git diff
    repo_path: str             # Optional: Repository path (default: ".")
    test_directories: str     # Optional: Test directories (default: "tests,test")
```

#### Output Contract:
```python
class Outputs(TypedDict):
    untested_functions: List[dict]  # List of {name, file, lineno, source, class_name}
```

### 3. Step: GenerateUnitTests

**File**: `patchwork/steps/GenerateUnitTests/GenerateUnitTests.py`

This step calls the LLM to generate pytest unit tests for the detected functions.

#### Process:
1. **Group Functions**: Group functions by source file to generate cohesive tests
2. **Build Prompt**: Create a prompt with system instructions and function source
3. **Call LLM**: Send prompt to Groq API (or compatible endpoint)
4. **Parse Response**: Extract test code from LLM response
5. **Return Results**: Generated test code for each function

#### Key Functions:

```python
def _derive_test_path(source_file: str) -> str:
    """Convert source path to test path."""
    # "patchwork/utils.py" → "tests/test_utils.py"

def _strip_code_fences(text: str) -> str:
    """Remove ```python ... ``` markdown wrapping."""
```

#### Input Contract:
```python
class Inputs(TypedDict):
    untested_functions: List[dict]    # From DetectUntestedFunctions
    groq_api_key: str                   # Required: Groq API key
    model: str                          # Optional: LLM model
    client_base_url: str                # Optional: API endpoint
```

#### Output Contract:
```python
class Outputs(TypedDict):
    generated_tests: List[dict]  # List of {source_file, test_file, test_source, function_name}
```

### 4. Step: CreateTestPR

**File**: `patchwork/steps/CreateTestPR/CreateTestPR.py`

This step writes generated tests to disk and optionally creates a GitHub PR.

#### Process:
1. **Write Files**: Write test source to appropriate test directories
2. **Create Branch**: Create a new git branch (unless dry_run)
3. **Commit**: Commit the changes
4. **Push**: Push to origin
5. **Create PR**: Open GitHub PR (unless dry_run)

#### Key Functions:

```python
def _write_test_files(generated_tests: list[dict], repo_path: Path) -> dict[str, str]:
    """Write test files to disk."""

def _git_commit_and_push(repo_path: Path, branch: str, files: list[str], base_branch: str):
    """Create branch, commit, and push."""

def _open_github_pr(repo_path: Path, github_api_key: str, branch: str, base_branch: str, file_count: int):
    """Open GitHub PR and return URL."""
```

#### Input Contract:
```python
class Inputs(TypedDict):
    generated_tests: List[dict]     # From GenerateUnitTests
    repo_path: str                  # Optional: Repository path
    github_api_key: str            # Optional: GitHub token
    base_branch: str               # Optional: Target branch
    pr_branch_prefix: str          # Optional: Branch prefix
    dry_run: bool                  # Optional: Skip git/PR
```

#### Output Contract:
```python
class Outputs(TypedDict):
    pr_url: str                     # PR URL or "dry_run"
    written_files: List[str]       # Written test file paths
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                       │
└─────────────────────────────────────────────────────────────────────────────┘

1. USER INPUTS
   ┌─────────────────────────────────────────┐
   │ pr_diff: "diff --git..."                │
   │ groq_api_key: "gsk_..."                │
   │ github_api_key: "ghp_..."              │
   │ dry_run: false                         │
   └─────────────────────────────────────────┘
                    │
                    ▼
2. DETECT UNTESTED FUNCTIONS
   ┌─────────────────────────────────────────┐
   │ Input:  pr_diff                         │
   │ Process:                                │
   │   1. Parse diff                         │
   │   2. Extract Python files              │
   │   3. AST parse to find functions       │
   │   4. Check existing test coverage      │
   │ Output: untested_functions: [...]      │
   └─────────────────────────────────────────┘
                    │
                    ▼
3. GENERATE UNIT TESTS
   ┌─────────────────────────────────────────┐
   │ Input:  untested_functions              │
   │ Process:                                │
   │   1. Group by source file              │
   │   2. Build LLM prompt                  │
   │   3. Call Groq API                     │
   │   4. Parse response                   │
   │ Output: generated_tests: [...]         │
   └─────────────────────────────────────────┘
                    │
                    ▼
4. CREATE TEST PR
   ┌─────────────────────────────────────────┐
   │ Input:  generated_tests                 │
   │ Process:                                │
   │   1. Write test files to disk          │
   │   2. Git: create branch                │
   │   3. Git: commit changes               │
   │   4. Git: push to origin               │
   │   5. GitHub: create PR                 │
   │ Output: pr_url, written_files          │
   └─────────────────────────────────────────┘
                    │
                    ▼
5. FINAL OUTPUT
   ┌─────────────────────────────────────────┐
   │ {                                      │
   │   "untested_functions": [...],         │
   │   "generated_tests": [...],           │
   │   "pr_url": "https://...",            │
   │   "written_files": [...]              │
   │ }                                      │
   └─────────────────────────────────────────┘
```

---

## Step System

### Base Step Class

**File**: `patchwork/step.py`

All steps inherit from the `Step` base class:

```python
class Step(abc.ABC):
    def __init__(self, inputs: DataPoint):
        # Validates required inputs
        # Stores inputs
        # Wraps run() with logging and error handling

    @abc.abstractmethod
    def run(self) -> DataPoint:
        """Implement the step logic."""
        ...
```

### Input/Output Contracts

Steps declare their inputs and outputs using TypedDict:

```python
class MyInputs(TypedDict):
    required_field: str
    optional_field: int  # Optional (has default)

class MyOutputs(TypedDict):
    result_field: str

class MyStep(Step, input_class=MyInputs, output_class=MyOutputs):
    def run(self) -> dict:
        return {"result_field": "value"}
```

### Step Lifecycle

1. **Initialization**: Validate required inputs
2. **Execution**: Run the step logic
3. **Output**: Return results as dict
4. **Error Handling**: Exceptions are caught and logged

### Debug Mode

Steps support debug mode for inspecting inputs:

```python
step = MyStep(inputs)
step.debug(inputs)  # Pauses and shows inputs if debug=True
```

---

## Patchflow System

Patchflows orchestrate multiple steps:

```python
class MyPatchflow:
    def __init__(self, inputs: dict):
        self.inputs = inputs

    def run(self) -> dict:
        # Step 1
        step1 = Step1(self.inputs)
        step1_output = step1.run()

        # Step 2 (uses output from step 1)
        step2_inputs = {**self.inputs, **step1_output}
        step2 = Step2(step2_inputs)
        step2_output = step2.run()

        # Combine outputs
        return {**step1_output, **step2_output}
```

---

## CLI Pipeline

**File**: `patchwork/app.py`

The CLI processes inputs in this order:

```
1. Parse global options (--config, --log, --list, etc.)
   ↓
2. Find patchflow class
   ↓
3. Load config from YAML if provided
   ↓
4. Parse patchflow-specific arguments
   ↓
5. Instantiate patchflow
   ↓
6. Run patchflow
   ↓
7. Output results (JSON/YAML)
```

### Argument Processing

```bash
nullshift NullShift \
    groq_api_key=gsk_xxx \
    github_api_key=ghp_xxx \
    pr_diff="$(git diff origin/main)"
```

Arguments are parsed as:
- `--key=value` → `inputs["key"] = "value"`
- `--flag` → `inputs["flag"] = True`

---

## Extension Points

### Adding a New Step

1. Create directory: `patchwork/steps/MyStep/`
2. Create `__init__.py` and `MyStep.py`
3. Define Input/Output TypedDicts
4. Implement Step class
5. Add tests

### Adding a New Patchflow

1. Create directory: `patchwork/patchflows/MyPatchflow/`
2. Create `__init__.py` and `MyPatchflow.py`
3. Import and compose Steps
4. Register in CLI (automatic via package structure)

### Custom LLM Provider

To use a different LLM:

```python
# Override GenerateUnitTests to use different client
class MyGenerateUnitTests(GenerateUnitTests):
    def __init__(self, inputs):
        super().__init__(inputs)
        # Use custom client
        self._client = MyCustomClient(inputs["api_key"])
```

---

## Testing Strategy

### Test Types

1. **Unit Tests** (`tests/steps/`): Test individual steps in isolation
2. **Integration Tests** (`tests/cicd/`): Test full patchflow with mocked external services
3. **Common Tests** (`tests/common/`): Shared utilities and fixtures

### Test Fixtures

**File**: `tests/conftest.py`

```python
@pytest.fixture
def simple_diff():
    """Simple git diff for testing."""
    return """diff --git a/myapp.py b/myapp.py
--- a/myapp.py
+++ b/myapp.py
@@ -1,3 +1,7 @@
+def add(a, b):
+    return a + b
"""

@pytest.fixture
def tmp_path(tmp_path_factory):
    """Temporary directory for tests."""
    return tmp_path_factory.mktemp("test_repo")
```

### Mocking External Services

```python
# Mock OpenAI client
mocker.patch("patchwork.steps.GenerateUnitTests.GenerateUnitTests.OpenAI")

# Mock GitHub API
mocker.patch("github.Github")

# Mock git operations
mocker.patch("git.Repo")
```

---

## Security Considerations

1. **API Keys**: Never log or expose API keys
2. **Code Execution**: Generated tests are not executed, only written to disk
3. **Dry Run**: Use `dry_run=True` for safe testing
4. **Branch Isolation**: Tests are created on a separate branch

---

## Performance Considerations

1. **Batching**: Multiple functions in the same file are batched into one LLM call
2. **Caching**: Results are not cached (each run is independent)
3. **Rate Limits**: Be aware of Groq API rate limits

---

## Troubleshooting

### Common Issues

1. **No functions detected**: Check that the diff includes Python files
2. **LLM errors**: Verify API key and endpoint configuration
3. **Git errors**: Ensure the repository has a remote configured
4. **PR creation fails**: Check GitHub token permissions

### Debug Mode

Use `--debug` flag to inspect inputs at each step:

```bash
nullshift NullShift --debug groq_api_key=... pr_diff=...
```

---

## Further Reading

- [Patchwork Framework](https://github.com/patched-codes/patchwork)
- [Python AST Module](https://docs.python.org/3/library/ast.html)
- [Groq API Documentation](https://docs.groq.com/)
- [PyGithub Documentation](https://pygithub.readthedocs.io/)

