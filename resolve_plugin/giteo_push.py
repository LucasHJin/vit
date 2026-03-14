"""Giteo: Push — Resolve Workspace > Scripts menu item.

Pushes the current branch to the remote so collaborators can pull it.
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
    from resolve_plugin.plugin_utils import get_project_dir, show_error, show_message, _log
    from giteo.core import git_current_branch, git_push, GitError

    project_dir = get_project_dir()
    if not project_dir:
        show_error("Giteo", "No giteo project found.\nRun 'giteo init <path>' from terminal.")
        return

    branch = git_current_branch(project_dir)
    _log(f"Pushing '{branch}' to origin...")

    try:
        output = git_push(project_dir, "origin", branch)
        show_message("Giteo: Push", f"Pushed '{branch}' to origin.\n\n{output.strip()}")
    except GitError as e:
        error_msg = str(e)
        if "No configured push destination" in error_msg or "does not appear to be a git repository" in error_msg:
            show_error(
                "Giteo: Push",
                f"No remote configured.\n\n"
                f"From terminal, run:\n"
                f"  cd {project_dir}\n"
                f"  git remote add origin <your-github-url>\n"
                f"  giteo push",
            )
        else:
            show_error("Giteo: Push", f"Push failed:\n{error_msg}")


try:
    main()
except Exception:
    print(f"[giteo] SCRIPT ERROR:\n{traceback.format_exc()}")
