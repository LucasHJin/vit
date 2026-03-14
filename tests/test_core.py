"""Tests for core.py — git wrapper operations in a temp directory."""

import json
import os
import tempfile

import pytest

from giteo.core import (
    GitError,
    find_project_root,
    git_add,
    git_branch,
    git_checkout,
    git_commit,
    git_current_branch,
    git_diff,
    git_init,
    git_list_branches,
    git_log,
    git_merge,
    git_merge_base,
    git_revert,
    git_show_file,
    git_status,
    is_git_repo,
)
from giteo.json_writer import _write_json


@pytest.fixture
def project_dir():
    """Create a temp directory and init a giteo project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        git_init(tmpdir)
        # Initial commit
        git_add(tmpdir, [".giteo/", "timeline/", "assets/"])
        git_commit(tmpdir, "initial commit")
        yield tmpdir


def _write_cuts(project_dir, items):
    """Helper to write cuts.json with given items."""
    data = {
        "video_tracks": [
            {"index": 1, "items": items}
        ]
    }
    _write_json(os.path.join(project_dir, "timeline", "cuts.json"), data)


def test_init_creates_structure(project_dir):
    """git_init should create .giteo/, timeline/, assets/."""
    assert os.path.isdir(os.path.join(project_dir, ".giteo"))
    assert os.path.isdir(os.path.join(project_dir, "timeline"))
    assert os.path.isdir(os.path.join(project_dir, "assets"))
    assert os.path.isfile(os.path.join(project_dir, ".giteo", "config.json"))


def test_is_git_repo(project_dir):
    assert is_git_repo(project_dir) is True
    assert is_git_repo("/tmp/nonexistent_dir_xyz") is False


def test_commit_and_log(project_dir):
    """Should be able to commit and see it in log."""
    _write_cuts(project_dir, [{"id": "item_001", "name": "Test Clip"}])
    git_add(project_dir, ["timeline/"])
    git_commit(project_dir, "add test clip")

    log = git_log(project_dir)
    assert "add test clip" in log


def test_branch_and_checkout(project_dir):
    """Should create and switch branches."""
    git_branch(project_dir, "color-grade")
    assert git_current_branch(project_dir) == "color-grade"

    git_checkout(project_dir, "main")
    assert git_current_branch(project_dir) == "main"

    branches = git_list_branches(project_dir)
    assert "main" in branches
    assert "color-grade" in branches


def test_merge_clean(project_dir):
    """Merging branches that edit different files should succeed cleanly."""
    # Create color-grade branch and modify color.json
    git_branch(project_dir, "color-grade")
    _write_json(
        os.path.join(project_dir, "timeline", "color.json"),
        {"grades": {"item_001": {"num_nodes": 2, "nodes": [{"index": 1, "label": "", "lut": ""}, {"index": 2, "label": "LUT", "lut": "Warm.cube"}], "version_name": "", "drx_file": None}}},
    )
    git_add(project_dir, ["timeline/"])
    git_commit(project_dir, "add color grade")

    # Switch to main and modify cuts.json
    git_checkout(project_dir, "main")
    _write_cuts(project_dir, [{"id": "item_001", "name": "Updated Clip"}])
    git_add(project_dir, ["timeline/"])
    git_commit(project_dir, "update clip name")

    # Merge should succeed — different files
    success, output = git_merge(project_dir, "color-grade")
    assert success is True


def test_merge_conflict(project_dir):
    """Merging branches that edit the same file should produce a conflict."""
    # Create experiment branch and modify cuts.json
    git_branch(project_dir, "experiment")
    _write_cuts(project_dir, [{"id": "item_001", "name": "Experiment Clip"}])
    git_add(project_dir, ["timeline/"])
    git_commit(project_dir, "experiment edit")

    # Switch to main and modify cuts.json differently
    git_checkout(project_dir, "main")
    _write_cuts(project_dir, [{"id": "item_001", "name": "Main Clip"}])
    git_add(project_dir, ["timeline/"])
    git_commit(project_dir, "main edit")

    # Merge should fail — same file modified
    success, output = git_merge(project_dir, "experiment")
    assert success is False


def test_git_show_file(project_dir):
    """Should retrieve file content at a specific ref."""
    _write_cuts(project_dir, [{"id": "item_001", "name": "V1"}])
    git_add(project_dir, ["timeline/"])
    git_commit(project_dir, "version 1")

    _write_cuts(project_dir, [{"id": "item_001", "name": "V2"}])
    git_add(project_dir, ["timeline/"])
    git_commit(project_dir, "version 2")

    # HEAD should be V2
    content = git_show_file(project_dir, "HEAD", "timeline/cuts.json")
    assert content is not None
    data = json.loads(content)
    assert data["video_tracks"][0]["items"][0]["name"] == "V2"

    # HEAD~1 should be V1
    content = git_show_file(project_dir, "HEAD~1", "timeline/cuts.json")
    assert content is not None
    data = json.loads(content)
    assert data["video_tracks"][0]["items"][0]["name"] == "V1"


def test_git_status(project_dir):
    """git_status should show modified files."""
    _write_cuts(project_dir, [{"id": "item_001", "name": "New"}])
    status = git_status(project_dir)
    assert "timeline" in status


def test_find_project_root(project_dir):
    """find_project_root should find .giteo directory."""
    # From project dir itself
    found = find_project_root(project_dir)
    assert found == project_dir

    # From a subdirectory
    sub = os.path.join(project_dir, "timeline")
    found = find_project_root(sub)
    assert found == project_dir


def test_revert(project_dir):
    """git_revert should undo the last commit."""
    _write_cuts(project_dir, [{"id": "item_001", "name": "Before"}])
    git_add(project_dir, ["timeline/"])
    git_commit(project_dir, "before revert")

    _write_cuts(project_dir, [{"id": "item_001", "name": "After"}])
    git_add(project_dir, ["timeline/"])
    git_commit(project_dir, "after revert")

    git_revert(project_dir)

    log = git_log(project_dir)
    assert "Revert" in log
