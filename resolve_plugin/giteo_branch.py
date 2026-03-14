"""Giteo: New Branch — Resolve Workspace > Scripts menu item.

Creates a new branch and switches to it.
"""
import os
import sys
import traceback

try:
    _real = os.path.realpath(__file__)
except NameError:
    _real = None
if _real:
    _root = os.path.dirname(os.path.dirname(_real))
    if os.path.isdir(os.path.join(_root, "giteo")) and _root not in sys.path:
        sys.path.insert(0, _root)
else:
    _pf = os.path.expanduser("~/.giteo/package_path")
    if os.path.exists(_pf):
        with open(_pf) as _f:
            _root = _f.read().strip()
        if _root and os.path.isdir(os.path.join(_root, "giteo")) and _root not in sys.path:
            sys.path.insert(0, _root)


def main():
    from resolve_plugin.plugin_utils import (
        get_project_dir, ask_string, show_error, show_message, _log,
    )
    from giteo.core import git_branch, git_current_branch, git_list_branches

    project_dir = get_project_dir()
    if not project_dir:
        show_error("Giteo", "No giteo project found.\nRun 'giteo init <path>' from terminal.")
        return

    current = git_current_branch(project_dir)
    branches = git_list_branches(project_dir)
    _log(f"Current branch: {current}")
    _log(f"All branches: {', '.join(branches)}")

    branch_name = ask_string(
        "Giteo: New Branch",
        f"Current branch: {current}\nAll branches: {', '.join(branches)}\n\nNew branch name:",
    )
    if not branch_name:
        _log("No branch name provided — cancelled.")
        return

    branch_name = branch_name.strip()
    if not branch_name:
        return

    try:
        git_branch(project_dir, branch_name)
        show_message("Giteo", f"Created and switched to branch '{branch_name}'")
    except Exception as e:
        show_error("Giteo", f"Failed to create branch: {e}")


try:
    main()
except Exception:
    print(f"[giteo] SCRIPT ERROR:\n{traceback.format_exc()}")
