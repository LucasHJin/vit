"""Vit: Save Version — Resolve Workspace > Scripts menu item.

Serializes the current timeline and commits a new version.
The `resolve` variable is injected by DaVinci Resolve.
"""
import os
import sys
import traceback

# Bootstrap: find the vit package regardless of symlink resolution
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
    from resolve_plugin.plugin_utils import (
        check_resolve, get_project_dir, ask_string, show_error, show_message, _log,
    )
    from vit.serializer import serialize_timeline
    from vit.core import git_add, git_commit, GitError

    try:
        _resolve = resolve  # noqa: F821 — injected by DaVinci Resolve
    except NameError:
        _resolve = None
    if not check_resolve(_resolve):
        return

    project_dir = get_project_dir()
    if not project_dir:
        show_error("Vit", "No vit project found.\nRun 'vit init <path>' from terminal.")
        return

    project = _resolve.GetProjectManager().GetCurrentProject()
    timeline = project.GetCurrentTimeline()

    if not timeline:
        show_error("Vit", "No timeline is currently active in Resolve.")
        return

    timeline_name = timeline.GetName() or "untitled"
    default_message = f"save '{timeline_name}'"

    message = ask_string(
        "Vit: Save Version",
        "Commit message:",
        initial=default_message,
    )
    if not message:
        message = default_message
        _log(f"Using default message: {message}")

    _log(f"Serializing timeline '{timeline_name}'...")

    serialize_timeline(timeline, project, project_dir, resolve_app=_resolve)
    git_add(project_dir, ["timeline/", "assets/", ".vit/", ".gitignore"])

    try:
        commit_hash = git_commit(project_dir, f"vit: {message}")
        show_message("Vit", f"Saved version: {message}\nCommit: {commit_hash}")
    except GitError as e:
        if "nothing to commit" in str(e):
            show_message("Vit", "Nothing to commit — timeline unchanged.")
        else:
            show_error("Vit", f"Commit failed:\n{e}")


try:
    main()
except Exception:
    print(f"[vit] SCRIPT ERROR:\n{traceback.format_exc()}")
