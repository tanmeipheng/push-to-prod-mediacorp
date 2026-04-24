"""
GitHub PR Automator — Creates a local branch with fix commits,
and optionally opens a remote PR via the GitHub API.

Modes:
  - local:  Creates a git branch + commits locally (no push needed).
  - remote: Pushes branch and opens a PR via GitHub API (requires GITHUB_TOKEN).
"""

import os
import subprocess
import time

from github import Github, GithubException


def _git(args: list[str], cwd: str | None = None) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd or _repo_root(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _repo_root() -> str:
    """Return the repo root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_fix_branch(
    fixed_code: str,
    test_code: str,
    incident_report: str,
    fault_type: str,
    source_file_path: str = "vulnerable_app/integration.py",
) -> str:
    """
    Create a local git branch with the fix commits.
    Returns the branch name.
    """
    repo_root = _repo_root()
    timestamp = int(time.time())
    branch_name = f"fix/transient-fault-{fault_type}-{timestamp}"

    # Remember current branch to return to it
    original_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])

    # Create and switch to new branch
    _git(["checkout", "-b", branch_name])
    print(f"   Created branch: {branch_name}")

    # Write fixed source file
    _write_and_commit(
        repo_root, source_file_path, fixed_code,
        f"fix: add {fault_type} resilience to {source_file_path}",
    )

    # Write test file
    _write_and_commit(
        repo_root, "tests/test_integration.py", test_code,
        f"test: add mock test for {fault_type} resilience",
    )

    # Write incident report
    _write_and_commit(
        repo_root, "INCIDENT_REPORT.md", incident_report,
        "docs: add auto-generated incident report",
    )

    # Switch back to original branch
    _git(["checkout", original_branch])
    print(f"   Switched back to {original_branch}")

    return branch_name


def _write_and_commit(repo_root: str, rel_path: str, content: str, message: str):
    """Write a file and commit it."""
    full_path = os.path.join(repo_root, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)
    _git(["add", rel_path])
    _git(["commit", "-m", message])


def push_and_open_pr(
    branch_name: str,
    fault_type: str,
    incident_report: str,
) -> str:
    """
    Push a local branch to origin and open a PR via GitHub API.
    Returns the PR URL.
    """
    # Push branch
    _git(["push", "-u", "origin", branch_name])
    print(f"   Pushed branch: {branch_name}")

    # Open PR via GitHub API
    token = os.environ["GITHUB_TOKEN"]
    repo_name = os.environ["GITHUB_REPO"]

    g = Github(token)
    repo = g.get_repo(repo_name)

    pr = repo.create_pull(
        title=f"🛡️ Auto-Heal: {fault_type} — Inject Resilience Pattern",
        body=incident_report,
        head=branch_name,
        base=repo.default_branch,
    )
    print(f"   PR #{pr.number} opened: {pr.html_url}")
    return pr.html_url
