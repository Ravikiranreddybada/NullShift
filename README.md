<div align="center">

# 🔍 NullShift

**AI-Powered Unit Test Generation for Python Pull Requests**

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI Version](https://img.shields.io/pypi/v/nullshift-cli.svg)](https://pypi.org/project/nullshift-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/Tests-passing-brightgreen.svg)](https://github.com/NullShift/nullshift/actions)
[![Code Style: Black](https://img.shields.io/badge/Code%20Style-Black-000000.svg)](https://github.com/psf/black)
[![Downloads](https://img.shields.io/pypi/dm/nullshift-cli.svg)](https://pypi.org/project/nullshift-cli/)

</div>

---

## ✨ What is NullShift?

NullShift is an **intelligent test generation tool** that automatically detects untested Python functions in your pull requests and generates comprehensive pytest unit tests for them. It then creates a GitHub PR with the generated tests, so your team can review and merge them.

### 🎯 Key Features

- **🤖 AI-Powered Test Generation** — Uses Groq's LLM (Llama 3.3) to generate high-quality pytest tests
- **🔍 Smart Detection** — Automatically identifies Python functions without test coverage
- **📝 Automated PR Creation** — Opens GitHub pull requests with generated tests
- **🔧 Extensible Architecture** — Built on Patchwork framework, easy to extend
- **🧪 Dry-Run Mode** — Test locally without touching git or GitHub
- **🌐 Multi-LLM Support** — Works with any OpenAI-compatible endpoint (Groq, Ollama, etc.)

---

## 🚀 Quick Start

### Installation

```bash
# From PyPI (recommended)
pip install nullshift-cli

# From source
pip install -e .
```

### Basic Usage

```bash
# Run against your current branch with a dry run (no git/PR)
nullshift NullShift \
    groq_api_key=gsk_your_api_key \
    pr_diff="$(git diff origin/main)" \
    dry_run

# Full run with GitHub PR creation
nullshift NullShift \
    groq_api_key=gsk_your_api_key \
    github_api_key=ghp_your_github_token \
    pr_diff="$(git diff origin/main)"
```

---

## 📖 How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            NULLSHIFT WORKFLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐      ┌──────────────┐      ┌───────────────┐      ┌────────┐
     │  GitHub  │      │   Detect     │      │    Generate   │      │ Create │
     │    PR    │      │   Untested   │      │  Unit Tests   │      │   PR   │
     └────┬─────┘      │  Functions   │      │     (LLM)     │      │  (Git) │
          │            └───────┬───────┘      └───────┬───────┘      └────┬────┘
          │                    │                      │                   │
          │  git diff  ───────► │                      │                   │
          │                    │  List of functions   │                   │
          │                    │  without tests    ──►│                   │
          │                    │                      │  Test files   ──►│
          │                    │                      │                   │
     ◄────┘                    ◄──────────────────────┘                   │
     PR URL                    untested_functions     generated_tests   PR Created
```

### Step-by-Step Process

1. **📊 Detect** — Parses the PR diff and uses AST parsing to find Python functions that were added or modified
2. **🧠 Generate** — Sends each function's source code to Groq's LLM with a carefully crafted prompt to generate pytest tests
3. **📦 Create PR** — Commits the generated test files on a new branch and opens a GitHub pull request

---

## ⚙️ CLI Reference

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `groq_api_key` | ✅ | - | Groq API key (format: `gsk_...`) |
| `github_api_key` | ✅* | - | GitHub personal access token (*not needed with `dry_run`) |
| `pr_diff` | ✅ | - | Unified diff — use `$(git diff origin/main)` |
| `repo_path` | ❌ | `.` | Local repo root path |
| `model` | ❌ | `llama-3.3-70b-versatile` | LLM model name |
| `client_base_url` | ❌ | `https://api.groq.com/openai/v1` | Custom Groq-compatible endpoint |
| `base_branch` | ❌ | `main` | PR target branch |
| `pr_branch_prefix` | ❌ | `nullshift/auto-tests` | Branch prefix for auto-generated branches |
| `test_directories` | ❌ | `tests,test` | Comma-separated test folder names |
| `dry_run` | ❌ | `False` | Write tests locally only — skip git/PR |

---

## 🔧 Using Alternative LLMs

NullShift supports any OpenAI-compatible endpoint:

### Local Model via Ollama
```bash
nullshift NullShift \
    client_base_url=http://localhost:11434/v1 \
    groq_api_key=no-key \
    model=codellama \
    github_api_key=ghp_... \
    pr_diff="$(git diff origin/main)"
```

### OpenAI
```bash
nullshift NullShift \
    client_base_url=https://api.openai.com/v1 \
    groq_api_key=sk-... \
    model=gpt-4 \
    github_api_key=ghp_... \
    pr_diff="$(git diff origin/main)"
```

### Anthropic Claude
```bash
nullshift NullShift \
    client_base_url=https://api.anthropic.com/v1 \
    groq_api_key=sk-ant-... \
    model=claude-3-5-sonnet-20241022 \
    github_api_key=ghp_... \
    pr_diff="$(git diff origin/main)"
```

---

## 🏗️ Architecture

NullShift is built on the **Patchwork** framework — a composable system of Steps and Patchflows.

```
┌─────────────────────────────────────────────────────────────────┐
│                        NULLSHIFT PATCHFLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │ DetectUntested  │───►│ GenerateUnit     │───►│ CreateTest  │ │
│  │   Functions     │    │    Tests         │    │     PR      │ │
│  └────────┬────────┘    └────────┬────────┘    └──────┬──────┘ │
│           │                        │                    │        │
│           ▼                        ▼                    ▼        │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │ Parse git diff  │    │ Call Groq LLM    │    │ Commit &    │ │
│  │ Find functions  │    │ Generate pytest  │    │ Open PR     │ │
│  │ Check coverage  │    │ Return tests     │    │ Write files │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | File | Description |
|-----------|------|-------------|
| **NullShift** | `patchwork/patchflows/NullShift/NullShift.py` | Main orchestrator patchflow |
| **DetectUntestedFunctions** | `patchwork/steps/DetectUntestedFunctions/DetectUntestedFunctions.py` | Parses diff, finds untested functions using AST |
| **GenerateUnitTests** | `patchwork/steps/GenerateUnitTests/GenerateUnitTests.py` | Calls LLM to generate pytest tests |
| **CreateTestPR** | `patchwork/steps/CreateTestPR/CreateTestPR.py` | Writes tests to disk and creates GitHub PR |

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
# Install development dependencies
pip install -e ".[all]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=patchwork --cov-report=term-missing

# Run specific test file
pytest tests/cicd/test_nullshift_flow.py -v
```

---

## 📁 Project Structure

```
NullShift/
├── patchwork/                 # Main package
│   ├── patchflows/            # Patchflow definitions
│   │   └── NullShift/
│   │       └── NullShift.py  # Main patchflow
│   ├── steps/                 # Step implementations
│   │   ├── DetectUntestedFunctions/
│   │   ├── GenerateUnitTests/
│   │   └── CreateTestPR/
│   ├── common/                # Shared utilities
│   │   ├── constants.py
│   │   └── client/
│   ├── step.py               # Base Step class
│   ├── app.py                # CLI entry point
│   └── logger.py             # Logging utilities
├── tests/                     # Test suite
│   ├── cicd/                  # Integration tests
│   ├── steps/                 # Unit tests for steps
│   └── common/                # Common utilities tests
├── pyproject.toml             # Project configuration
├── Makefile                   # Build commands
└── README.md                  # This file
```

---

## 🔨 Development

### Setup

```bash
# Clone the repository
git clone https://github.com/NullShift/NullShift.git
cd NullShift

# Install with development dependencies
make install-dev

# Run tests
make test

# Run with coverage
make test-cov
```

### Available Make Commands

| Command | Description |
|---------|-------------|
| `make install` | Install NullShift (production) |
| `make install-dev` | Install with dev dependencies |
| `make test` | Run full test suite |
| `make test-cov` | Run tests with coverage |
| `make lint` | Check code style |
| `make format` | Auto-format code |
| `make clean` | Remove build artifacts |

---

## 🤝 Contributing

Contributions are welcome! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Groq](https://groq.com/) for providing the LLM API
- [Patchwork](https://github.com/patched-codes/patchwork) framework
- [PyGithub](https://github.com/PyGithub/PyGithub) for GitHub API integration
- All contributors and testers

---

## 📚 Related Projects

- [Patchwork](https://github.com/patched-codes/patchwork) - The framework NullShift is built on
- [tree-sitter](https://github.com/tree-sitter/tree-sitter) - AST parsing
- [pytest](https://pytest.org/) - Testing framework

---

<div align="center">

**Made with ❤️ by [Ravikiranreddybada](https://github.com/Ravikiranreddybada)**

*If you find NullShift helpful, please ⭐ star the repository!*

</div>

