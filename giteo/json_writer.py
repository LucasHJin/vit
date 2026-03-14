"""Write domain-split JSON files to disk."""

import json
import os
from typing import Dict, List

from .models import (
    Asset,
    AudioTrack,
    ColorGrade,
    Marker,
    Timeline,
    TimelineMetadata,
    VideoTrack,
)


def _write_json(filepath: str, data: dict) -> None:
    """Write JSON with consistent formatting for clean git diffs."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def write_cuts(project_dir: str, video_tracks: List[VideoTrack]) -> None:
    """Write timeline/cuts.json."""
    data = {"video_tracks": [t.to_dict() for t in video_tracks]}
    _write_json(os.path.join(project_dir, "timeline", "cuts.json"), data)


def write_color(project_dir: str, grades: Dict[str, ColorGrade]) -> None:
    """Write timeline/color.json."""
    data = {"grades": {k: v.to_dict() for k, v in grades.items()}}
    _write_json(os.path.join(project_dir, "timeline", "color.json"), data)


def write_audio(project_dir: str, audio_tracks: List[AudioTrack]) -> None:
    """Write timeline/audio.json."""
    data = {"audio_tracks": [t.to_dict() for t in audio_tracks]}
    _write_json(os.path.join(project_dir, "timeline", "audio.json"), data)


def write_effects(project_dir: str, effects: dict) -> None:
    """Write timeline/effects.json."""
    _write_json(os.path.join(project_dir, "timeline", "effects.json"), effects)


def write_markers(project_dir: str, markers: List[Marker]) -> None:
    """Write timeline/markers.json."""
    data = {"markers": [m.to_dict() for m in markers]}
    _write_json(os.path.join(project_dir, "timeline", "markers.json"), data)


def write_metadata(project_dir: str, metadata: TimelineMetadata) -> None:
    """Write timeline/metadata.json."""
    _write_json(os.path.join(project_dir, "timeline", "metadata.json"), metadata.to_dict())


def write_manifest(project_dir: str, assets: Dict[str, Asset]) -> None:
    """Write assets/manifest.json."""
    data = {"assets": {k: v.to_dict() for k, v in assets.items()}}
    _write_json(os.path.join(project_dir, "assets", "manifest.json"), data)


def write_timeline(project_dir: str, timeline: Timeline) -> None:
    """Write all domain-split JSON files for a complete timeline."""
    write_cuts(project_dir, timeline.video_tracks)
    write_color(project_dir, timeline.color_grades)
    write_audio(project_dir, timeline.audio_tracks)
    write_effects(project_dir, timeline.effects)
    write_markers(project_dir, timeline.markers)
    write_metadata(project_dir, timeline.metadata)
    write_manifest(project_dir, timeline.assets)


def read_json(filepath: str) -> dict:
    """Read a JSON file, returning empty dict if not found."""
    if not os.path.exists(filepath):
        return {}
    with open(filepath) as f:
        return json.load(f)


def read_all_domain_files(project_dir: str) -> dict:
    """Read all domain JSON files into a dict keyed by domain name."""
    return {
        "cuts": read_json(os.path.join(project_dir, "timeline", "cuts.json")),
        "color": read_json(os.path.join(project_dir, "timeline", "color.json")),
        "audio": read_json(os.path.join(project_dir, "timeline", "audio.json")),
        "effects": read_json(os.path.join(project_dir, "timeline", "effects.json")),
        "markers": read_json(os.path.join(project_dir, "timeline", "markers.json")),
        "metadata": read_json(os.path.join(project_dir, "timeline", "metadata.json")),
        "manifest": read_json(os.path.join(project_dir, "assets", "manifest.json")),
    }
