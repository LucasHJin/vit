"""Vit: Show Status — Resolve Workspace > Scripts menu item.

Shows current branch and modified files.
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
    if os.path.isdir(os.path.join(_root, "vit")) and _root not in sys.path:
        sys.path.insert(0, _root)
else:
    _pf = os.path.expanduser("~/.vit/package_path")
    if os.path.exists(_pf):
        with open(_pf) as _f:
            _root = _f.read().strip()
        if _root and os.path.isdir(os.path.join(_root, "vit")) and _root not in sys.path:
            sys.path.insert(0, _root)


def main():
    from resolve_plugin.plugin_utils import get_project_dir, show_error, show_message, _log
    from vit.core import git_current_branch, git_status, git_log

    project_dir = get_project_dir()
    if not project_dir:
        show_error("Vit", "No vit project found.\nRun 'vit init <path>' from terminal.")
        return

    current = git_current_branch(project_dir)
    status = git_status(project_dir)
    log = git_log(project_dir, max_count=5)

    lines = [f"Branch: {current}", ""]
    if status:
        lines += ["Changes:", status]
    else:
        lines.append("Working tree clean.")
    lines += ["", "Recent history:", log]

    msg = "\n".join(lines)
    _log(msg)
    show_message("Vit: Status", msg)


try:
    main()
except Exception:
    print(f"[vit] SCRIPT ERROR:\n{traceback.format_exc()}")
