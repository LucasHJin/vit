"""Dataclasses for timeline entities."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Transform:
    pan: float = 0.0
    tilt: float = 0.0
    zoom_x: float = 1.0
    zoom_y: float = 1.0
    opacity: float = 100.0

    def to_dict(self) -> dict:
        return {
            "Pan": self.pan,
            "Tilt": self.tilt,
            "ZoomX": self.zoom_x,
            "ZoomY": self.zoom_y,
            "Opacity": self.opacity,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Transform":
        return cls(
            pan=d.get("Pan", 0.0),
            tilt=d.get("Tilt", 0.0),
            zoom_x=d.get("ZoomX", 1.0),
            zoom_y=d.get("ZoomY", 1.0),
            opacity=d.get("Opacity", 100.0),
        )


@dataclass
class VideoItem:
    id: str
    name: str
    media_ref: str
    record_start_frame: int
    record_end_frame: int
    source_start_frame: int
    source_end_frame: int
    track_index: int
    transform: Transform = field(default_factory=Transform)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "media_ref": self.media_ref,
            "record_start_frame": self.record_start_frame,
            "record_end_frame": self.record_end_frame,
            "source_start_frame": self.source_start_frame,
            "source_end_frame": self.source_end_frame,
            "track_index": self.track_index,
            "transform": self.transform.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VideoItem":
        return cls(
            id=d["id"],
            name=d["name"],
            media_ref=d["media_ref"],
            record_start_frame=d["record_start_frame"],
            record_end_frame=d["record_end_frame"],
            source_start_frame=d["source_start_frame"],
            source_end_frame=d["source_end_frame"],
            track_index=d["track_index"],
            transform=Transform.from_dict(d.get("transform", {})),
        )


@dataclass
class VideoTrack:
    index: int
    items: List[VideoItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VideoTrack":
        return cls(
            index=d["index"],
            items=[VideoItem.from_dict(i) for i in d.get("items", [])],
        )


@dataclass
class AudioItem:
    id: str
    media_ref: str
    start_frame: int
    end_frame: int
    volume: float = 0.0
    pan: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "media_ref": self.media_ref,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "volume": self.volume,
            "pan": self.pan,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AudioItem":
        return cls(
            id=d["id"],
            media_ref=d["media_ref"],
            start_frame=d["start_frame"],
            end_frame=d["end_frame"],
            volume=d.get("volume", 0.0),
            pan=d.get("pan", 0.0),
        )


@dataclass
class AudioTrack:
    index: int
    items: List[AudioItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AudioTrack":
        return cls(
            index=d["index"],
            items=[AudioItem.from_dict(i) for i in d.get("items", [])],
        )


@dataclass
class ColorGrade:
    """Color grade state for a single clip.

    The Resolve API exposes SetCDL() but not GetCDL(), so we can't read
    actual color wheel values. Instead we capture:
      - Structural info readable via API (node count, labels, LUT paths)
      - Full grade as a DRX still (binary, git-tracked)
    """
    num_nodes: int = 1
    nodes: List[dict] = field(default_factory=list)
    version_name: str = ""
    drx_file: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "num_nodes": self.num_nodes,
            "nodes": self.nodes,
            "version_name": self.version_name,
            "drx_file": self.drx_file,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ColorGrade":
        return cls(
            num_nodes=d.get("num_nodes", 1),
            nodes=d.get("nodes", []),
            version_name=d.get("version_name", ""),
            drx_file=d.get("drx_file"),
        )


@dataclass
class Marker:
    frame: int
    color: str = "Blue"
    name: str = ""
    note: str = ""
    duration: int = 1

    def to_dict(self) -> dict:
        return {
            "frame": self.frame,
            "color": self.color,
            "name": self.name,
            "note": self.note,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Marker":
        return cls(
            frame=d["frame"],
            color=d.get("color", "Blue"),
            name=d.get("name", ""),
            note=d.get("note", ""),
            duration=d.get("duration", 1),
        )


@dataclass
class Asset:
    filename: str
    original_path: str
    duration_frames: int
    codec: str
    resolution: str

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "original_path": self.original_path,
            "duration_frames": self.duration_frames,
            "codec": self.codec,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Asset":
        return cls(
            filename=d["filename"],
            original_path=d["original_path"],
            duration_frames=d["duration_frames"],
            codec=d["codec"],
            resolution=d["resolution"],
        )


@dataclass
class TimelineMetadata:
    project_name: str = ""
    timeline_name: str = ""
    frame_rate: float = 24.0
    width: int = 1920
    height: int = 1080
    start_timecode: str = "01:00:00:00"
    video_track_count: int = 1
    audio_track_count: int = 1

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "timeline_name": self.timeline_name,
            "frame_rate": self.frame_rate,
            "resolution": {"width": self.width, "height": self.height},
            "start_timecode": self.start_timecode,
            "track_count": {
                "video": self.video_track_count,
                "audio": self.audio_track_count,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TimelineMetadata":
        res = d.get("resolution", {})
        tc = d.get("track_count", {})
        return cls(
            project_name=d.get("project_name", ""),
            timeline_name=d.get("timeline_name", ""),
            frame_rate=d.get("frame_rate", 24.0),
            width=res.get("width", 1920),
            height=res.get("height", 1080),
            start_timecode=d.get("start_timecode", "01:00:00:00"),
            video_track_count=tc.get("video", 1),
            audio_track_count=tc.get("audio", 1),
        )


@dataclass
class Timeline:
    """Complete timeline state, split into domain files."""
    metadata: TimelineMetadata = field(default_factory=TimelineMetadata)
    video_tracks: List[VideoTrack] = field(default_factory=list)
    audio_tracks: List[AudioTrack] = field(default_factory=list)
    color_grades: Dict[str, ColorGrade] = field(default_factory=dict)
    effects: dict = field(default_factory=dict)
    markers: List[Marker] = field(default_factory=list)
    assets: Dict[str, Asset] = field(default_factory=dict)
