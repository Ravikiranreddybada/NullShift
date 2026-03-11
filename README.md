<div align="center">

# 🔍 NullShift

**AI-powered unit test generation for Python pull requests**

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

NullShift detects untested Python functions on pull requests and **autonomously generates pytest unit tests** — then opens a PR with the generated tests so your team can review and merge them.

</div>

---

## ✨ How It Works

```
git diff origin/main  →  NullShift CLI  →  Groq LLM  →  PR with tests
```

1. **Detect** — Parses the PR diff, finds Python functions that were added or modified with no corresponding test coverage.
2. **Generate** — Calls Groq's LLM (llama-3.3-70b-versatile) with each function's source and prompts it to write thorough pytest tests.
3. **Create PR** — Commits the generated test files on a new branch and opens a GitHub pull request for human review.

---

## 🚀 Quick Start

### Install

```bash
pip install nullshift-cli
```

### Run against your current branch

```bash
nullshift NullShift \
    groq_api_key=gsk_... \
    github_api_key=ghp_... \
    pr_diff="$(git diff origin/main)"
```

### Dry run (no git, no PR — just write test files locally)

```bash
nullshift NullShift \
    groq_api_key=gsk_... \
    pr_diff="$(git diff origin/main)" \
    dry_run
```

---

## ⚙️ CLI Reference

| Argument | Required | Description |
|---|---|---|
| `groq_api_key` | ✅ | Groq API key (format: `gsk_...`) |
| `github_api_key` | ✅* | GitHub personal access token (*not needed with `dry_run`) |
| `pr_diff` | ✅ | Unified diff — use `$(git diff origin/main)` |
| `repo_path` | ❌ | Local repo root (default: `.`) |
| `model` | ❌ | LLM model name (default: `llama-3.3-70b-versatile`) |
| `client_base_url` | ❌ | Custom Groq-compatible endpoint (default: `https://api.groq.com/openai/v1`) |
| `base_branch` | ❌ | PR target branch (default: `main`) |
| `pr_branch_prefix` | ❌ | Branch prefix (default: `nullshift/auto-tests`) |
| `test_directories` | ❌ | Comma-separated test folder names (default: `tests,test`) |
| `dry_run` | ❌ | Write tests locally only — skip git/PR |

---

## 🤖 Using Alternative LLMs

NullShift defaults to Groq, but supports any Groq-compatible endpoint.

**Local model via Ollama**
```bash
nullshift NullShift \
    client_base_url=http://localhost:11434/v1 \
    groq_api_key=no-key \
    model=codellama \
    github_api_key=ghp_... \
    pr_diff="$(git diff origin/main)"
```

---

## 🔧 Architecture

NullShift is built on the **Patchwork** framework — a composable system of Steps and Patchflows.

```
NullShift (patchflow)
├── DetectUntestedFunctions (step)  — parse diff, find untested functions
├── GenerateUnitTests (step)        — call LLM, produce pytest code
└── CreateTestPR (step)             — commit + open GitHub PR
```

### Adding a New Step

```python
from typing_extensions import TypedDict
from patchwork.step import Step

class MyStepInputs(TypedDict):
    my_input: str

class MyStepOutputs(TypedDict):
    my_output: str

class MyStep(Step, input_class=MyStepInputs, output_class=MyStepOutputs):
    def __init__(self, inputs):
        super().__init__(inputs)

    def run(self) -> dict:
        return {"my_output": self.inputs["my_input"].upper()}
```

---

## 🧪 Running Tests

```bash
pip install pytest pytest-mock
pytest tests/ -v
```

