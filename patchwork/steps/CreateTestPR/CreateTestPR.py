"""
CreateTestPR
============
Writes the generated test files to the repository, commits them on a new
branch, and opens a pull request on GitHub.

Inputs (TypedDict)
------------------
- ``generated_tests``   : list[dict] – from GenerateUnitTests
- ``repo_path``         : str        – local path to the git repository root
- ``github_api_key``    : str        – GitHub personal access token
- ``pr_branch_prefix``  : str        – branch prefix (default: "nullshift/auto-tests")
- ``pr_title``          : str        – PR title (default: auto-generated)
- ``pr_body``           : str        – PR body  (default: auto-generated)
- ``base_branch``       : str        – target branch (default: "main")
- ``dry_run``           : bool       – if True, write files but skip git/PR (default: False)

Outputs (TypedDict)
-------------------
- ``pr_url``            : str  – URL of the created PR (empty string on dry_run)
- ``test_files_written``: list[str] – repo-relative paths of files written
- ``branch_name``       : str  – name of the created branch
"""
from __future__ import annotations

import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from typing_extensions import TypedDict

from patchwork.step import Step, StepStatus

# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------


class CreateTestPRInputs(TypedDict, total=False):
    generated_tests: List[Dict]
    repo_path: str
    github_api_key: str
    pr_branch_prefix: str
    pr_title: str
    pr_body: str
    base_branch: str
    dry_run: bool


class CreateTestPROutputs(TypedDict):
    pr_url: str
    test_files_written: List[str]
    branch_name: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pr_body(generated_tests: List[Dict]) -> str:
    lines = [
        "## 🤖 Auto-generated Unit Tests by NullShift",
        "",
        "This PR was created automatically by [NullShift](https://github.com/Ravikiranreddybada/NullShift).",
        "It adds pytest unit tests for functions that were modified in the triggering PR but lacked test coverage.",
        "",
        "### Functions covered",
        "",
    ]
    for entry in generated_tests:
        class_prefix = f"{entry['class_name']}." if entry.get("class_name") else ""
        lines.append(f"- `{class_prefix}{entry['function_name']}` in `{entry['source_file']}`")
    lines += [
        "",
        "> **Review these tests carefully** before merging — LLM-generated tests may",
        "> need adjustment to match your domain logic.",
    ]
    return "\n".join(lines)


def _merge_test_files(generated_tests: List[Dict]) -> Dict[str, str]:
    """
    Merge multiple generated tests that target the same test file into a single
    source blob (de-duplicating identical import lines).
    """
    merged: Dict[str, List[str]] = {}
    for entry in generated_tests:
        test_file = entry["test_file"]
        merged.setdefault(test_file, []).append(entry["test_source"])

    result: Dict[str, str] = {}
    for test_file, sources in merged.items():
        # Simple concat with a separator comment
        combined = "\n\n# " + "-" * 60 + "\n\n".join(sources)
        result[test_file] = combined
    return result


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------


class CreateTestPR(
    Step,
    input_class=CreateTestPRInputs,
    output_class=CreateTestPROutputs,
):
    """
    Commits generated test files and opens a GitHub pull-request.
    """

    def __init__(self, inputs: Dict):
        super().__init__(inputs)
        self.generated_tests: List[Dict] = inputs.get("generated_tests", [])
        self.repo_path = Path(inputs.get("repo_path", "."))
        self.github_api_key: Optional[str] = inputs.get("github_api_key")
        self.branch_prefix: str = inputs.get("pr_branch_prefix", "nullshift/auto-tests")
        self.pr_title: Optional[str] = inputs.get("pr_title")
        self.pr_body: Optional[str] = inputs.get("pr_body")
        self.base_branch: str = inputs.get("base_branch", "main")
        self.dry_run: bool = bool(inputs.get("dry_run", False))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_test_files(self, merged: Dict[str, str]) -> List[str]:
        written: List[str] = []
        for rel_path, source in merged.items():
            abs_path = self.repo_path / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to existing test file or create new one
            if abs_path.exists():
                existing = abs_path.read_text(encoding="utf-8")
                source = existing.rstrip() + "\n\n" + source

            abs_path.write_text(source, encoding="utf-8")
            written.append(rel_path)
        return written

    def _git_commit_and_push(self, branch_name: str, files: List[str]) -> None:
        import git

        repo = git.Repo(self.repo_path)
        # Create and checkout new branch
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()

        for rel_path in files:
            repo.index.add([str(self.repo_path / rel_path)])

        repo.index.commit(
            f"test: add auto-generated unit tests via NullShift\n\n"
            f"Generated for {len(files)} file(s): {', '.join(files)}"
        )
        origin = repo.remote(name="origin")
        origin.push(refspec=f"{branch_name}:{branch_name}")

    def _create_github_pr(self, branch_name: str, title: str, body: str) -> str:
        from github import Github

        g = Github(self.github_api_key)
        # Determine repo from git remote URL
        import git

        repo_obj = git.Repo(self.repo_path)
        remote_url: str = repo_obj.remotes.origin.url
        # Strip .git suffix and extract owner/repo
        remote_url = remote_url.rstrip("/").removesuffix(".git")
        repo_name = "/".join(remote_url.split("/")[-2:])

        gh_repo = g.get_repo(repo_name)
        pr = gh_repo.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base=self.base_branch,
        )
        return pr.html_url

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(self) -> Dict:
        from patchwork.logger import logger

        if not self.generated_tests:
            self.set_status(StepStatus.SKIPPED, "No generated tests to commit.")
            return {"pr_url": "", "test_files_written": [], "branch_name": ""}

        merged = _merge_test_files(self.generated_tests)
        files_written = self._write_test_files(merged)
        logger.info(f"CreateTestPR: wrote {len(files_written)} test file(s): {files_written}")

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        branch_name = f"{self.branch_prefix}-{timestamp}"

        pr_title = self.pr_title or (
            f"test: auto-generated unit tests for "
            f"{len(self.generated_tests)} function(s) [NullShift]"
        )
        pr_body = self.pr_body or _build_pr_body(self.generated_tests)

        if self.dry_run:
            logger.info(
                f"CreateTestPR: dry_run=True — skipping git commit and PR creation.\n"
                f"  Would create branch: {branch_name}\n"
                f"  PR title: {pr_title}"
            )
            return {
                "pr_url": "",
                "test_files_written": files_written,
                "branch_name": branch_name,
            }

        try:
            self._git_commit_and_push(branch_name, files_written)
            pr_url = self._create_github_pr(branch_name, pr_title, pr_body)
            logger.info(f"CreateTestPR: PR created → {pr_url}")
            return {
                "pr_url": pr_url,
                "test_files_written": files_written,
                "branch_name": branch_name,
            }
        except Exception as exc:
            self.set_status(StepStatus.FAILED, str(exc))
            raise
