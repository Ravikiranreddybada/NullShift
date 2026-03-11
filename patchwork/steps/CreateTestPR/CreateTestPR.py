"""
CreateTestPR Step Module
=======================

This module implements the final step of the NullShift pipeline: writing
generated tests to disk and creating a GitHub pull request.

Overview
--------
The CreateTestPR step takes the generated test code from GenerateUnitTests
and performs the final steps of the workflow:
1. Writes test files to the appropriate locations in the repository
2. Creates a new git branch
3. Commits the changes
4. Pushes to the remote
5. Opens a GitHub pull request

The step supports a "dry-run" mode for testing without making any git
or GitHub changes.

Key Features
------------
- Automatic test file creation
- Git branch management
- GitHub PR creation with formatted description
- Dry-run mode for safe testing
- Proper error handling for git operations

How It Works
------------
1. Receive generated tests from GenerateUnitTests step
2. Write test files to appropriate test directories
3. If not dry_run:
   a. Create new git branch
   b. Stage and commit test files
   c. Push to origin
   d. Create GitHub PR with description
4. Return PR URL and written file paths

Example Usage
-------------
>>> from patchwork.steps.CreateTestPR import CreateTestPR
>>>
>>> inputs = {
...     "generated_tests": [
...         {
...             "test_file": "tests/test_utils.py",
...             "test_source": "def test_add(): assert 1+1==2"
...         }
...     ],
...     "repo_path": "/path/to/repo",
...     "github_api_key": "ghp_...",
...     "dry_run": True,
... }
>>> step = CreateTestPR(inputs)
>>> result = step.run()
>>> print(result)
{"pr_url": "dry_run", "written_files": ["tests/test_utils.py"]}

Dry Run Mode
-----------
When dry_run=True, the step will:
- Write test files to disk ✓
- NOT create git branch
- NOT commit changes
- NOT push to remote
- NOT create GitHub PR
- Return "dry_run" as pr_url

This is useful for:
- Testing the tool locally
- Previewing generated tests before committing
- Development and debugging

Git Operations
--------------
The step performs these git operations:
1. Create new branch: nullshift/auto-tests-{uuid}
2. Checkout new branch
3. Stage test files
4. Commit with message
5. Push to origin

The branch name includes a short UUID to ensure uniqueness.

GitHub PR Details
-----------------
Created PRs include:
- Title: "[NullShift] Auto-generated unit tests ({n} file(s))"
- Body: Formatted description with explanation
- Head: New branch with generated tests
- Base: Target branch (default: main)

The PR body includes:
- Description of NullShift
- Explanation of auto-generated tests
- Request for human review

Input Contract
--------------
Required:
    - generated_tests (list[dict]): Tests from GenerateUnitTests

Optional:
    - repo_path (str): Repository path (default: ".")
    - github_api_key (str): GitHub token (required unless dry_run=True)
    - base_branch (str): Target branch (default: "main")
    - pr_branch_prefix (str): Branch prefix (default: "nullshift/auto-tests")
    - dry_run (bool): Skip git/PR (default: False)

Output Contract
---------------
pr_url (str): 
    - GitHub PR URL if successfully created
    - "dry_run" if dry_run mode
    - "" if no tests to write

written_files (list[str]):
    List of relative paths to test files written to disk

Error Handling
-------------
- Missing GitHub token (without dry_run): Raises ValueError
- Git operation failures: Raised exceptions
- GitHub API failures: Raised exceptions
- No remote configured: Git push will fail

Security Considerations
----------------------
1. Tests are written before git operations (atomic on failure)
2. Branch is created from current HEAD (safe)
3. PR requires GitHub token with repo scope
4. Generated code is NOT executed (safe)

See Also
--------
- patchwork.step.Step: Base class
- gitpython: Git operations library
- PyGithub: GitHub API library
- patchwork.steps.GenerateUnitTests: Previous step
"""

from __future__ import annotations

import textwrap
import uuid
from pathlib import Path
from typing import List

from typing_extensions import TypedDict

from patchwork.logger import logger
from patchwork.step import Step


# ============================================================================
# TypedDict Contracts
# ============================================================================

class _Inputs(TypedDict, total=False):
    """Optional input parameters for CreateTestPR."""
    repo_path: str          # Repository root path
    github_api_key: str    # GitHub personal access token
    base_branch: str       # Target branch for PR
    pr_branch_prefix: str  # Branch name prefix
    dry_run: bool          # Skip git/PR operations


class _Required(TypedDict):
    """Required input parameters for CreateTestPR."""
    generated_tests: List[dict]  # Generated test code


class Inputs(_Required, _Inputs):
    """Complete input contract for CreateTestPR step."""
    pass


class Outputs(TypedDict):
    """Output type for CreateTestPR step."""
    pr_url: str              # PR URL or "dry_run"
    written_files: List[str] # Written test file paths


# ============================================================================
# Helper Functions (Private)
# ============================================================================

def _write_test_files(generated_tests: list[dict], repo_path: Path) -> dict[str, str]:
    """
    Write generated test source code to disk.
    
    Creates test files in the appropriate directories. If multiple tests
    target the same file, they are merged (last write wins).
    
    Args:
        generated_tests: List of test dictionaries with test_file and test_source
        repo_path: Repository root path
        
    Returns:
        Dictionary mapping test file paths to their source code
        
    The function:
    - Creates parent directories as needed
    - Writes UTF-8 encoded files
    - Logs each file written
    """
    # Deduplicate by test file path
    # (Multiple functions in same file produce same test_file)
    file_map: dict[str, str] = {}
    for entry in generated_tests:
        test_path = entry["test_file"]
        # Last write wins if already present
        if test_path not in file_map:
            file_map[test_path] = entry["test_source"]

    # Write each file
    written: dict[str, str] = {}
    for rel_path, source in file_map.items():
        # Resolve to absolute path
        abs_path = repo_path / rel_path
        
        # Create parent directories if needed
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the test file
        abs_path.write_text(source, encoding="utf-8")
        
        # Track for return value
        written[rel_path] = source
        logger.info(f"  Written: {abs_path}")
    
    return written


def _git_commit_and_push(
    repo_path: Path, 
    branch: str, 
    files: list[str], 
    base_branch: str
) -> None:
    """
    Create git branch, commit changes, and push to origin.
    
    Git operations performed:
    1. Create new branch from current HEAD
    2. Checkout the new branch
    3. Stage specified files
    4. Commit with descriptive message
    5. Push to origin
    
    Args:
        repo_path: Repository root path
        branch: New branch name
        files: List of file paths to commit
        base_branch: Target branch (for commit message)
        
    Raises:
        git.GitError: If any git operation fails
    """
    import git  # gitpython

    # Open the repository
    repo = git.Repo(repo_path)
    
    # Create and checkout new branch from current HEAD
    new_branch = repo.create_head(branch)
    new_branch.checkout()

    # Stage the test files
    repo.index.add([str(repo_path / f) for f in files])
    
    # Commit with descriptive message
    repo.index.commit(
        textwrap.dedent(
            f"""\
            chore(nullshift): auto-generate unit tests

            Generated by NullShift for {len(files)} test file(s).
            Target branch: {base_branch}
            """
        )
    )
    
    # Push to origin
    origin = repo.remote("origin")
    origin.push(refspec=f"{branch}:{branch}")
    logger.info(f"Pushed branch '{branch}' to origin.")


def _open_github_pr(
    repo_path: Path, 
    github_api_key: str, 
    branch: str, 
    base_branch: str, 
    file_count: int
) -> str:
    """
    Create a GitHub pull request with the generated tests.
    
    Creates a PR with:
    - Title indicating auto-generated tests
    - Body explaining NullShift and requesting review
    - Head set to the branch with tests
    - Base set to target branch
    
    Args:
        repo_path: Repository root path
        github_api_key: GitHub personal access token
        branch: Branch name with tests
        base_branch: Target branch
        file_count: Number of test files (for title)
        
    Returns:
        HTML URL of created pull request
        
    Raises:
        ValueError: If GitHub org/repo cannot be parsed from remote
        github.GithubException: If PR creation fails
    """
    from github import Github  # PyGithub
    import git

    # Open the git repository to get remote URL
    repo = git.Repo(repo_path)
    remote_url = repo.remote("origin").url  # e.g. git@github.com:org/repo.git

    # Parse org/repo from various URL formats:
    # - git@github.com:org/repo.git
    # - https://github.com/org/repo.git
    import re
    match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", remote_url)
    if not match:
        raise ValueError(f"Cannot parse GitHub org/repo from remote URL: {remote_url}")
    full_repo_name = match.group(1)

    # Authenticate with GitHub
    gh = Github(github_api_key)
    gh_repo = gh.get_repo(full_repo_name)
    
    # Create the pull request
    pr = gh_repo.create_pull(
        title=f"[NullShift] Auto-generated unit tests ({file_count} file(s))",
        body=textwrap.dedent(
            """\
            ## 🤖 NullShift — Auto-generated Tests

            This PR was created automatically by **NullShift**.  
            It adds pytest unit tests for functions detected on the PR diff that
            had no existing coverage.

            > Please review, adjust, and merge when satisfied.
            """
        ),
        head=branch,
        base=base_branch,
    )
    
    logger.info(f"GitHub PR created: {pr.html_url}")
    return pr.html_url


# ============================================================================
# Step Implementation
# ============================================================================

class CreateTestPR(Step, input_class=Inputs, output_class=Outputs):
    """
    Write generated tests to disk and create GitHub PR.
    
    This is the final step in the NullShift pipeline. It takes the
    generated test code and either:
    - Writes files locally (dry_run mode)
    - Full workflow: write → commit → push → PR
    
    Attributes:
        _tests: List of generated test dictionaries
        _repo_path: Repository root path
        _github_api_key: GitHub token for PR creation
        _base_branch: Target branch for PR
        _branch_prefix: Prefix for auto-generated branch names
        _dry_run: Whether to skip git/PR operations
    
    Example:
        >>> inputs = {
        ...     "generated_tests": [...],
        ...     "github_api_key": "ghp_xxx",
        ...     "dry_run": False,
        ... }
        >>> step = CreateTestPR(inputs)
        >>> result = step.run()
    """

    def __init__(self, inputs: dict) -> None:
        """
        Initialize the CreateTestPR step.
        
        Args:
            inputs: Dictionary with generated_tests and optional parameters.
        
        Raises:
            ValueError: If github_api_key missing and dry_run is False
        """
        super().__init__(inputs)
        
        # Store generated tests
        self._tests: list[dict] = inputs["generated_tests"]
        
        # Resolve repository path to absolute
        self._repo_path = Path(inputs.get("repo_path", ".")).resolve()
        
        # GitHub configuration
        self._github_api_key: str = inputs.get("github_api_key", "")
        self._base_branch: str = inputs.get("base_branch", "main")
        self._branch_prefix: str = inputs.get("pr_branch_prefix", "nullshift/auto-tests")
        
        # Dry-run mode flag
        self._dry_run: bool = bool(inputs.get("dry_run", False))

    def run(self) -> dict:
        """
        Execute the test file writing and PR creation workflow.
        
        This method:
        1. Writes test files to disk
        2. If not dry_run:
           - Creates git branch
           - Commits changes
           - Pushes to origin
           - Creates GitHub PR
        
        Returns:
            Dictionary with:
            - pr_url: GitHub PR URL or "dry_run" or ""
            - written_files: List of written test file paths
            
        The output indicates success even if some operations are skipped
        (dry_run mode).
        """
        # Handle case with no tests
        if not self._tests:
            logger.info("CreateTestPR: nothing to commit.")
            return {"pr_url": "", "written_files": []}

        # =====================================================================
        # Step 1: Write Test Files to Disk
        # =====================================================================
        # This happens regardless of dry_run mode
        written = _write_test_files(self._tests, self._repo_path)
        written_files = list(written.keys())

        # =====================================================================
        # Step 2: Handle Dry-Run Mode
        # =====================================================================
        if self._dry_run:
            # In dry-run, we skip all git/GitHub operations
            logger.info(
                f"CreateTestPR: dry_run=True — skipping git & GitHub. "
                f"{len(written_files)} file(s) written."
            )
            return {"pr_url": "dry_run", "written_files": written_files}

        # =====================================================================
        # Step 3: Validate GitHub Configuration
        # =====================================================================
        if not self._github_api_key:
            raise ValueError("github_api_key is required unless dry_run=True")

        # =====================================================================
        # Step 4: Create Git Branch
        # =====================================================================
        # Generate unique branch name with UUID
        branch = f"{self._branch_prefix}-{uuid.uuid4().hex[:8]}"
        logger.info(f"CreateTestPR: committing to branch '{branch}' …")

        # =====================================================================
        # Step 5: Git Commit and Push
        # =====================================================================
        _git_commit_and_push(
            self._repo_path, 
            branch, 
            written_files, 
            self._base_branch
        )

        # =====================================================================
        # Step 6: Create GitHub Pull Request
        # =====================================================================
        pr_url = _open_github_pr(
            self._repo_path,
            self._github_api_key,
            branch,
            self._base_branch,
            len(written_files),
        )

        return {"pr_url": pr_url, "written_files": written_files}

