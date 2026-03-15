"""Git wrapper — all git operations go through subprocess."""

import os
import subprocess
from typing import List, Optional, Tuple


class GitError(Exception):
    """Raised when a git command fails."""
    pass


def _run(args: List[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise GitError(f"git {' '.join(args)} failed: {detail}")
    return result


_PROJECT_GITIGNORE = """\
# OS files
.DS_Store
Thumbs.db
Desktop.ini

# Media files — giteo tracks metadata, not binaries
*.mov
*.mp4
*.mxf
*.avi
*.mkv
*.wav
*.aif
*.aiff
*.mp3
*.aac
*.braw
*.r3d
*.arw
*.dng

# Render output
Render/
Deliver/

# DaVinci Resolve project files (managed by Resolve, not giteo)
*.drp

# Environment / secrets
.env
.env.*

# Python
__pycache__/
*.pyc
"""


def git_init(project_dir: str) -> None:
    """Initialize a new git repo and create .giteo/ config."""
    os.makedirs(project_dir, exist_ok=True)
    _run(["init"], cwd=project_dir)

    # Create .giteo config directory
    giteo_dir = os.path.join(project_dir, ".giteo")
    os.makedirs(giteo_dir, exist_ok=True)

    import json
    config = {"version": "0.1.0", "nle": "resolve"}
    config_path = os.path.join(giteo_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, sort_keys=True)

    # Create timeline and assets directories
    timeline_dir = os.path.join(project_dir, "timeline")
    assets_dir = os.path.join(project_dir, "assets")
    os.makedirs(timeline_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)

    # Write .gitignore for the video project
    gitignore_path = os.path.join(project_dir, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w") as f:
            f.write(_PROJECT_GITIGNORE)


def git_add(project_dir: str, paths: List[str]) -> None:
    """Stage files for commit."""
    _run(["add"] + paths, cwd=project_dir)


def git_commit(project_dir: str, message: str) -> str:
    """Create a commit. Returns the commit hash."""
    result = _run(["commit", "-m", message], cwd=project_dir)
    # Extract short hash from output
    for line in result.stdout.splitlines():
        if line.strip().startswith("["):
            # e.g. "[main abc1234] commit message"
            parts = line.strip().split()
            if len(parts) >= 2:
                return parts[1].rstrip("]")
    return ""


def git_branch(project_dir: str, branch_name: str) -> None:
    """Create and switch to a new branch."""
    _run(["checkout", "-b", branch_name], cwd=project_dir)


def git_checkout(project_dir: str, ref: str) -> None:
    """Switch to a branch or commit."""
    _run(["checkout", ref], cwd=project_dir)


def git_merge(project_dir: str, branch: str) -> Tuple[bool, str]:
    """Attempt to merge a branch. Returns (success, output)."""
    result = _run(["merge", branch], cwd=project_dir, check=False)
    success = result.returncode == 0
    output = result.stdout + result.stderr
    return success, output


def git_merge_abort(project_dir: str) -> None:
    """Abort an in-progress merge."""
    _run(["merge", "--abort"], cwd=project_dir)


def git_diff(project_dir: str, ref: Optional[str] = None) -> str:
    """Get diff output. If ref is given, diff against it."""
    args = ["diff"]
    if ref:
        args.append(ref)
    result = _run(args, cwd=project_dir)
    return result.stdout


def git_diff_staged(project_dir: str) -> str:
    """Get diff of staged changes."""
    result = _run(["diff", "--cached"], cwd=project_dir)
    return result.stdout


def git_log(project_dir: str, max_count: int = 20) -> str:
    """Get formatted log output."""
    result = _run(
        ["log", f"--max-count={max_count}", "--oneline", "--decorate"],
        cwd=project_dir,
    )
    return result.stdout


def git_status(project_dir: str) -> str:
    """Get status output."""
    result = _run(["status", "--short"], cwd=project_dir)
    return result.stdout


def git_revert(project_dir: str) -> None:
    """Revert the last commit."""
    _run(["revert", "HEAD", "--no-edit"], cwd=project_dir)


def git_push(project_dir: str, remote: str = "origin", branch: Optional[str] = None) -> str:
    """Push to remote."""
    args = ["push", remote]
    if branch:
        args.append(branch)
    result = _run(args, cwd=project_dir)
    return result.stdout + result.stderr


def git_pull(project_dir: str, remote: str = "origin", branch: Optional[str] = None) -> str:
    """Pull from remote."""
    args = ["pull", remote]
    if branch:
        args.append(branch)
    result = _run(args, cwd=project_dir)
    return result.stdout + result.stderr


def git_current_branch(project_dir: str) -> str:
    """Get current branch name."""
    result = _run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir)
    return result.stdout.strip()


def git_list_branches(project_dir: str) -> List[str]:
    """List all local branches."""
    result = _run(["branch", "--list"], cwd=project_dir)
    branches = []
    for line in result.stdout.splitlines():
        branch = line.strip().lstrip("* ")
        if branch:
            branches.append(branch)
    return branches


def git_show_file(project_dir: str, ref: str, filepath: str) -> Optional[str]:
    """Get file content at a specific ref (e.g. 'HEAD', 'main', merge base)."""
    result = _run(["show", f"{ref}:{filepath}"], cwd=project_dir, check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def git_merge_base(project_dir: str, ref1: str, ref2: str) -> Optional[str]:
    """Find the merge base between two refs."""
    result = _run(["merge-base", ref1, ref2], cwd=project_dir, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_list_conflicted_files(project_dir: str) -> List[str]:
    """List files with merge conflicts."""
    result = _run(["diff", "--name-only", "--diff-filter=U"], cwd=project_dir, check=False)
    return [f for f in result.stdout.splitlines() if f.strip()]


def git_checkout_theirs(project_dir: str, paths: List[str]) -> None:
    """Resolve conflicts by taking the incoming branch's version."""
    _run(["checkout", "--theirs"] + paths, cwd=project_dir)


def git_is_clean(project_dir: str) -> bool:
    """Check if working directory is clean (no uncommitted or untracked files in tracked dirs)."""
    result = _run(["status", "--porcelain"], cwd=project_dir, check=False)
    return len(result.stdout.strip()) == 0


def is_git_repo(project_dir: str) -> bool:
    """Check if directory is a git repo."""
    if not os.path.isdir(project_dir):
        return False
    result = _run(["rev-parse", "--git-dir"], cwd=project_dir, check=False)
    return result.returncode == 0


def find_project_root(start_dir: Optional[str] = None) -> Optional[str]:
    """Find the giteo project root by looking for .giteo/ directory."""
    current = start_dir or os.getcwd()
    while True:
        if os.path.isdir(os.path.join(current, ".giteo")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def git_log_with_changes(project_dir: str, max_count: int = 20) -> List[dict]:
    """Get commit log with file change information for each commit.

    Returns list of dicts with: hash, message, branch, date, files_changed
    """
    result = _run(
        [
            "log",
            f"--max-count={max_count}",
            "--pretty=format:%H|%s|%ad|%D",
            "--date=relative",
            "--name-only",
        ],
        cwd=project_dir,
        check=False,
    )
    if result.returncode != 0:
        return []

    commits = []
    lines = result.stdout.strip().split("\n")
    current_commit = None

    for line in lines:
        if "|" in line and line.count("|") >= 3:
            # This is a commit line
            if current_commit:
                commits.append(current_commit)
            parts = line.split("|", 3)
            hash_val = parts[0]
            message = parts[1]
            date = parts[2]
            refs = parts[3] if len(parts) > 3 else ""

            # Extract branch from refs
            branch = "main"
            if refs:
                for ref in refs.split(","):
                    ref = ref.strip()
                    if ref.startswith("HEAD -> "):
                        branch = ref.replace("HEAD -> ", "")
                        break
                    elif "/" not in ref and ref not in ("HEAD", ""):
                        branch = ref
                        break

            current_commit = {
                "hash": hash_val[:7],
                "message": message,
                "date": date,
                "branch": branch,
                "files_changed": [],
            }
        elif line.strip() and current_commit:
            # This is a file path
            current_commit["files_changed"].append(line.strip())

    if current_commit:
        commits.append(current_commit)

    return commits


def categorize_commit(files_changed: List[str]) -> str:
    """Determine the dominant category for a commit based on files changed.

    Returns: 'audio', 'video', or 'color'
    """
    counts = {"audio": 0, "video": 0, "color": 0}

    for f in files_changed:
        if "audio" in f.lower():
            counts["audio"] += 1
        elif "color" in f.lower():
            counts["color"] += 1
        elif "cuts" in f.lower() or "video" in f.lower():
            counts["video"] += 1

    # Return category with most changes, default to video
    max_cat = max(counts, key=counts.get)
    if counts[max_cat] == 0:
        return "video"
    return max_cat


def git_log_with_topology(project_dir: str, max_count: int = 30) -> dict:
    """Get commit log with parent information for graph visualization.

    Returns dict with:
        - commits: list of commit dicts with:
            - hash, parents, message, branch, is_head
            - is_main_commit: True if commit is reachable from main (for visual positioning)
        - branches: list of branch names encountered
        - head: hash of current HEAD commit
    """
    # Get HEAD hash
    head_result = _run(["rev-parse", "HEAD"], cwd=project_dir, check=False)
    head_hash = head_result.stdout.strip()[:7] if head_result.returncode == 0 else ""

    # Get current branch
    current_result = _run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir, check=False)
    current_branch = current_result.stdout.strip() if current_result.returncode == 0 else "main"

    # Determine the main branch name (main or master)
    main_branch = "main"
    for candidate in ["main", "master"]:
        check = _run(["rev-parse", "--verify", candidate], cwd=project_dir, check=False)
        if check.returncode == 0:
            main_branch = candidate
            break

    # Get commits reachable from main branch (for visual positioning)
    main_commits = set()
    main_cmd = ["log", main_branch, "--pretty=format:%H"]
    if max_count > 0:
        main_cmd.insert(2, f"--max-count={max_count}")
    main_log = _run(main_cmd, cwd=project_dir, check=False)
    if main_log.returncode == 0:
        for line in main_log.stdout.strip().split("\n"):
            if line.strip():
                main_commits.add(line.strip()[:7])

    # Get commits with parent hashes
    log_cmd = ["log", "--all", "--pretty=format:%H|%P|%s|%D", "--date-order"]
    if max_count > 0:
        log_cmd.insert(2, f"--max-count={max_count}")
    result = _run(log_cmd, cwd=project_dir, check=False)
    if result.returncode != 0:
        return {"commits": [], "branches": [], "head": ""}

    commits = []
    branch_set = set()

    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) < 3:
            continue

        hash_full = parts[0]
        hash_short = hash_full[:7]
        parents_str = parts[1]
        message = parts[2]
        refs = parts[3] if len(parts) > 3 else ""

        # Parse parents
        parents = [p[:7] for p in parents_str.split() if p]

        # Check if this commit is reachable from main (for visual positioning)
        is_main_commit = hash_short in main_commits

        # Extract branch name from refs (for labeling)
        branch = None
        is_head = False
        if refs:
            for ref in refs.split(","):
                ref = ref.strip()
                if ref.startswith("HEAD -> "):
                    branch = ref.replace("HEAD -> ", "")
                    is_head = True
                    break
                elif ref == "HEAD":
                    is_head = True
                elif "/" not in ref and ref not in ("HEAD", ""):
                    if branch is None:
                        branch = ref

        # If no branch found from refs, use context
        if branch is None:
            if is_main_commit:
                branch = main_branch
            else:
                branch = current_branch

        branch_set.add(branch)

        commits.append({
            "hash": hash_short,
            "parents": parents,
            "message": message,
            "branch": branch,
            "is_head": is_head or hash_short == head_hash,
            "is_main_commit": is_main_commit,  # For visual positioning
        })

    return {
        "commits": commits,
        "branches": list(branch_set),
        "head": head_hash,
    }
