"""
Shared pytest fixtures for NullShift tests.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture()
def simple_diff() -> str:
    """A minimal unified diff adding one Python function."""
    return textwrap.dedent(
        """\
        diff --git a/patchwork/utils.py b/patchwork/utils.py
        index 0000000..1111111 100644
        --- a/patchwork/utils.py
        +++ b/patchwork/utils.py
        @@ -0,0 +1,6 @@
        +def add(a, b):
        +    \"\"\"Return the sum of a and b.\"\"\"
        +    return a + b
        """
    )


@pytest.fixture()
def multi_function_diff() -> str:
    """A diff that adds two functions, one of which is tested."""
    return textwrap.dedent(
        """\
        diff --git a/patchwork/math_utils.py b/patchwork/math_utils.py
        index 0000000..2222222 100644
        --- a/patchwork/math_utils.py
        +++ b/patchwork/math_utils.py
        @@ -0,0 +1,10 @@
        +def multiply(a, b):
        +    return a * b
        +
        +def divide(a, b):
        +    if b == 0:
        +        raise ValueError("Division by zero")
        +    return a / b
        """
    )


@pytest.fixture()
def repo_with_source(tmp_path: Path) -> Path:
    """
    Creates a minimal fake repository:
      tmp_path/
        patchwork/
          utils.py        ← contains `add` function
        tests/
          test_other.py   ← references something else (not `add`)
    """
    src = tmp_path / "patchwork"
    src.mkdir()
    (src / "utils.py").write_text(
        textwrap.dedent(
            """\
            def add(a, b):
                \"\"\"Return the sum of a and b.\"\"\"
                return a + b
            """
        )
    )

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_other.py").write_text(
        textwrap.dedent(
            """\
            def test_placeholder():
                assert True
            """
        )
    )

    return tmp_path


@pytest.fixture()
def repo_with_tests(tmp_path: Path) -> Path:
    """
    Same as repo_with_source but the test file DOES reference `add`.
    """
    src = tmp_path / "patchwork"
    src.mkdir()
    (src / "utils.py").write_text(
        textwrap.dedent(
            """\
            def add(a, b):
                return a + b
            """
        )
    )

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_utils.py").write_text(
        textwrap.dedent(
            """\
            from patchwork.utils import add

            def test_add():
                assert add(1, 2) == 3
            """
        )
    )

    return tmp_path


@pytest.fixture()
def sample_untested_functions() -> list:
    return [
        {
            "name": "add",
            "file": "patchwork/utils.py",
            "lineno": 1,
            "source": "def add(a, b):\n    return a + b",
            "class_name": None,
        }
    ]


@pytest.fixture()
def sample_generated_tests() -> list:
    return [
        {
            "source_file": "patchwork/utils.py",
            "test_file": "tests/test_utils.py",
            "test_source": "import pytest\nfrom patchwork.utils import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
            "function_name": "add",
            "class_name": None,
        }
    ]
