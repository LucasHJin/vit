"""Deserialize domain-split JSON → DaVinci Resolve timeline.

Reads the JSON files and applies the state back to a Resolve timeline.
"""

import json
import os
from typing import Dict, List

from .json_writer import read_json
from .models import (
    AudioItem,
    AudioTrack,
    ColorGrade,
    Marker,
    TimelineMetadata,
    Transform,
    VideoItem,
    VideoTrack,
)


def _load_cuts(project_dir: str) -> List[VideoTrack]:
    """Load video tracks from cuts.json."""
    data = read_json(os.path.join(project_dir, "timeline", "cuts.json"))
    if not data:
        return []
    return [VideoTrack.from_dict(t) for t in data.get("video_tracks", [])]


def _load_audio(project_dir: str) -> List[AudioTrack]:
    """Load audio tracks from audio.json."""
    data = read_json(os.path.join(project_dir, "timeline", "audio.json"))
    if not data:
        return []
    return [AudioTrack.from_dict(t) for t in data.get("audio_tracks", [])]


def _load_color(project_dir: str) -> Dict[str, ColorGrade]:
    """Load color grades from color.json."""
    data = read_json(os.path.join(project_dir, "timeline", "color.json"))
    if not data:
        return {}
    return {k: ColorGrade.from_dict(v) for k, v in data.get("grades", {}).items()}


def _load_markers(project_dir: str) -> List[Marker]:
    """Load markers from markers.json."""
    data = read_json(os.path.join(project_dir, "timeline", "markers.json"))
    if not data:
        return []
    return [Marker.from_dict(m) for m in data.get("markers", [])]


def _load_metadata(project_dir: str) -> TimelineMetadata:
    """Load metadata from metadata.json."""
    data = read_json(os.path.join(project_dir, "timeline", "metadata.json"))
    if not data:
        return TimelineMetadata()
    return TimelineMetadata.from_dict(data)


def _load_manifest(project_dir: str) -> dict:
    """Load asset manifest."""
    return read_json(os.path.join(project_dir, "assets", "manifest.json"))


def _apply_metadata(timeline, project, metadata: TimelineMetadata) -> None:
    """Apply metadata settings to a Resolve timeline."""
    timeline.SetSetting("timelineFrameRate", str(metadata.frame_rate))
    timeline.SetSetting("timelineResolutionWidth", str(metadata.width))
    timeline.SetSetting("timelineResolutionHeight", str(metadata.height))
    timeline.SetStartTimecode(metadata.start_timecode)


def _find_media_pool_item(media_pool, manifest: dict, media_ref: str):
    """Find or import a media pool item by its asset reference."""
    asset_info = manifest.get("assets", {}).get(media_ref)
    if not asset_info:
        return None

    original_path = asset_info.get("original_path", "")
    if not original_path or not os.path.exists(original_path):
        return None

    root_folder = media_pool.GetRootFolder()
    clips = root_folder.GetClipList()

    if clips:
        for clip in clips:
            clip_path = clip.GetClipProperty("File Path") or ""
            if clip_path == original_path:
                return clip

    imported = media_pool.ImportMedia([original_path])
    if imported and len(imported) > 0:
        return imported[0]

    return None


def _clear_timeline(timeline) -> None:
    """Best-effort removal of existing content before restoring a snapshot.

    Resolve's scripting API has limited deletion support, so we try
    multiple approaches and silently skip any that aren't available.
    """
    # Clear markers first (well-supported API)
    try:
        markers = timeline.GetMarkers()
        if markers:
            for frame in list(markers.keys()):
                timeline.DeleteMarkerAtFrame(frame)
    except (AttributeError, TypeError):
        pass

    # Try to remove clips from each track
    for track_type in ["video", "audio"]:
        try:
            track_count = timeline.GetTrackCount(track_type)
        except (AttributeError, TypeError):
            continue

        for track_idx in range(1, track_count + 1):
            try:
                clips = timeline.GetItemListInTrack(track_type, track_idx)
                if clips:
                    # Resolve 18.5+ may support DeleteClips
                    timeline.DeleteClips(clips, False)
            except (AttributeError, TypeError):
                pass


def _apply_video_tracks(timeline, media_pool, video_tracks: List[VideoTrack], manifest: dict) -> None:
    """Apply video track items to the Resolve timeline."""
    for track in video_tracks:
        while timeline.GetTrackCount("video") < track.index:
            timeline.AddTrack("video")

        for item in track.items:
            pool_item = _find_media_pool_item(media_pool, manifest, item.media_ref)
            if not pool_item:
                print(f"  Warning: Could not find media for '{item.name}' ({item.media_ref})")
                continue

            clip_info = {
                "mediaPoolItem": pool_item,
                "startFrame": item.source_start_frame,
                "endFrame": item.source_end_frame,
                "trackIndex": item.track_index,
                "recordFrame": item.record_start_frame,
            }
            media_pool.AppendToTimeline([clip_info])


def _apply_audio_tracks(timeline, media_pool, audio_tracks: List[AudioTrack], manifest: dict) -> None:
    """Apply audio track items to the Resolve timeline."""
    for track in audio_tracks:
        while timeline.GetTrackCount("audio") < track.index:
            timeline.AddTrack("audio")

        for item in track.items:
            pool_item = _find_media_pool_item(media_pool, manifest, item.media_ref)
            if not pool_item:
                print(f"  Warning: Could not find media for audio '{item.id}' ({item.media_ref})")
                continue

            clip_info = {
                "mediaPoolItem": pool_item,
                "startFrame": item.start_frame,
                "endFrame": item.end_frame,
                "trackIndex": track.index,
            }
            media_pool.AppendToTimeline([clip_info])

            # Apply audio properties after the clip is on the timeline
            clips = timeline.GetItemListInTrack("audio", track.index)
            if clips:
                placed_clip = clips[-1]
                try:
                    placed_clip.SetProperty("Volume", item.volume)
                    placed_clip.SetProperty("Pan", item.pan)
                except (AttributeError, TypeError):
                    pass


def _apply_color(timeline, color_grades: Dict[str, ColorGrade],
                 project_dir: str = "") -> None:
    """Apply color grading data to clips on the timeline.

    Applies DRX grade stills when available (full grade restore),
    and falls back to LUT-only restore from structural info.
    """
    grades_dir = os.path.join(project_dir, "timeline", "grades") if project_dir else ""

    track_count = timeline.GetTrackCount("video")
    for track_idx in range(1, track_count + 1):
        clips = timeline.GetItemListInTrack("video", track_idx)
        if not clips:
            continue

        for i, clip in enumerate(clips):
            item_id = f"item_{track_idx:03d}_{i:03d}"
            grade = color_grades.get(item_id)
            if not grade:
                continue

            # Try DRX grade restore first (complete grade data)
            if grade.drx_file and grades_dir:
                drx_path = os.path.join(grades_dir, grade.drx_file)
                if os.path.exists(drx_path):
                    try:
                        success = timeline.ApplyGradeFromDRX(
                            drx_path, 0, clip)
                        if success:
                            continue
                    except (AttributeError, TypeError):
                        pass

            # Fallback: apply LUTs from structural info
            for node_info in grade.nodes:
                lut = node_info.get("lut", "")
                if lut:
                    try:
                        clip.SetLUT(node_info["index"], lut)
                    except (AttributeError, TypeError):
                        pass


def _apply_markers(timeline, markers: List[Marker]) -> None:
    """Apply markers to the timeline."""
    for marker in markers:
        timeline.AddMarker(
            marker.frame,
            marker.color,
            marker.name,
            marker.note,
            marker.duration,
        )


def deserialize_timeline(timeline, project, project_dir: str) -> None:
    """Deserialize domain-split JSON files back into a Resolve timeline.

    Clears the existing timeline content first, then re-applies the full
    snapshot from the domain-split JSON files.

    Args:
        timeline: Resolve Timeline object
        project: Resolve Project object
        project_dir: Path to the giteo project directory
    """
    metadata = _load_metadata(project_dir)
    video_tracks = _load_cuts(project_dir)
    audio_tracks = _load_audio(project_dir)
    color_grades = _load_color(project_dir)
    markers = _load_markers(project_dir)
    manifest = _load_manifest(project_dir)

    media_pool = project.GetMediaPool()

    # Clear existing timeline content before restoring
    _clear_timeline(timeline)

    # Apply in order: metadata first, then tracks, then overlays
    _apply_metadata(timeline, project, metadata)
    _apply_video_tracks(timeline, media_pool, video_tracks, manifest)
    _apply_audio_tracks(timeline, media_pool, audio_tracks, manifest)
    _apply_color(timeline, color_grades, project_dir)
    _apply_markers(timeline, markers)

    print(f"  Restored timeline '{metadata.timeline_name}' from giteo snapshot")
