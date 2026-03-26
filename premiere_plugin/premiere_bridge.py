"""Premiere Bridge — stdin/stdout JSON dispatcher to vit.core.

Spawned as a subprocess by the CEP panel's Node.js layer.
Reads newline-delimited JSON from stdin, writes JSON responses to stdout.

Unlike the Resolve launcher, this bridge does NOT call serialize/deserialize —
that's handled by ExtendScript in the CEP panel. This bridge only handles
git operations via vit.core.

Usage: python -u premiere_bridge.py --project-dir /path/to/project
"""
import json
import os
import sys
import traceback

# Bootstrap: find the vit package
_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
if os.path.isdir(os.path.join(_root, "vit")) and _root not in sys.path:
    sys.path.insert(0, _root)


def _log(msg):
    """Log to stderr (stdout is reserved for IPC)."""
    sys.stderr.write(f"[vit-bridge] {msg}\n")
    sys.stderr.flush()


def handle_request(request, project_dir):
    """Handle a JSON request from the Node.js layer.

    Returns a JSON-serializable response dict.
    Modeled after resolve_plugin/vit_panel_launcher.py:handle_request(),
    but without Resolve-specific serialize/deserialize calls.
    """
    action = request.get("action")

    try:
        if action == "ping":
            return {"ok": True}

        elif action == "get_branch":
            from vit.core import git_current_branch
            branch = git_current_branch(project_dir)
            return {"ok": True, "branch": branch}

        elif action == "save":
            from vit.core import git_add, git_commit, GitError

            msg = request.get("message", "save version")
            # Files are already written by the Node.js layer
            git_add(project_dir, ["timeline/", "assets/", ".vit/", ".gitignore"])
            try:
                hash_val = git_commit(project_dir, f"vit: {msg}")
                return {"ok": True, "hash": hash_val, "message": msg}
            except GitError as e:
                if "nothing to commit" in str(e):
                    return {"ok": True, "message": "Nothing to commit — unchanged."}
                return {"ok": False, "error": str(e)}

        elif action == "new_branch":
            from vit.core import git_branch
            name = request.get("name", "").strip()
            if not name:
                return {"ok": False, "error": "No branch name provided."}
            git_branch(project_dir, name)
            return {"ok": True, "branch": name}

        elif action == "list_branches":
            from vit.core import git_list_branches, git_current_branch
            branches = git_list_branches(project_dir)
            current = git_current_branch(project_dir)
            return {"ok": True, "branches": branches, "current": current}

        elif action == "switch_branch":
            from vit.core import git_checkout, git_current_branch

            target = request.get("branch", "")
            current = git_current_branch(project_dir)
            if target and target != current:
                git_checkout(project_dir, target)
            return {"ok": True, "branch": target}

        elif action == "merge":
            from vit.core import (
                git_add, git_commit, git_merge, git_is_clean,
                git_current_branch, git_list_conflicted_files,
                git_checkout_theirs, GitError,
            )
            from vit.validator import validate_project, format_issues

            target = request.get("branch", "")
            current = git_current_branch(project_dir)

            # Auto-save if dirty (files already written by Node.js layer)
            if not git_is_clean(project_dir):
                git_add(project_dir, ["timeline/", "assets/", ".vit/", ".gitignore"])
                try:
                    git_commit(project_dir, f"vit: auto-save before merging '{target}'")
                except GitError as e:
                    if "nothing to commit" not in str(e):
                        return {"ok": False, "error": str(e)}

            success, output = git_merge(project_dir, target)
            if not success:
                conflicted = git_list_conflicted_files(project_dir)
                auto_resolvable = [
                    f for f in conflicted
                    if f.startswith("timeline/") or f.startswith("assets/")
                ]
                non_resolvable = [f for f in conflicted if f not in auto_resolvable]
                if auto_resolvable and not non_resolvable:
                    try:
                        git_checkout_theirs(project_dir, auto_resolvable)
                        git_add(project_dir, auto_resolvable)
                        git_commit(project_dir, f"vit: merged '{target}' (auto-resolved)")
                        success = True
                    except GitError as e:
                        return {"ok": False, "error": f"Auto-resolve failed: {e}"}

            if success:
                issues = validate_project(project_dir)
                issue_text = format_issues(issues) if issues else ""
                return {"ok": True, "branch": target, "current": current, "issues": issue_text}
            else:
                return {"ok": False, "error": f"Merge conflicts. Use terminal: vit merge {target}"}

        elif action == "push":
            from vit.core import git_current_branch, git_push, GitError
            branch = git_current_branch(project_dir)
            try:
                output = git_push(project_dir, "origin", branch)
                return {"ok": True, "branch": branch, "output": output.strip()}
            except GitError as e:
                return {"ok": False, "error": str(e)}

        elif action == "pull":
            from vit.core import git_current_branch, git_pull, GitError
            branch = git_current_branch(project_dir)
            try:
                output = git_pull(project_dir, "origin", branch)
            except GitError as e:
                return {"ok": False, "error": str(e)}
            return {"ok": True, "branch": branch, "output": output.strip()}

        elif action == "status":
            from vit.core import git_current_branch, git_status, git_log
            branch = git_current_branch(project_dir)
            status = git_status(project_dir)
            log_out = git_log(project_dir, max_count=5)
            return {
                "ok": True,
                "branch": branch,
                "status": status.strip() if status else "Working tree clean",
                "log": log_out or "",
            }

        elif action == "get_changes":
            from vit.differ import get_changes_by_category
            try:
                changes = get_changes_by_category(project_dir, "HEAD")
                return {"ok": True, "changes": changes}
            except Exception:
                return {"ok": True, "changes": {"audio": [], "video": [], "color": []}}

        elif action == "get_commit_history":
            from vit.core import git_log_with_changes, categorize_commit
            limit = request.get("limit", 10)
            commits = git_log_with_changes(project_dir, max_count=limit)
            for commit in commits:
                commit["category"] = categorize_commit(commit.get("files_changed", []))
            return {"ok": True, "commits": commits}

        elif action == "compare_branches":
            from vit.differ import get_branch_diff_by_category
            branch_a = request.get("branch_a", "")
            branch_b = request.get("branch_b", "")
            if not branch_a or not branch_b:
                return {"ok": False, "error": "Both branch_a and branch_b required"}
            changes_a, changes_b = get_branch_diff_by_category(project_dir, branch_a, branch_b)
            return {
                "ok": True,
                "branch_a": branch_a,
                "branch_b": branch_b,
                "changes_a": changes_a,
                "changes_b": changes_b,
            }

        elif action == "get_commit_graph":
            from vit.core import git_log_with_topology
            limit = request.get("limit", 30)
            try:
                data = git_log_with_topology(project_dir, max_count=limit)
                branch_colors = {}
                color_idx = 0
                for branch in data.get("branches", []):
                    if branch in ("main", "master"):
                        branch_colors[branch] = 3  # orange
                    else:
                        branch_colors[branch] = color_idx % 3
                        color_idx += 1
                return {
                    "ok": True,
                    "commits": data.get("commits", []),
                    "branches": data.get("branches", []),
                    "branch_colors": branch_colors,
                    "head": data.get("head", ""),
                }
            except Exception as e:
                return {"ok": False, "error": str(e)}

        elif action == "init":
            from vit.core import git_init
            git_init(project_dir, nle="premiere")
            return {"ok": True}

        elif action == "quit":
            return {"ok": True, "quit": True}

        else:
            return {"ok": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        _log(f"Error handling {action}: {traceback.format_exc()}")
        return {"ok": False, "error": str(e)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Vit Premiere Bridge")
    parser.add_argument("--project-dir", required=True, help="Path to vit project directory")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    _log(f"Bridge started. Project: {project_dir}")

    # Main loop: read JSON from stdin, write responses to stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            _log(f"Bad JSON: {e}")
            response = {"ok": False, "error": f"Invalid JSON: {e}"}
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            continue

        response = handle_request(request, project_dir)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

        if response.get("quit"):
            break

    _log("Bridge exiting.")


if __name__ == "__main__":
    main()
