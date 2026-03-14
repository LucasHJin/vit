"""Tests for deserializer — verify timeline restoration from JSON."""

import os
import tempfile

import pytest

from giteo.serializer import serialize_timeline
from giteo.deserializer import (
    _collect_video_clip_infos,
    _create_fresh_timeline,
    _create_timeline_with_clips,
    _timeline_has_clips,
    _wait_for_current_timeline,
    deserialize_timeline,
)
from tests.mock_resolve import (
    MockMediaPool,
    MockProject,
    MockTimeline,
    MockTimelineItem,
    MockMediaPoolItem,
    create_test_timeline,
)


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "timeline"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "assets"), exist_ok=True)
        yield tmpdir


def test_create_fresh_timeline_uses_temp_name():
    """_create_fresh_timeline should create with a temp name, not rename anything."""
    old_tl = MockTimeline(name="My Edit")
    media_pool = MockMediaPool()
    project = MockProject(name="Test", timeline=old_tl)

    fresh, old_name = _create_fresh_timeline(project, media_pool, old_tl)

    assert fresh.GetName().startswith("giteo_temp_")
    assert fresh is not old_tl
    assert old_tl.GetName() == "My Edit"
    assert old_name == "My Edit"


def test_create_fresh_timeline_sets_current():
    """_create_fresh_timeline should set the new timeline as current."""
    old_tl = MockTimeline(name="My Edit")
    media_pool = MockMediaPool()
    project = MockProject(name="Test", timeline=old_tl)

    fresh, _ = _create_fresh_timeline(project, media_pool, old_tl)
    assert project.GetCurrentTimeline() is fresh


def test_create_fresh_timeline_no_rename_before_population():
    """_create_fresh_timeline must NOT call SetName on old timeline."""
    old_tl = MockTimeline(name="My Edit")
    media_pool = MockMediaPool()
    project = MockProject(name="Test", timeline=old_tl)

    _create_fresh_timeline(project, media_pool, old_tl)
    assert old_tl.GetName() == "My Edit"


def test_create_timeline_with_clips_atomic():
    """_create_timeline_with_clips should use CreateTimelineFromClips."""
    media_pool = MockMediaPool()
    pool_item = MockMediaPoolItem(filepath="/Volumes/Media/test.mov", frames=1000)
    clip_infos = [{"mediaPoolItem": pool_item, "startFrame": 0, "endFrame": 100}]

    new_tl, created_with_clips = _create_timeline_with_clips(media_pool, clip_infos, 12345)

    assert new_tl is not None
    assert created_with_clips is True
    assert new_tl.GetName().startswith("giteo_temp_")
    assert _timeline_has_clips(new_tl)


def test_create_timeline_with_clips_empty():
    """_create_timeline_with_clips with no clips should create empty timeline."""
    media_pool = MockMediaPool()

    new_tl, created_with_clips = _create_timeline_with_clips(media_pool, [], 12345)

    assert new_tl is not None
    assert created_with_clips is False
    assert not _timeline_has_clips(new_tl)


def test_create_timeline_with_clips_fallback():
    """If CreateTimelineFromClips fails, fall back to CreateEmptyTimeline."""
    media_pool = MockMediaPool()
    media_pool.CreateTimelineFromClips = lambda name, infos: None
    pool_item = MockMediaPoolItem(filepath="/Volumes/Media/test.mov", frames=1000)
    clip_infos = [{"mediaPoolItem": pool_item, "startFrame": 0, "endFrame": 100}]

    new_tl, created_with_clips = _create_timeline_with_clips(media_pool, clip_infos, 12345)

    assert new_tl is not None
    assert created_with_clips is False
    assert not _timeline_has_clips(new_tl)


def test_wait_for_current_timeline_succeeds():
    """_wait_for_current_timeline should return True when timeline is current."""
    tl = MockTimeline(name="Test")
    project = MockProject(name="Test", timeline=tl)

    result = _wait_for_current_timeline(project, tl, max_retries=3, delay=0.01)
    assert result is True


def test_wait_for_current_timeline_retries_set():
    """_wait_for_current_timeline should re-issue SetCurrentTimeline on first retry."""
    current_tl = MockTimeline(name="Current")
    other_tl = MockTimeline(name="Other")
    project = MockProject(name="Test", timeline=current_tl)

    result = _wait_for_current_timeline(project, other_tl, max_retries=2, delay=0.01)
    assert result is True
    assert project.GetCurrentTimeline() is other_tl


def test_timeline_has_clips_empty():
    """An empty timeline should report no clips."""
    tl = MockTimeline(name="Empty")
    assert not _timeline_has_clips(tl)


def test_timeline_has_clips_with_video():
    """A timeline with video clips should report having clips."""
    clip = MockTimelineItem(name="Clip", start=0, end=100)
    tl = MockTimeline(name="Has Clips", video_tracks={1: [clip]})
    assert _timeline_has_clips(tl)


def test_timeline_has_clips_with_audio():
    """A timeline with audio clips should report having clips."""
    clip = MockTimelineItem(name="Audio", start=0, end=100)
    tl = MockTimeline(name="Has Audio", audio_tracks={1: [clip]})
    assert _timeline_has_clips(tl)


def test_safety_check_prevents_duplication(project_dir):
    """If both CreateTimelineFromClips and CreateEmptyTimeline fail,
    deserialize should bail out rather than duplicate clips."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    mp = project.GetMediaPool()
    mp.CreateEmptyTimeline = lambda name: None
    mp.CreateTimelineFromClips = lambda name, infos: None

    deserialize_timeline(timeline, project, project_dir)

    # Old timeline should NOT be renamed (we bailed out)
    assert timeline.GetName() == "Main Edit v3"


def test_deserialize_uses_create_timeline_from_clips(project_dir):
    """deserialize_timeline should create the new timeline atomically
    with video clips via CreateTimelineFromClips."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    calls = []
    mp = project.GetMediaPool()
    original_create = mp.CreateTimelineFromClips

    def tracking_create(name, infos):
        calls.append(("CreateTimelineFromClips", name, len(infos)))
        return original_create(name, infos)

    mp.CreateTimelineFromClips = tracking_create

    deserialize_timeline(timeline, project, project_dir)

    assert len(calls) == 1
    assert calls[0][0] == "CreateTimelineFromClips"
    assert calls[0][2] > 0  # had clip infos


def test_deserialize_renames_after_population(project_dir):
    """Renames should happen AFTER clips are populated, not before."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    old_name = timeline.GetName()
    deserialize_timeline(timeline, project, project_dir)

    assert timeline.GetName() != old_name
    assert ".giteo-old" in timeline.GetName()


def test_deserialize_fresh_timeline_is_current(project_dir):
    """After deserialization, the project's current timeline should be the fresh one."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    deserialize_timeline(timeline, project, project_dir)

    current = project.GetCurrentTimeline()
    assert current is not timeline
    assert current.GetName() == "Main Edit v3"
