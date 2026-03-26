/**
 * serializer.jsx — Serialize Premiere Pro timeline to vit JSON objects.
 *
 * Each serialize* function returns a JSON string that the JS panel parses.
 * All output must match the structure defined in vit/models.py:to_dict().
 *
 * Depends on: host_utils.jsx (loaded via manifest ScriptPath).
 */

// Load host_utils if not already loaded
if (typeof TICKS_PER_SECOND === "undefined") {
    var scriptDir = (new File($.fileName)).parent.fsName;
    $.evalFile(scriptDir + "/host_utils.jsx");
}

// --------------------------------------------------------------------------
// Premiere -> Resolve composite mode mapping
// Premiere blend modes are string-based; Resolve uses integer IDs.
// --------------------------------------------------------------------------
var PREMIERE_BLEND_TO_VIT = {
    "Normal": 0,
    "Add": 1,
    "Subtract": 2,
    "Difference": 3,
    "Multiply": 4,
    "Screen": 5,
    "Overlay": 6,
    "Hard Light": 7,
    "Soft Light": 8,
    "Darken": 9,
    "Lighten": 10,
    "Color Dodge": 11,
    "Color Burn": 12,
    "Exclusion": 13,
    "Hue": 14,
    "Saturation": 15,
    "Color": 16,
    "Luminosity": 30,
    "Divide": 18,
    "Linear Dodge (Add)": 19,
    "Linear Burn": 20,
    "Linear Light": 21,
    "Vivid Light": 22,
    "Pin Light": 23,
    "Hard Mix": 24,
    "Lighter Color": 25,
    "Darker Color": 26
};

// Premiere marker color index -> vit color name
var MARKER_COLOR_MAP = {
    0: "Green",
    1: "Red",
    2: "Purple",
    3: "Orange",
    4: "Yellow",
    5: "White",
    6: "Blue",
    7: "Cyan"
};


/**
 * Serialize timeline metadata only.
 * Returns JSON string matching TimelineMetadata.to_dict().
 */
function serializeMetadata() {
    var seq = app.project.activeSequence;
    if (!seq) return '{"error": "No active sequence"}';

    var fps = getFps(seq);
    var w = parseInt(seq.frameSizeHorizontal, 10) || 1920;
    var h = parseInt(seq.frameSizeVertical, 10) || 1080;
    var startTC = getStartTimecode(seq);
    var videoTrackCount = seq.videoTracks.numTracks;
    var audioTrackCount = seq.audioTracks.numTracks;
    var projectName = app.project.name || "";
    var timelineName = seq.name || "";

    // Remove file extension from project name
    projectName = projectName.replace(/\.prproj$/i, "");

    return JSON.stringify({
        "project_name": projectName,
        "timeline_name": timelineName,
        "frame_rate": Math.round(fps * 1000) / 1000,
        "resolution": {"width": w, "height": h},
        "start_timecode": startTC,
        "track_count": {
            "video": videoTrackCount,
            "audio": audioTrackCount
        }
    });
}


/**
 * Read transform properties from a video clip's Motion component.
 * Returns an object matching Transform.to_dict().
 */
function readClipTransform(clip, seqWidth, seqHeight) {
    var t = {
        "Pan": 0.0,
        "Tilt": 0.0,
        "ZoomX": 1.0,
        "ZoomY": 1.0,
        "Opacity": 100.0
    };

    // Motion is always components[0] for video clips
    var motion = findComponent(clip, "Motion");
    if (motion) {
        var pos = getComponentPropertyValue(motion, "Position");
        if (pos !== undefined && pos.length >= 2) {
            // Premiere Position is normalized 0-1 relative to sequence size
            // Vit Pan/Tilt: offset from center in pixels
            t["Pan"] = Math.round(((pos[0] * seqWidth) - (seqWidth / 2)) * 100) / 100;
            t["Tilt"] = Math.round(((pos[1] * seqHeight) - (seqHeight / 2)) * 100) / 100;
        }

        var scale = getComponentPropertyValue(motion, "Scale");
        if (scale !== undefined) {
            // Premiere Scale is 0-100+ percentage, Vit ZoomX is multiplier
            var scaleVal = (typeof scale === "number") ? scale : scale[0];
            t["ZoomX"] = Math.round((scaleVal / 100) * 10000) / 10000;
            t["ZoomY"] = t["ZoomX"];

            // Negative scale = flip
            if (scaleVal < 0) {
                t["FlipX"] = true;
                t["ZoomX"] = Math.abs(t["ZoomX"]);
            }
        }

        // Check for non-uniform scale
        var scaleHeight = getComponentPropertyValue(motion, "Scale Height");
        if (scaleHeight !== undefined) {
            t["ZoomY"] = Math.round((scaleHeight / 100) * 10000) / 10000;
        }

        var rotation = getComponentPropertyValue(motion, "Rotation");
        if (rotation !== undefined && rotation !== 0) {
            t["RotationAngle"] = Math.round(rotation * 100) / 100;
        }

        var anchor = getComponentPropertyValue(motion, "Anchor Point");
        if (anchor !== undefined && anchor.length >= 2) {
            var ax = Math.round(((anchor[0] * seqWidth) - (seqWidth / 2)) * 100) / 100;
            var ay = Math.round(((anchor[1] * seqHeight) - (seqHeight / 2)) * 100) / 100;
            if (ax !== 0) t["AnchorPointX"] = ax;
            if (ay !== 0) t["AnchorPointY"] = ay;
        }
    }

    // Opacity is its own component
    var opacityComp = findComponent(clip, "Opacity");
    if (opacityComp) {
        var opVal = getComponentPropertyValue(opacityComp, "Opacity");
        if (opVal !== undefined) {
            t["Opacity"] = Math.round(opVal * 100) / 100;
        }

        // Blend mode
        var blendMode = getComponentPropertyValue(opacityComp, "Blend Mode");
        if (blendMode !== undefined) {
            // blendMode is typically an index in Premiere
            // We'll store it in the VideoItem, not in transform
        }
    }

    // Crop effect (only present if user has applied it)
    var cropEffect = findComponent(clip, "Crop");
    if (cropEffect) {
        var cl = getComponentPropertyValue(cropEffect, "Left");
        var cr = getComponentPropertyValue(cropEffect, "Right");
        var ct = getComponentPropertyValue(cropEffect, "Top");
        var cb = getComponentPropertyValue(cropEffect, "Bottom");
        if (cl !== undefined && cl !== 0) t["CropLeft"] = Math.round(cl * 100) / 100;
        if (cr !== undefined && cr !== 0) t["CropRight"] = Math.round(cr * 100) / 100;
        if (ct !== undefined && ct !== 0) t["CropTop"] = Math.round(ct * 100) / 100;
        if (cb !== undefined && cb !== 0) t["CropBottom"] = Math.round(cb * 100) / 100;
    }

    return t;
}


/**
 * Read the blend mode from a clip's Opacity component.
 * Returns the vit composite_mode integer.
 */
function readBlendMode(clip) {
    var opacityComp = findComponent(clip, "Opacity");
    if (!opacityComp) return 0;
    var blendMode = getComponentPropertyValue(opacityComp, "Blend Mode");
    if (blendMode === undefined || blendMode === null) return 0;
    // In Premiere, Blend Mode property returns an integer index
    // 1=Normal, 2=Dissolve, etc. We map the common ones
    // Premiere blend mode indices (varies by version, but generally):
    var premiereBlendToVit = {
        1: 0,    // Normal
        3: 9,    // Darken
        4: 4,    // Multiply
        5: 12,   // Color Burn
        6: 20,   // Linear Burn
        7: 26,   // Darker Color
        8: 10,   // Lighten
        9: 5,    // Screen
        10: 11,  // Color Dodge
        11: 19,  // Linear Dodge (Add)
        12: 25,  // Lighter Color
        13: 6,   // Overlay
        14: 8,   // Soft Light
        15: 7,   // Hard Light
        16: 22,  // Vivid Light
        17: 21,  // Linear Light
        18: 23,  // Pin Light
        19: 24,  // Hard Mix
        20: 3,   // Difference
        21: 13,  // Exclusion
        22: 2,   // Subtract
        23: 18,  // Divide
        24: 14,  // Hue
        25: 15,  // Saturation
        26: 16,  // Color
        27: 30   // Luminosity
    };
    return premiereBlendToVit[blendMode] || 0;
}


/**
 * Determine if a clip is a generator/title (no media file).
 */
function isGeneratorClip(clip) {
    if (!clip.projectItem) return true;
    try {
        var path = clip.projectItem.getMediaPath();
        if (!path || path === "") return true;
    } catch (e) {
        return true;
    }
    return false;
}


/**
 * Serialize all video tracks.
 * Returns JSON string matching {video_tracks: [VideoTrack.to_dict()], asset_paths: [...]}.
 */
function serializeVideoTracks() {
    var seq = app.project.activeSequence;
    if (!seq) return '{"error": "No active sequence"}';

    var seqWidth = parseInt(seq.frameSizeHorizontal, 10) || 1920;
    var seqHeight = parseInt(seq.frameSizeVertical, 10) || 1080;
    var videoTracks = [];
    var assetPaths = [];

    for (var ti = 0; ti < seq.videoTracks.numTracks; ti++) {
        var track = seq.videoTracks[ti];
        var trackIdx = ti + 1;
        var items = [];

        for (var ci = 0; ci < track.clips.numItems; ci++) {
            var clip = track.clips[ci];
            var itemId = "item_" + pad3(trackIdx) + "_" + pad3(ci);
            var clipName = clip.name || ("clip_" + trackIdx + "_" + ci);
            var mediaRef = "";
            var itemType = "media";
            var generatorName = "";

            if (isGeneratorClip(clip)) {
                itemType = "generator";
                generatorName = clipName;
                mediaRef = "generator:" + itemId;
                // Check if it's a title
                var lowerName = clipName.toLowerCase();
                if (lowerName.indexOf("text") >= 0 || lowerName.indexOf("title") >= 0 ||
                    lowerName.indexOf("caption") >= 0 || lowerName.indexOf("subtitle") >= 0 ||
                    lowerName.indexOf("lower third") >= 0) {
                    itemType = "title";
                }
            } else {
                var mediaPath = clip.projectItem.getMediaPath();
                mediaRef = mediaPath || ("unknown_" + ci);
                // Collect paths for asset manifest (hashing done in Node.js)
                if (mediaPath && mediaPath !== "") {
                    assetPaths.push(mediaPath);
                }
            }

            var transform = readClipTransform(clip, seqWidth, seqHeight);
            var compositeMode = readBlendMode(clip);

            // Speed
            var speedPercent = 100.0;
            try {
                var spd = clip.getSpeed();
                if (spd !== undefined && spd !== null) {
                    speedPercent = Math.round(spd * 100 * 10000) / 10000;
                }
            } catch (e) {}

            // Enabled state
            var clipEnabled = true;
            try {
                clipEnabled = !clip.disabled;
            } catch (e) {}

            // Build the VideoItem dict
            var item = {
                "id": itemId,
                "name": clipName,
                "media_ref": mediaRef,
                "record_start_frame": ticksToFrames(clip.start.ticks, seq),
                "record_end_frame": ticksToFrames(clip.end.ticks, seq),
                "source_start_frame": ticksToFrames(clip.inPoint.ticks, seq),
                "source_end_frame": ticksToFrames(clip.outPoint.ticks, seq),
                "track_index": trackIdx,
                "transform": transform
            };

            // Conditional fields (match models.py VideoItem.to_dict())
            if (speedPercent !== 100.0) {
                item["speed"] = {"speed_percent": speedPercent};
            }
            if (compositeMode !== 0) {
                item["composite_mode"] = compositeMode;
            }
            if (!clipEnabled) {
                item["clip_enabled"] = false;
            }
            if (itemType !== "media") {
                item["item_type"] = itemType;
            }
            if (generatorName !== "") {
                item["generator_name"] = generatorName;
            }
            // fusion_comp_file: Premiere doesn't have Fusion, use ""
            // text_properties: could extract from Essential Graphics, future work

            items.push(item);
        }

        videoTracks.push({
            "index": trackIdx,
            "items": items
        });
    }

    return JSON.stringify({
        "video_tracks": videoTracks,
        "asset_paths": assetPaths
    });
}


/**
 * Serialize all audio tracks.
 * Returns JSON string matching {audio_tracks: [AudioTrack.to_dict()]}.
 */
function serializeAudioTracks() {
    var seq = app.project.activeSequence;
    if (!seq) return '{"error": "No active sequence"}';

    var audioTracks = [];

    for (var ti = 0; ti < seq.audioTracks.numTracks; ti++) {
        var track = seq.audioTracks[ti];
        var trackIdx = ti + 1;
        var items = [];

        for (var ci = 0; ci < track.clips.numItems; ci++) {
            var clip = track.clips[ci];
            var audioId = "audio_" + pad3(trackIdx) + "_" + pad3(ci);

            // Media ref
            var mediaRef = "";
            try {
                var mediaPath = clip.projectItem.getMediaPath();
                mediaRef = mediaPath || ("unknown_a" + ci);
            } catch (e) {
                mediaRef = "unknown_a" + ci;
            }

            // Volume and pan from audio components
            var volume = 0.0;
            var pan = 0.0;

            // Audio clip's Volume component
            var volumeComp = findComponent(clip, "Volume");
            if (volumeComp) {
                var volVal = getComponentPropertyValue(volumeComp, "Level");
                if (volVal !== undefined) {
                    volume = Math.round(volVal * 100) / 100;
                }
            }

            // Channel Volume / Panner
            var pannerComp = findComponent(clip, "Panner");
            if (!pannerComp) {
                pannerComp = findComponent(clip, "Channel Volume");
            }
            if (pannerComp) {
                var panVal = getComponentPropertyValue(pannerComp, "Balance");
                if (panVal === undefined) {
                    panVal = getComponentPropertyValue(pannerComp, "Pan");
                }
                if (panVal !== undefined) {
                    pan = Math.round(panVal * 100) / 100;
                }
            }

            // Speed
            var speedPercent = 100.0;
            try {
                var spd = clip.getSpeed();
                if (spd !== undefined && spd !== null) {
                    speedPercent = Math.round(spd * 100 * 10000) / 10000;
                }
            } catch (e) {}

            var audioItem = {
                "id": audioId,
                "media_ref": mediaRef,
                "start_frame": ticksToFrames(clip.start.ticks, seq),
                "end_frame": ticksToFrames(clip.end.ticks, seq),
                "volume": volume,
                "pan": pan
            };

            if (speedPercent !== 100.0) {
                audioItem["speed"] = {"speed_percent": speedPercent};
            }

            items.push(audioItem);
        }

        audioTracks.push({
            "index": trackIdx,
            "items": items
        });
    }

    return JSON.stringify({"audio_tracks": audioTracks});
}


/**
 * Serialize color grades (Lumetri Color) for all video clips.
 * Returns JSON string matching {grades: {clip_id: ColorGrade.to_dict()}}.
 *
 * Advantage over Resolve: Lumetri properties are directly readable.
 */
function serializeColor() {
    var seq = app.project.activeSequence;
    if (!seq) return '{"error": "No active sequence"}';

    var grades = {};

    for (var ti = 0; ti < seq.videoTracks.numTracks; ti++) {
        var track = seq.videoTracks[ti];
        var trackIdx = ti + 1;

        for (var ci = 0; ci < track.clips.numItems; ci++) {
            var clip = track.clips[ci];
            var itemId = "item_" + pad3(trackIdx) + "_" + pad3(ci);

            // Find Lumetri Color effect
            var lumetri = null;
            if (clip.components) {
                for (var ei = 0; ei < clip.components.numItems; ei++) {
                    if (clip.components[ei].displayName === "Lumetri Color") {
                        lumetri = clip.components[ei];
                        break;
                    }
                }
            }

            if (!lumetri) {
                // No Lumetri — single empty node
                grades[itemId] = {
                    "num_nodes": 1,
                    "nodes": [{"index": 1, "label": "", "lut": ""}],
                    "version_name": "",
                    "drx_file": null,
                    "lut_file": null
                };
                continue;
            }

            // Read Lumetri properties — single node = single Lumetri instance
            var node = {
                "index": 1,
                "label": "Lumetri",
                "lut": ""
            };

            // Basic Correction
            var temp = getComponentPropertyValue(lumetri, "Temperature");
            if (temp !== undefined && temp !== null) node["temperature"] = Math.round(temp * 1000) / 1000;

            var tintVal = getComponentPropertyValue(lumetri, "Tint");
            if (tintVal !== undefined && tintVal !== null) node["tint"] = Math.round(tintVal * 1000) / 1000;

            var exposure = getComponentPropertyValue(lumetri, "Exposure");
            // Map Exposure to gain_m (master gain) — closest equivalent
            if (exposure !== undefined && exposure !== null && exposure !== 0) {
                node["gain_m"] = Math.round(exposure * 1000) / 1000;
            }

            var contrast = getComponentPropertyValue(lumetri, "Contrast");
            if (contrast !== undefined && contrast !== null) node["contrast"] = Math.round(contrast * 1000) / 1000;

            var highlights = getComponentPropertyValue(lumetri, "Highlights");
            if (highlights !== undefined && highlights !== null && highlights !== 0) {
                node["gain_r"] = Math.round(highlights * 1000) / 1000;
            }

            var shadows = getComponentPropertyValue(lumetri, "Shadows");
            if (shadows !== undefined && shadows !== null && shadows !== 0) {
                node["lift_m"] = Math.round(shadows * 1000) / 1000;
            }

            var whites = getComponentPropertyValue(lumetri, "Whites");
            if (whites !== undefined && whites !== null && whites !== 0) {
                node["gain_g"] = Math.round(whites * 1000) / 1000;
            }

            var blacks = getComponentPropertyValue(lumetri, "Blacks");
            if (blacks !== undefined && blacks !== null && blacks !== 0) {
                node["lift_r"] = Math.round(blacks * 1000) / 1000;
            }

            var saturation = getComponentPropertyValue(lumetri, "Saturation");
            if (saturation !== undefined && saturation !== null) {
                node["saturation"] = Math.round((saturation / 100) * 10000) / 10000;
            }

            // Creative section
            var vibrance = getComponentPropertyValue(lumetri, "Vibrance");
            if (vibrance !== undefined && vibrance !== null && vibrance !== 0) {
                node["color_boost"] = Math.round(vibrance * 1000) / 1000;
            }

            // Sharpness
            var sharpness = getComponentPropertyValue(lumetri, "Sharpen");
            if (sharpness !== undefined && sharpness !== null && sharpness !== 0) {
                node["sharpness"] = Math.round(sharpness * 1000) / 1000;
            }

            // Check for input LUT
            var lutPath = getComponentPropertyValue(lumetri, "Input LUT");
            if (lutPath !== undefined && lutPath !== null && lutPath !== "") {
                node["lut"] = String(lutPath);
            }

            grades[itemId] = {
                "num_nodes": 1,
                "nodes": [node],
                "version_name": "",
                "drx_file": null,
                "lut_file": null
            };
        }
    }

    return JSON.stringify({"grades": grades});
}


/**
 * Serialize timeline markers.
 * Returns JSON string matching {markers: [Marker.to_dict()]}.
 */
function serializeMarkers() {
    var seq = app.project.activeSequence;
    if (!seq) return '{"error": "No active sequence"}';

    var markers = [];
    var seqMarkers = seq.markers;

    if (seqMarkers && seqMarkers.numMarkers > 0) {
        for (var i = 0; i < seqMarkers.numMarkers; i++) {
            var marker;
            if (i === 0) {
                marker = seqMarkers.getFirstMarker();
            } else {
                marker = seqMarkers.getNextMarker(marker);
            }
            if (!marker) break;

            var frame = ticksToFrames(marker.start.ticks, seq);
            var endFrame = ticksToFrames(marker.end.ticks, seq);
            var duration = endFrame - frame;
            if (duration < 1) duration = 1;

            // Map color
            var colorName = "Blue";
            var colorIdx = marker.colorIndex;
            if (colorIdx !== undefined && MARKER_COLOR_MAP[colorIdx] !== undefined) {
                colorName = MARKER_COLOR_MAP[colorIdx];
            } else if (marker.type !== undefined) {
                // Fallback: some versions expose type instead of colorIndex
                if (MARKER_COLOR_MAP[marker.type] !== undefined) {
                    colorName = MARKER_COLOR_MAP[marker.type];
                }
            }

            markers.push({
                "frame": frame,
                "color": colorName,
                "name": marker.name || "",
                "note": marker.comments || "",
                "duration": duration
            });
        }
    }

    return JSON.stringify({"markers": markers});
}


/**
 * Serialize the complete timeline — calls all serialize functions.
 * Returns a JSON string with all domain data.
 */
function serializeTimeline() {
    var metadata = serializeMetadata();
    var cuts = serializeVideoTracks();
    var audio = serializeAudioTracks();
    var color = serializeColor();
    var markers = serializeMarkers();

    return JSON.stringify({
        "metadata": metadata,
        "cuts": cuts,
        "audio": audio,
        "color": color,
        "markers": markers
    });
}
