"""Audit snapshots: a record of what changed on a timeline, taken headlessly.

This is a second way to use vit, alongside the branch/merge workflow:

  - It runs from outside Resolve (CLI, agent, hook), not from the panel.
  - Every timeline gets its own folder, so a project with "rough cut v1",
    "v2" and "v3" keeps a separate history for each instead of overwriting
    one shared `timeline/` folder.
  - Clips are identified by Resolve's unique item ID, so the diff after an
    insert says "one clip added", not "every later clip changed".
  - Source files are referenced by path, not by hashing their contents.
  - Colour is recorded as metadata only unless asked, so a snapshot doesn't
    switch pages or move the playhead under the editor.
  - An optional journal entry (what was asked for: the tool call, the script)
    is committed together with the snapshot (what resulted).

Layout inside the vit project:

    timelines/
      index.json                 # key -> timeline name, project
      <key>/                     # one per timeline; same layout as a vit project
        timeline/cuts.json ...
        assets/manifest.json
    journal/
      20261118T172501Z-tighten-trims.json

Snapshots only ever read from Resolve. Nothing here restores a timeline; for
rollback, duplicate the timeline in Resolve before changing it.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .core import GitError, _run, git_config_get, git_show_file
from .differ import format_diff
from .json_writer import _write_json, read_json
from .serializer import serialize_timeline
from .validator import validate_project

TIMELINES_DIR = "timelines"
JOURNAL_DIR = "journal"
INDEX_FILE = "index.json"

# Domain files inside <key>/, relative to the timeline's own root
DOMAIN_FILES = {
    "cuts": "timeline/cuts.json",
    "color": "timeline/color.json",
    "audio": "timeline/audio.json",
    "effects": "timeline/effects.json",
    "markers": "timeline/markers.json",
    "metadata": "timeline/metadata.json",
}


class SnapshotError(Exception):
    """Raised when a snapshot can't be taken."""
    pass


def _slug(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-").lower()
    return slug[:max_len].strip("-") or "untitled"


def timeline_key(timeline) -> str:
    """Folder name for a timeline.

    Resolve's unique ID where available, so renaming a timeline keeps its
    history. Otherwise a slug of the name.
    """
    try:
        uid = timeline.GetUniqueId()
    except (AttributeError, TypeError):
        uid = None
    if uid:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(uid))
    return _slug(timeline.GetName() or "")


def timeline_root(project_dir: str, key: str) -> str:
    return os.path.join(project_dir, TIMELINES_DIR, key)


def find_timeline(project, name: Optional[str] = None):
    """Return the current timeline, or the one called `name`.

    Never changes which timeline is current.
    """
    if not name:
        timeline = project.GetCurrentTimeline()
        if not timeline:
            raise SnapshotError("No timeline is open in Resolve.")
        return timeline

    matches = []
    names = []
    try:
        count = int(project.GetTimelineCount() or 0)
    except (AttributeError, TypeError):
        count = 0
    for idx in range(1, count + 1):
        tl = project.GetTimelineByIndex(idx)
        if not tl:
            continue
        tl_name = tl.GetName() or ""
        names.append(tl_name)
        if tl_name == name:
            matches.append(tl)
    if not matches:
        listing = ", ".join(f"'{n}'" for n in names) or "none"
        raise SnapshotError(f"No timeline called '{name}'. Timelines: {listing}.")
    if len(matches) > 1:
        raise SnapshotError(
            f"{len(matches)} timelines are called '{name}'. Open the one you "
            "mean and snapshot without --timeline."
        )
    return matches[0]


def read_index(project_dir: str) -> dict:
    return read_json(os.path.join(project_dir, TIMELINES_DIR, INDEX_FILE))


def _update_index(project_dir: str, key: str, timeline, project) -> None:
    index = read_index(project_dir)
    entry = {
        "name": timeline.GetName() or "",
        "project": project.GetName() or "",
    }
    if index.get(key) != entry:
        index[key] = entry
        _write_json(os.path.join(project_dir, TIMELINES_DIR, INDEX_FILE), index)


def resolve_key(project_dir: str, name_or_key: str) -> str:
    """Turn a timeline name or key into a key that has snapshots."""
    index = read_index(project_dir)
    if name_or_key in index:
        return name_or_key
    keys = [k for k, v in index.items() if v.get("name") == name_or_key]
    if len(keys) == 1:
        return keys[0]
    if len(keys) > 1:
        raise SnapshotError(
            f"{len(keys)} snapshotted timelines are called '{name_or_key}'. "
            f"Use a key instead: {', '.join(keys)}."
        )
    known = ", ".join(f"'{v.get('name')}'" for v in index.values()) or "none"
    raise SnapshotError(f"No snapshots for '{name_or_key}'. Snapshotted: {known}.")


def load_domains(project_dir: str, key: str, ref: Optional[str] = None) -> Dict[str, dict]:
    """Load a timeline's domain files from disk, or from a git ref."""
    files = {}
    for domain, rel in DOMAIN_FILES.items():
        if ref is None:
            files[domain] = read_json(os.path.join(timeline_root(project_dir, key), rel))
        else:
            # Always forward slashes: this is a git path, not an OS path
            content = git_show_file(project_dir, ref, f"{TIMELINES_DIR}/{key}/{rel}")
            files[domain] = json.loads(content) if content else {}
    return files


def diff_timeline(project_dir: str, key: str, ref: str = "HEAD") -> Tuple[str, List[str]]:
    """Diff a timeline's files on disk against a git ref.

    Returns (human-readable diff, names of the domains that changed).
    """
    old_files = load_domains(project_dir, key, ref)
    new_files = load_domains(project_dir, key)
    changed = [d for d in DOMAIN_FILES if old_files.get(d, {}) != new_files.get(d, {})]
    name = new_files.get("metadata", {}).get("timeline_name", "")
    return format_diff(old_files, new_files, timeline_name=name), changed


def write_journal(project_dir: str, message: str, timeline_name: str, key: str,
                  entry) -> str:
    """Write one journal entry. Returns its path relative to the project."""
    now = datetime.now(timezone.utc)
    journal_dir = os.path.join(project_dir, JOURNAL_DIR)
    base = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{_slug(message, 40)}"
    rel = f"{JOURNAL_DIR}/{base}.json"
    n = 2
    while os.path.exists(os.path.join(project_dir, rel)):
        rel = f"{JOURNAL_DIR}/{base}-{n}.json"
        n += 1
    os.makedirs(journal_dir, exist_ok=True)
    _write_json(os.path.join(project_dir, rel), {
        "time": now.isoformat(timespec="seconds"),
        "message": message,
        "timeline": timeline_name,
        "timeline_key": key,
        "entry": entry,
    })
    return rel


def _commit(project_dir: str, message: str, paths: List[str]) -> Optional[str]:
    """Stage and commit only `paths`. Returns the short hash, or None if unchanged."""
    _run(["add", "--"] + paths, cwd=project_dir)
    staged = _run(["diff", "--cached", "--quiet", "--"] + paths, cwd=project_dir, check=False)
    if staged.returncode == 0:
        return None

    args = []
    # A headless caller can't be prompted for an identity
    if not git_config_get(project_dir, "user.name"):
        args += ["-c", "user.name=vit snapshot"]
    if not git_config_get(project_dir, "user.email"):
        args += ["-c", "user.email=vit-snapshot@localhost"]
    _run(args + ["commit", "-m", message, "--"] + paths, cwd=project_dir)
    return _run(["rev-parse", "--short", "HEAD"], cwd=project_dir).stdout.strip()


def snapshot(project_dir: str, timeline, project, message: str,
             resolve_app=None, color: bool = False, journal=None) -> dict:
    """Record a timeline's current state and commit it.

    Args:
        project_dir: The vit project (a git repo with .vit/).
        timeline, project: Resolve objects.
        message: Commit message. Say what was done and why.
        resolve_app: The Resolve app object; only needed with color=True.
        color: Also export a LUT (and on Studio a DRX) per clip. Switches
            Resolve to the Color page and moves the playhead while it runs.
        journal: Any JSON-serialisable record of what was asked for (a tool
            call's arguments, a script's text), committed with the snapshot.

    Returns a dict: timeline, key, commit (None if nothing was committed),
    changed (did the timeline itself change), domains_changed, diff, issues
    (from the validator), journal (path of the entry, if one was given).
    """
    if not message or not message.strip():
        raise SnapshotError("A snapshot needs a message.")

    if color:
        current = project.GetCurrentTimeline()
        if current is None or timeline_key(current) != timeline_key(timeline):
            raise SnapshotError(
                "Colour capture only works on the timeline that is open in "
                "Resolve. Open it, or snapshot without colour."
            )

    key = timeline_key(timeline)
    root = timeline_root(project_dir, key)
    os.makedirs(root, exist_ok=True)

    serialize_timeline(
        timeline, project, root,
        resolve_app=resolve_app if color else None,
        stable_ids=True,
        media_refs="path",
        capture_grades=color,
    )
    _update_index(project_dir, key, timeline, project)

    try:
        diff_text, domains_changed = diff_timeline(project_dir, key, "HEAD")
    except (GitError, ValueError):
        diff_text, domains_changed = "", []

    name = timeline.GetName() or ""
    paths = [f"{TIMELINES_DIR}/{key}", f"{TIMELINES_DIR}/{INDEX_FILE}"]
    journal_rel = None
    if journal is not None:
        journal_rel = write_journal(project_dir, message, name, key, journal)
        paths.append(journal_rel)

    commit = _commit(project_dir, message.strip(), paths)

    return {
        "timeline": name,
        "key": key,
        "commit": commit,
        "changed": bool(domains_changed),
        "domains_changed": domains_changed,
        "diff": diff_text,
        "issues": [str(i) for i in validate_project(root)],
        "journal": journal_rel,
    }
