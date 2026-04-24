"""
GitHub PR Automator — Best-practices Git + GitHub workflow.

Three-step flow:
  1. create_fix_branch()  — Build a feature branch with fix commits locally
                            using git plumbing (working tree stays untouched).
  2. push_branch()        — Push the local branch to the remote.
  3. open_pull_request()  — Open a PR on GitHub targeting the base branch.

Each step is independent and idempotent so the pipeline can stop at any
point (e.g. local-only during development) and resume later.
"""

import os
import subprocess
import tempfile
import time

from github import Github


# ── Configuration ─────────────────────────────────────────────

def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _base_branch() -> str:
    """Return the branch we target PRs against (reads env or defaults)."""
    return os.environ.get("TFAH_BASE_BRANCH", "main")


# ── Git helper ────────────────────────────────────────────────

def _git(
    args: list[str],
    cwd: str | None = None,
    input_data: str | None = None,
    env: dict | None = None,
) -> str:
    """Run a git command and return stdout. Raises on non-zero exit."""
    run_env = env or os.environ.copy()
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd or _repo_root(),
        capture_output=True,
        text=True,
        input=input_data,
        env=run_env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


# ── Step 1: Create feature branch (local, no checkout) ────────

def create_fix_branch(
    fixed_code: str,
    test_code: str,
    incident_report: str,
    fault_type: str,
    source_file_path: str = "vulnerable_app/integration.py",
) -> str:
    """
    Create a local feature branch with three atomic commits.

    Uses git plumbing (hash-object, read-tree, update-index, write-tree,
    commit-tree) so the working tree and index are never touched.
    Safe to run while the user is on any branch.

    Returns the branch name.
    """
    timestamp = int(time.time())
    branch_name = f"fix/transient-fault-{fault_type}-{timestamp}"
    parent_sha = _git(["rev-parse", "HEAD"])

    # Commit 1 — patched source
    parent_sha = _plumbing_commit(
        parent_sha, source_file_path, fixed_code,
        f"fix: add {fault_type} resilience to {source_file_path}",
    )

    # Commit 2 — test file
    parent_sha = _plumbing_commit(
        parent_sha, "tests/test_integration.py", test_code,
        f"test: add mock test for {fault_type} resilience",
    )

    # Commit 3 — incident report
    parent_sha = _plumbing_commit(
        parent_sha, "INCIDENT_REPORT.md", incident_report,
        "docs: add auto-generated incident report",
    )

    _git(["branch", branch_name, parent_sha])
    return branch_name


def _plumbing_commit(
    parent_sha: str, rel_path: str, content: str, message: str,
) -> str:
    """Create a commit that adds/updates one file, returns new commit SHA."""
    repo_root = _repo_root()
    blob_sha = _git(["hash-object", "-w", "--stdin"], input_data=content)

    # Temp index so the real one is untouched
    with tempfile.NamedTemporaryFile(suffix=".idx", delete=False) as tmp:
        tmp_index = tmp.name

    try:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = tmp_index

        # Populate temp index from parent tree
        subprocess.run(
            ["git", "read-tree", parent_sha],
            cwd=repo_root, env=env, check=True, capture_output=True,
        )

        # Slot in the new blob
        subprocess.run(
            ["git", "update-index", "--add",
             "--cacheinfo", f"100644,{blob_sha},{rel_path}"],
            cwd=repo_root, env=env, check=True, capture_output=True,
        )

        # Materialise the tree object
        result = subprocess.run(
            ["git", "write-tree"],
            cwd=repo_root, env=env, check=True,
            capture_output=True, text=True,
        )
        tree_sha = result.stdout.strip()
    finally:
        os.unlink(tmp_index)

    return _git(["commit-tree", tree_sha, "-p", parent_sha, "-m", message])


# ── Step 2: Push branch to remote ─────────────────────────────

def push_branch(branch_name: str, remote: str = "origin") -> None:
    """Push a local branch to the remote. Idempotent (force-updates)."""
    _git(["push", "-u", remote, branch_name])


# ── Step 3: Open Pull Request on GitHub ───────────────────────

def open_pull_request(
    branch_name: str,
    fault_type: str,
    incident_report: str,
    base_branch: str | None = None,
) -> str:
    """
    Open a PR on GitHub from *branch_name* → *base_branch*.
    Returns the PR HTML URL.
    """
    token = os.environ["GITHUB_TOKEN"]
    repo_name = os.environ["GITHUB_REPO"]
    base = base_branch or _base_branch()

    g = Github(token)
    repo = g.get_repo(repo_name)

    pr = repo.create_pull(
        title=f"🛡️ Auto-Heal: {fault_type} — Inject Resilience Pattern",
        body=incident_report,
        head=branch_name,
        base=base,
    )
    return pr.html_url


# ── Convenience: full flow in one call ────────────────────────

def create_and_push_pr(
    fixed_code: str,
    test_code: str,
    incident_report: str,
    fault_type: str,
    source_file_path: str = "vulnerable_app/integration.py",
    push: bool = True,
) -> tuple[str, str | None]:
    """
    End-to-end: branch → push → PR.

    Returns (branch_name, pr_url).
    Set push=False for local-only mode (pr_url will be None).
    """
    branch_name = create_fix_branch(
        fixed_code, test_code, incident_report,
        fault_type, source_file_path,
    )
    print(f"   Created branch: {branch_name}")

    if not push:
        return branch_name, None

    push_branch(branch_name)
    print(f"   Pushed branch to origin")

    pr_url = open_pull_request(branch_name, fault_type, incident_report)
    print(f"   PR opened: {pr_url}")

    return branch_name, pr_url


def push_existing_branch_and_pr(
    branch_name: str,
    fault_type: str,
    incident_report: str,
) -> str:
    """
    Push an already-created local branch and open a PR.

    Used when the branch was created during a pipeline run (push=False)
    and the user later wants to promote it to a PR.

    Returns the PR HTML URL.
    """
    push_branch(branch_name)
    print(f"   Pushed existing branch: {branch_name}")

    pr_url = open_pull_request(branch_name, fault_type, incident_report)
    print(f"   PR opened: {pr_url}")

    return pr_url
