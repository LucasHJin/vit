"""Tests for serializer — mock Resolve API, verify JSON output."""

import json
import os
import tempfile

import pytest

from giteo.serializer import serialize_timeline
from giteo.json_writer import read_json, read_all_domain_files
from tests.mock_resolve import create_test_timeline


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "timeline"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "assets"), exist_ok=True)
        yield tmpdir


def test_serialize_creates_all_domain_files(project_dir):
    """Serialization should create all 7 domain files."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    expected_files = [
        "timeline/cuts.json",
        "timeline/color.json",
        "timeline/audio.json",
        "timeline/effects.json",
        "timeline/markers.json",
        "timeline/metadata.json",
        "assets/manifest.json",
    ]

    for filepath in expected_files:
        full_path = os.path.join(project_dir, filepath)
        assert os.path.exists(full_path), f"Missing: {filepath}"


def test_cuts_json_structure(project_dir):
    """cuts.json should contain video tracks with items."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    cuts = read_json(os.path.join(project_dir, "timeline", "cuts.json"))

    assert "video_tracks" in cuts
    assert len(cuts["video_tracks"]) == 1

    track = cuts["video_tracks"][0]
    assert track["index"] == 1
    assert len(track["items"]) == 2

    item = track["items"][0]
    assert item["name"] == "Interview_A_001"
    assert item["record_start_frame"] == 0
    assert item["record_end_frame"] == 720
    assert "transform" in item
    assert "id" in item
    assert "media_ref" in item


def test_color_json_has_grades(project_dir):
    """color.json should have a grade entry for each video clip."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    color = read_json(os.path.join(project_dir, "timeline", "color.json"))

    assert "grades" in color
    # Should have entries for both clips
    assert len(color["grades"]) == 2


def test_audio_json_structure(project_dir):
    """audio.json should contain audio tracks with items."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    audio = read_json(os.path.join(project_dir, "timeline", "audio.json"))

    assert "audio_tracks" in audio
    assert len(audio["audio_tracks"]) == 1

    track = audio["audio_tracks"][0]
    assert len(track["items"]) == 1
    assert track["items"][0]["volume"] == -3.0


def test_markers_json(project_dir):
    """markers.json should capture timeline markers."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    markers = read_json(os.path.join(project_dir, "timeline", "markers.json"))

    assert "markers" in markers
    assert len(markers["markers"]) == 2
    assert markers["markers"][0]["frame"] == 240
    assert markers["markers"][0]["name"] == "Fix jump cut"


def test_metadata_json(project_dir):
    """metadata.json should capture project and timeline settings."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    metadata = read_json(os.path.join(project_dir, "timeline", "metadata.json"))

    assert metadata["project_name"] == "My Documentary"
    assert metadata["timeline_name"] == "Main Edit v3"
    assert metadata["frame_rate"] == 24.0
    assert metadata["resolution"]["width"] == 1920


def test_manifest_json(project_dir):
    """assets/manifest.json should register media files."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    manifest = read_json(os.path.join(project_dir, "assets", "manifest.json"))

    assert "assets" in manifest
    # Should have entries for each unique media file
    assert len(manifest["assets"]) >= 1


def test_json_formatting(project_dir):
    """JSON files should be formatted with indent=2, sort_keys=True."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    cuts_path = os.path.join(project_dir, "timeline", "cuts.json")
    with open(cuts_path) as f:
        content = f.read()

    # Should be indented
    assert "  " in content
    # Should end with newline
    assert content.endswith("\n")

    # Should be valid JSON that roundtrips
    parsed = json.loads(content)
    re_serialized = json.dumps(parsed, indent=2, sort_keys=True) + "\n"
    assert content == re_serialized


def test_read_all_domain_files(project_dir):
    """read_all_domain_files should return all domains."""
    _, project, timeline = create_test_timeline()
    serialize_timeline(timeline, project, project_dir)

    files = read_all_domain_files(project_dir)

    assert "cuts" in files
    assert "color" in files
    assert "audio" in files
    assert "markers" in files
    assert "metadata" in files
    assert "manifest" in files
