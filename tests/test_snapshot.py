"""Tests for headless audit snapshots (vit/snapshot.py) and what they rely on."""

import builtins
import json
import os
import subprocess

import pytest

from tests.mock_resolve import (
    MockMediaPoolItem,
    MockTimeline,
    MockTimelineItem,
    create_test_timeline,
)
from vit import serializer
from vit.core import git_init
from vit.differ import diff_cuts
from vit.serializer import _compute_media_hash, _media_ref, serialize_timeline
from vit.snapshot import (
    SnapshotError,
    diff_timeline,
    find_timeline,
    read_index,
    resolve_key,
    snapshot,
)


@pytest.fixture
def project_dir(tmp_path):
    d = str(tmp_path / "proj")
    git_init(d)
    return d


def _git(project_dir, *args):
    return subprocess.run(["git"] + list(args), cwd=project_dir,
                          capture_output=True, text=True).stdout


def _cut_ids(root):
    with open(os.path.join(root, "timeline", "cuts.json")) as f:
        cuts = json.load(f)
    return [i["id"] for t in cuts["video_tracks"] for i in t["items"]]


class PageSpy:
    """Stands in for the Resolve app; records page switches."""

    def __init__(self):
        self.opened = []

    def GetCurrentPage(self):
        return "edit"

    def OpenPage(self, page):
        self.opened.append(page)


# --- stable IDs ---------------------------------------------------------

def test_stable_ids_survive_an_insert(tmp_path):
    _, project, timeline = create_test_timeline()
    root = str(tmp_path)
    serialize_timeline(timeline, project, root, stable_ids=True, media_refs="path")
    before = _cut_ids(root)

    new_clip = MockTimelineItem(name="Opening", start=0, end=48,
                                media_pool_item=MockMediaPoolItem("/Volumes/Media/Open.mov"))
    timeline._video_tracks[1].insert(0, new_clip)
    serialize_timeline(timeline, project, root, stable_ids=True, media_refs="path")
    after = _cut_ids(root)

    assert after[1:] == before
    assert after[0] not in before


def test_positional_ids_are_still_the_default(tmp_path):
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, str(tmp_path))
    assert _cut_ids(str(tmp_path)) == ["item_001_000", "item_001_001"]


def test_stable_ids_fall_back_when_api_has_none(tmp_path):
    _, project, timeline = create_test_timeline()
    for clip in timeline._video_tracks[1]:
        clip.GetUniqueId = lambda: None
    serialize_timeline(timeline, project, str(tmp_path), stable_ids=True)
    assert _cut_ids(str(tmp_path)) == ["item_001_000", "item_001_001"]


def test_colour_grades_use_the_same_ids_as_cuts(tmp_path):
    _, project, timeline = create_test_timeline()
    root = str(tmp_path)
    serialize_timeline(timeline, project, root, stable_ids=True, capture_grades=False)
    with open(os.path.join(root, "timeline", "color.json")) as f:
        grade_ids = sorted(json.load(f)["grades"])
    assert grade_ids == sorted(_cut_ids(root))


# --- media refs ---------------------------------------------------------

def test_path_refs_never_open_the_file(tmp_path, monkeypatch):
    media = tmp_path / "clip.mov"
    media.write_bytes(b"x" * 1024)

    def no_open(*a, **k):
        raise AssertionError("media file was opened")

    monkeypatch.setattr(builtins, "open", no_open)
    ref = _media_ref(str(media), "path")
    assert ref.startswith("path:")
    assert ref == _media_ref(str(media), "path")


def test_content_hash_reads_each_file_once(tmp_path, monkeypatch):
    media = tmp_path / "clip.mov"
    media.write_bytes(b"x" * 4096)
    serializer._HASH_MEMO.clear()
    first = _compute_media_hash(str(media))

    def no_open(*a, **k):
        raise AssertionError("media file was hashed twice")

    monkeypatch.setattr(builtins, "open", no_open)
    assert _compute_media_hash(str(media)) == first


def test_content_hash_notices_a_changed_file(tmp_path):
    media = tmp_path / "clip.mov"
    media.write_bytes(b"a" * 100)
    first = _compute_media_hash(str(media))
    media.write_bytes(b"b" * 200)
    assert _compute_media_hash(str(media)) != first


# --- colour is opt-in ---------------------------------------------------

def test_metadata_only_colour_leaves_the_page_alone(tmp_path):
    _, project, timeline = create_test_timeline()
    spy = PageSpy()
    serialize_timeline(timeline, project, str(tmp_path), resolve_app=spy,
                       capture_grades=False)
    assert spy.opened == []
    assert not os.path.exists(os.path.join(str(tmp_path), "timeline", "grades"))


def test_skipping_grades_keeps_earlier_grade_files(tmp_path):
    _, project, timeline = create_test_timeline()
    root = str(tmp_path)
    serialize_timeline(timeline, project, root, stable_ids=True, capture_grades=False)
    item_id = _cut_ids(root)[0]

    grades_dir = os.path.join(root, "timeline", "grades")
    os.makedirs(grades_dir)
    open(os.path.join(grades_dir, f"{item_id}.cube"), "w").close()
    color_path = os.path.join(root, "timeline", "color.json")
    with open(color_path) as f:
        color = json.load(f)
    color["grades"][item_id]["lut_file"] = f"{item_id}.cube"
    with open(color_path, "w") as f:
        json.dump(color, f)

    serialize_timeline(timeline, project, root, stable_ids=True, capture_grades=False)
    with open(color_path) as f:
        assert json.load(f)["grades"][item_id]["lut_file"] == f"{item_id}.cube"


# --- differ -------------------------------------------------------------

def _one_clip(**over):
    item = {"id": "a", "name": "Clip.mov", "track_index": 1,
            "record_start_frame": 0, "record_end_frame": 100,
            "source_start_frame": 50, "source_end_frame": 150}
    item.update(over)
    return {"video_tracks": [{"index": 1, "items": [item]}]}


def test_diff_reports_a_slip():
    lines = diff_cuts(_one_clip(), _one_clip(source_start_frame=62, source_end_frame=162))
    assert len(lines) == 1
    assert "Slipped" in lines[0] and "+12f" in lines[0]


def test_diff_reports_a_move_not_two_trims():
    lines = diff_cuts(_one_clip(), _one_clip(record_start_frame=48, record_end_frame=148))
    assert len(lines) == 1
    assert "Moved" in lines[0] and "+48f" in lines[0]


def test_diff_reports_a_rename():
    lines = diff_cuts(_one_clip(), _one_clip(name="Interview_A_001"))
    assert len(lines) == 1 and "Renamed" in lines[0]


def test_diff_after_insert_is_one_add_plus_moves(tmp_path):
    _, project, timeline = create_test_timeline()
    root = str(tmp_path)
    serialize_timeline(timeline, project, root, stable_ids=True, media_refs="path")
    with open(os.path.join(root, "timeline", "cuts.json")) as f:
        old = json.load(f)

    for clip in timeline._video_tracks[1]:
        clip._start += 48
        clip._end += 48
    timeline._video_tracks[1].insert(0, MockTimelineItem(
        name="Opening", start=0, end=48,
        media_pool_item=MockMediaPoolItem("/Volumes/Media/Open.mov")))
    serialize_timeline(timeline, project, root, stable_ids=True, media_refs="path")
    with open(os.path.join(root, "timeline", "cuts.json")) as f:
        new = json.load(f)

    lines = diff_cuts(old, new)
    assert sum("+ Added" in l for l in lines) == 1
    assert sum("Moved" in l for l in lines) == 2
    assert not any("Removed" in l or "Trimmed" in l for l in lines)


# --- snapshot -----------------------------------------------------------

def test_snapshot_commits_and_reports(project_dir):
    _, project, timeline = create_test_timeline()
    result = snapshot(project_dir, timeline, project, "built rough cut v1")

    assert result["commit"]
    assert result["changed"] is True
    assert "cuts" in result["domains_changed"]
    assert result["timeline"] == "Main Edit v3"
    assert "built rough cut v1" in _git(project_dir, "log", "--oneline")
    assert os.path.exists(os.path.join(
        project_dir, "timelines", result["key"], "timeline", "cuts.json"))
    assert read_index(project_dir)[result["key"]]["name"] == "Main Edit v3"


def test_unchanged_timeline_makes_no_commit(project_dir):
    _, project, timeline = create_test_timeline()
    snapshot(project_dir, timeline, project, "first")
    result = snapshot(project_dir, timeline, project, "second")
    assert result["commit"] is None
    assert result["changed"] is False
    assert result["domains_changed"] == []
    assert "second" not in _git(project_dir, "log", "--oneline")


def test_snapshot_names_only_the_domains_that_changed(project_dir):
    _, project, timeline = create_test_timeline()
    snapshot(project_dir, timeline, project, "before")
    timeline._audio_tracks[1][0].SetProperty("Volume", -9.0)
    result = snapshot(project_dir, timeline, project, "lower interview level")
    assert result["domains_changed"] == ["audio"]
    assert "volume" in result["diff"]


def test_each_timeline_gets_its_own_folder(project_dir):
    _, project, v1 = create_test_timeline()
    v2 = MockTimeline(name="Main Edit v4", video_tracks={1: [
        MockTimelineItem(name="Only", start=0, end=24,
                         media_pool_item=MockMediaPoolItem("/Volumes/Media/Only.mov"))]})
    r1 = snapshot(project_dir, v1, project, "v3")
    r2 = snapshot(project_dir, v2, project, "v4")

    assert r1["key"] != r2["key"]
    assert len(_cut_ids(os.path.join(project_dir, "timelines", r1["key"]))) == 2
    assert len(_cut_ids(os.path.join(project_dir, "timelines", r2["key"]))) == 1
    assert resolve_key(project_dir, "Main Edit v4") == r2["key"]

    # v3 is untouched by v4's snapshot
    _, changed = diff_timeline(project_dir, r1["key"], "HEAD")
    assert changed == []


def test_renaming_a_timeline_keeps_its_history(project_dir):
    _, project, timeline = create_test_timeline()
    r1 = snapshot(project_dir, timeline, project, "first")
    timeline.SetName("Main Edit FINAL")
    r2 = snapshot(project_dir, timeline, project, "renamed")
    assert r2["key"] == r1["key"]
    assert r2["domains_changed"] == ["metadata"]
    assert read_index(project_dir)[r1["key"]]["name"] == "Main Edit FINAL"


def test_journal_is_committed_with_the_snapshot(project_dir):
    _, project, timeline = create_test_timeline()
    call = {"tool": "run_script", "script": "tl.AddMarker(...)"}
    result = snapshot(project_dir, timeline, project, "add markers", journal=call)

    assert result["journal"].startswith("journal/")
    with open(os.path.join(project_dir, result["journal"])) as f:
        entry = json.load(f)
    assert entry["entry"] == call
    assert entry["timeline_key"] == result["key"]
    assert result["journal"] in _git(project_dir, "show", "--name-only", "HEAD")


def test_journal_alone_is_still_recorded(project_dir):
    _, project, timeline = create_test_timeline()
    snapshot(project_dir, timeline, project, "first")
    result = snapshot(project_dir, timeline, project, "script ran, changed nothing",
                      journal={"tool": "run_script"})
    assert result["changed"] is False
    assert result["commit"]


def test_snapshot_leaves_other_staged_work_alone(project_dir):
    _, project, timeline = create_test_timeline()
    with open(os.path.join(project_dir, "notes.txt"), "w") as f:
        f.write("mine")
    _git(project_dir, "add", "notes.txt")
    snapshot(project_dir, timeline, project, "first")
    assert "notes.txt" not in _git(project_dir, "show", "--name-only", "HEAD")
    assert "notes.txt" in _git(project_dir, "diff", "--cached", "--name-only")


def test_snapshot_needs_a_message(project_dir):
    _, project, timeline = create_test_timeline()
    with pytest.raises(SnapshotError):
        snapshot(project_dir, timeline, project, "  ")


def test_colour_capture_refuses_a_timeline_that_is_not_open(project_dir):
    _, project, _ = create_test_timeline()
    other = MockTimeline(name="Other")
    with pytest.raises(SnapshotError):
        snapshot(project_dir, other, project, "x", color=True)


def test_find_timeline_by_name_does_not_switch(project_dir):
    _, project, current = create_test_timeline()
    other = project.GetMediaPool().CreateEmptyTimeline("Selects")
    assert find_timeline(project) is current
    assert find_timeline(project, "Selects") is other
    assert project.GetCurrentTimeline() is current
    with pytest.raises(SnapshotError):
        find_timeline(project, "Nope")
