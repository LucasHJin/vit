# Vit JSON Schemas

Full schema examples for domain-split timeline files. All files live in the `timeline/` directory of your vit project. Grade sidecar files (`.cube` LUTs) are stored in `timeline/grades/`.

## timeline/cuts.json

```json
{
  "video_tracks": [
    {
      "index": 1,
      "items": [
        {
          "id": "item_001",
          "name": "Interview_A_001",
          "media_ref": "sha256:abcdef...",
          "record_start_frame": 0,
          "record_end_frame": 720,
          "source_start_frame": 100,
          "source_end_frame": 820,
          "track_index": 1,
          "transform": {
            "Pan": 0.0,
            "Tilt": 0.0,
            "ZoomX": 1.0,
            "ZoomY": 1.0,
            "Opacity": 100.0,
            "RotationAngle": 15.0,
            "CropLeft": 50.0,
            "CropRight": 50.0,
            "FlipX": true
          },
          "speed": {
            "speed_percent": 50.0,
            "retime_process": 3,
            "retime_process_name": "optical_flow",
            "motion_estimation": 4,
            "motion_estimation_name": "enhanced_better"
          },
          "composite_mode": 5,
          "composite_mode_name": "screen"
        }
      ]
    }
  ]
}
```

## timeline/color.json

Each entry is keyed by clip `id` (matching `cuts.json`). `lut_file` points to the baked `.cube` grade file in `timeline/grades/`.

```json
{
  "grades": {
    "item_001": {
      "num_nodes": 2,
      "nodes": [
        {
          "node_index": 1,
          "label": "Corrector",
          "tools": ["Primary Offset"],
          "lut_path": null
        },
        {
          "node_index": 2,
          "label": "Sat",
          "tools": ["Primary Corrector"],
          "lut_path": null
        }
      ],
      "version_name": "Version 1",
      "drx_file": null,
      "lut_file": "item_001.cube"
    }
  }
}
```

## timeline/grades/

Binary `.cube` (33-point 3D LUT) files — one per graded clip, named `<item_id>.cube`. These are exported by `ExportLUT()` and parsed on restore to drive `SetCDL()`. Text-based and git-diffable.

```
timeline/grades/
  item_001.cube
  item_003.cube
```

## timeline/audio.json

```json
{
  "audio_tracks": [
    {
      "index": 1,
      "items": [
        {
          "id": "audio_001",
          "media_ref": "sha256:abcdef...",
          "start_frame": 0,
          "end_frame": 720,
          "volume": 0.0,
          "pan": 0.0
        }
      ]
    }
  ]
}
```

## timeline/markers.json

```json
{
  "markers": [
    {
      "frame": 240,
      "color": "Blue",
      "name": "Fix jump cut",
      "note": "Transition feels abrupt",
      "duration": 1
    }
  ]
}
```

## timeline/metadata.json

```json
{
  "project_name": "My Documentary",
  "timeline_name": "Main Edit v3",
  "frame_rate": 24.0,
  "resolution": { "width": 1920, "height": 1080 },
  "start_timecode": "01:00:00:00",
  "track_count": { "video": 3, "audio": 4 }
}
```

## assets/manifest.json

```json
{
  "assets": {
    "sha256:abcdef...": {
      "filename": "Interview_A_001.mov",
      "original_path": "/Volumes/Media/Interview_A_001.mov",
      "duration_frames": 14400,
      "codec": "ProRes 422",
      "resolution": "1920x1080"
    }
  }
}
```
