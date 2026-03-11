# Contributing to NullShift

Thank you for your interest in contributing to NullShift! This document outlines the process for contributing to the project.

## 🎯 Ways to Contribute

There are many ways to contribute to NullShift:

- 🐛 **Bug Reports** - Report issues you find
- 💡 **Feature Requests** - Suggest new features
- 📝 **Documentation** - Improve docs and examples
- 💻 **Code Contributions** - Submit pull requests
- 🧪 **Testing** - Improve test coverage

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- A Groq API key (for testing LLM integration)
- A GitHub account (for PR creation)

### Development Setup

1. **Fork the repository**
   ```bash
   git clone https://github.com/NullShift/NullShift.git
   cd NullShift
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   # Using Make
   make install-dev

   # Or manually
   pip install -e ".[all]"
   pip install pytest pytest-mock pytest-cov black isort autoflake
   ```

4. **Verify installation**
   ```bash
   make test
   ```

## 📋 Coding Standards

We follow these coding standards:

- **Code Style**: Black (line length: 120)
- **Import Sorting**: isort
- **Type Hints**: Required for public APIs
- **Docstrings**: Google-style docstrings

### Auto-Formatting

Before committing, format your code:

```bash
# Format code
make format

# Check formatting
make lint
```

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/cicd/test_nullshift_flow.py -v

# Run specific test
pytest tests/cicd/test_nullshift_flow.py::TestNullShiftPatchflow::test_full_flow_dry_run -v
```

## 🔧 Project Structure

```
NullShift/
├── patchwork/
│   ├── patchflows/           # Patchflow definitions
│   │   └── NullShift/
│   │       └── NullShift.py
│   ├── steps/                # Step implementations
│   │   ├── DetectUntestedFunctions/
│   │   ├── GenerateUnitTests/
│   │   └── CreateTestPR/
│   ├── common/               # Shared utilities
│   ├── step.py              # Base Step class
│   ├── app.py               # CLI entry point
│   └── logger.py            # Logging
├── tests/                    # Test suite
├── pyproject.toml
├── Makefile
└── README.md
```

## 🏗️ Adding a New Step

Steps are the building blocks of NullShift. Here's how to add one:

1. **Create the step directory**
   ```bash
   mkdir -p patchwork/steps/MyNewStep
   ```

2. **Create `__init__.py`**
   ```python
   from .MyNewStep import MyNewStep

   __all__ = ["MyNewStep"]
   ```

3. **Create the step class**
   ```python
   """MyNewStep module."""
   from __future__ import annotations

   from typing_extensions import TypedDict

   from patchwork.step import Step


   class Inputs(TypedDict):
       required_input: str


   class Outputs(TypedDict):
       output_result: str


   class MyNewStep(Step, input_class=Inputs, output_class=Outputs):
       """Description of what this step does."""

       def __init__(self, inputs: dict):
           super().__init__(inputs)

       def run(self) -> dict:
           # Your implementation here
           return {"output_result": "success"}
   ```

4. **Add tests**
   ```python
   # tests/steps/test_my_new_step.py
   def test_my_new_step():
       step = MyNewStep({"required_input": "test"})
       result = step.run()
       assert result["output_result"] == "success"
   ```

## 📝 Commit Message Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Maintenance

Examples:
```
feat(detect): add support for async functions
fix(generate): handle empty function sources
docs: update README with new examples
test: add unit tests for CreateTestPR
```

## 🐛 Reporting Bugs

When reporting bugs, please include:

1. **Title** - Clear description of the issue
2. **Description** - Detailed explanation
3. **Steps to Reproduce** - How to trigger the bug
4. **Expected vs Actual Behavior** - What should happen vs what happens
5. **Environment** - OS, Python version, etc.
6. **Logs** - Relevant log output

## 💡 Requesting Features

When requesting features:

1. **Use Case** - What problem does this solve?
2. **Proposed Solution** - How should it work?
3. **Alternatives** - Other solutions considered
4. **Additional Context** - Any other relevant information

## 📬 Pull Request Process

1. **Create a branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes** and ensure:
   - Tests pass
   - Code is formatted
   - No linting errors

3. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add my new feature"
   ```

4. **Push to your fork**
   ```bash
   git push origin feature/my-feature
   ```

5. **Open a Pull Request**
   - Fill out the PR template
   - Link any related issues

## 🤝 Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help others learn
- Accept constructive criticism professionally
- Focus on what's best for the community

## 📞 Getting Help

- **GitHub Issues** - For bugs and feature requests
- **GitHub Discussions** - For questions and community support
- **Documentation** - Check the README and ARCHITECTURE.md

## 🙏 Thank You

Thank you for contributing to NullShift! Every contribution helps make this project better for everyone.

