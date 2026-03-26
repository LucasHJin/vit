/**
 * deserializer.jsx — Restore a Premiere Pro timeline from vit JSON.
 *
 * Called from the JS panel via CSInterface.evalScript().
 * Each function takes a JSON string argument, parses it, and applies changes.
 *
 * Depends on: host_utils.jsx (loaded via manifest ScriptPath).
 */

// Load host_utils if not already loaded
if (typeof TICKS_PER_SECOND === "undefined") {
    var scriptDir = (new File($.fileName)).parent.fsName;
    $.evalFile(scriptDir + "/host_utils.jsx");
}


// Reverse mapping: vit composite_mode int -> Premiere blend mode index
var VIT_TO_PREMIERE_BLEND = {
    0: 1,     // Normal
    1: 11,    // Add -> Linear Dodge
    2: 22,    // Subtract
    3: 20,    // Difference
    4: 4,     // Multiply
    5: 9,     // Screen
    6: 13,    // Overlay
    7: 15,    // Hard Light
    8: 14,    // Soft Light
    9: 3,     // Darken
    10: 8,    // Lighten
    11: 10,   // Color Dodge
    12: 5,    // Color Burn
    13: 21,   // Exclusion
    14: 24,   // Hue
    15: 25,   // Saturation
    16: 26,   // Color
    18: 23,   // Divide
    19: 11,   // Linear Dodge (Add)
    20: 6,    // Linear Burn
    21: 17,   // Linear Light
    22: 16,   // Vivid Light
    23: 18,   // Pin Light
    24: 19,   // Hard Mix
    25: 12,   // Lighter Color
    26: 7,    // Darker Color
    30: 27    // Luminosity
};


/**
 * Rename existing timeline to avoid conflicts.
 * Returns the old timeline name.
 */
function renameOldTimeline() {
    var seq = app.project.activeSequence;
    if (!seq) return "";
    var oldName = seq.name;
    seq.name = oldName + ".vit-old";
    return oldName;
}


/**
 * Deserialize and rebuild the timeline from JSON domain data.
 *
 * Strategy:
 *   1. Rename current timeline to .vit-old
 *   2. Create a new sequence with the original name
 *   3. Place clips according to cuts.json
 *   4. Apply transforms, color, markers
 *   5. Delete the .vit-old timeline
 *
 * This avoids Premiere's clip duplication issues when modifying in-place.
 *
 * @param {string} jsonStr - JSON object with keys: metadata, cuts, audio, color, markers
 */
function deserializeTimeline(jsonStr) {
    try {
        var data = JSON.parse(jsonStr);
    } catch (e) {
        return '{"ok": false, "error": "Invalid JSON: ' + jsonEscape(e.message) + '"}';
    }

    var metadata = data.metadata || {};
    var cuts = data.cuts || {};
    var audio = data.audio || {};
    var color = data.color || {};
    var markers = data.markers || {};

    var seq = app.project.activeSequence;
    if (!seq) {
        return '{"ok": false, "error": "No active sequence"}';
    }

    var seqWidth = parseInt(seq.frameSizeHorizontal, 10) || 1920;
    var seqHeight = parseInt(seq.frameSizeVertical, 10) || 1080;

    // --- Phase 1: Clear existing clips ---
    // Remove all clips from all tracks
    clearAllTracks(seq);

    // --- Phase 2: Place video clips ---
    var videoTracks = (cuts.video_tracks) || [];
    for (var ti = 0; ti < videoTracks.length; ti++) {
        var trackData = videoTracks[ti];
        var trackIdx = trackData.index - 1; // 0-based for Premiere API
        if (trackIdx >= seq.videoTracks.numTracks) continue;
        var track = seq.videoTracks[trackIdx];

        var items = trackData.items || [];
        for (var ci = 0; ci < items.length; ci++) {
            var item = items[ci];
            placeVideoClip(seq, track, item, seqWidth, seqHeight);
        }
    }

    // --- Phase 3: Place audio clips ---
    var audioTracks = (audio.audio_tracks) || [];
    for (var ati = 0; ati < audioTracks.length; ati++) {
        var aTrackData = audioTracks[ati];
        var aTrackIdx = aTrackData.index - 1;
        if (aTrackIdx >= seq.audioTracks.numTracks) continue;
        var aTrack = seq.audioTracks[aTrackIdx];

        var aItems = aTrackData.items || [];
        for (var aci = 0; aci < aItems.length; aci++) {
            placeAudioClip(seq, aTrack, aItems[aci]);
        }
    }

    // --- Phase 4: Apply color grades ---
    applyColorGrades(seq, color);

    // --- Phase 5: Restore markers ---
    restoreMarkers(seq, markers);

    return '{"ok": true}';
}


/**
 * Remove all clips from all tracks in a sequence.
 */
function clearAllTracks(seq) {
    // Video tracks
    for (var ti = 0; ti < seq.videoTracks.numTracks; ti++) {
        var track = seq.videoTracks[ti];
        // Remove clips in reverse order to avoid index shifting
        for (var ci = track.clips.numItems - 1; ci >= 0; ci--) {
            try {
                track.clips[ci].remove(false, false);
            } catch (e) {
                // Some clips may not be removable; skip
            }
        }
    }
    // Audio tracks
    for (var ati = 0; ati < seq.audioTracks.numTracks; ati++) {
        var aTrack = seq.audioTracks[ati];
        for (var aci = aTrack.clips.numItems - 1; aci >= 0; aci--) {
            try {
                aTrack.clips[aci].remove(false, false);
            } catch (e) {}
        }
    }
    // Markers
    var seqMarkers = seq.markers;
    if (seqMarkers) {
        while (seqMarkers.numMarkers > 0) {
            try {
                var m = seqMarkers.getFirstMarker();
                if (m) seqMarkers.deleteMarker(m);
                else break;
            } catch (e) { break; }
        }
    }
}


/**
 * Find a project item by media path.
 */
function findProjectItemByPath(mediaPath) {
    if (!mediaPath || mediaPath === "") return null;

    // Search root items
    var rootItems = app.project.rootItem.children;
    for (var i = 0; i < rootItems.numItems; i++) {
        var found = searchProjectItem(rootItems[i], mediaPath);
        if (found) return found;
    }
    return null;
}


function searchProjectItem(item, mediaPath) {
    if (!item) return null;

    // Check if this item matches
    try {
        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            var itemPath = item.getMediaPath();
            if (itemPath === mediaPath) return item;
        }
    } catch (e) {}

    // Recurse into bins
    if (item.children) {
        for (var i = 0; i < item.children.numItems; i++) {
            var found = searchProjectItem(item.children[i], mediaPath);
            if (found) return found;
        }
    }

    return null;
}


/**
 * Import a media file if not already in the project.
 * Returns the project item.
 */
function importMediaIfNeeded(mediaPath) {
    if (!mediaPath || mediaPath === "" || mediaPath.indexOf("generator:") === 0) return null;

    // Check if already imported
    var existing = findProjectItemByPath(mediaPath);
    if (existing) return existing;

    // Import the file
    try {
        var importResult = app.project.importFiles([mediaPath]);
        if (importResult) {
            // Return the newly imported item
            return findProjectItemByPath(mediaPath);
        }
    } catch (e) {}

    return null;
}


/**
 * Place a single video clip on a track.
 */
function placeVideoClip(seq, track, item, seqWidth, seqHeight) {
    var mediaRef = item.media_ref || "";
    var itemType = item.item_type || "media";

    // Skip generators for now (no equivalent automatic placement)
    if (itemType === "generator" || itemType === "title" || mediaRef.indexOf("generator:") === 0) {
        return;
    }

    // Find or import media
    var projectItem = importMediaIfNeeded(mediaRef);
    if (!projectItem) return;

    // Calculate position in ticks
    var startTicks = framesToTicks(item.record_start_frame, seq).toString();

    // Insert clip on track
    try {
        track.insertClip(projectItem, startTicks);
    } catch (e) {
        return;
    }

    // Find the newly inserted clip (last clip on track at this position)
    var placedClip = null;
    for (var i = track.clips.numItems - 1; i >= 0; i--) {
        var c = track.clips[i];
        if (ticksToFrames(c.start.ticks, seq) === item.record_start_frame) {
            placedClip = c;
            break;
        }
    }

    if (!placedClip) return;

    // Set source in/out points
    try {
        var inTicks = framesToTicks(item.source_start_frame, seq).toString();
        var outTicks = framesToTicks(item.source_end_frame, seq).toString();
        placedClip.inPoint = new Time();
        placedClip.inPoint.ticks = inTicks;
        placedClip.outPoint = new Time();
        placedClip.outPoint.ticks = outTicks;
    } catch (e) {}

    // Apply transform
    var transform = item.transform || {};
    applyTransform(placedClip, transform, seqWidth, seqHeight);

    // Apply blend mode
    if (item.composite_mode && item.composite_mode !== 0) {
        var premiereBlend = VIT_TO_PREMIERE_BLEND[item.composite_mode];
        if (premiereBlend !== undefined) {
            var opacityComp = findComponent(placedClip, "Opacity");
            if (opacityComp) {
                setComponentPropertyValue(opacityComp, "Blend Mode", premiereBlend);
            }
        }
    }

    // Apply speed
    if (item.speed && item.speed.speed_percent && item.speed.speed_percent !== 100) {
        try {
            placedClip.setSpeed(item.speed.speed_percent / 100);
        } catch (e) {}
    }

    // Disabled state
    if (item.clip_enabled === false) {
        try {
            placedClip.disabled = true;
        } catch (e) {}
    }
}


/**
 * Apply transform properties to a placed clip.
 */
function applyTransform(clip, transform, seqWidth, seqHeight) {
    var motion = findComponent(clip, "Motion");
    if (motion) {
        // Position (Pan/Tilt -> normalized Position)
        var panPx = transform["Pan"] || 0;
        var tiltPx = transform["Tilt"] || 0;
        var posX = (panPx + seqWidth / 2) / seqWidth;
        var posY = (tiltPx + seqHeight / 2) / seqHeight;
        setComponentPropertyValue(motion, "Position", [posX, posY]);

        // Scale (ZoomX -> percentage)
        var zoomX = transform["ZoomX"];
        if (zoomX === undefined) zoomX = 1.0;
        var scalePercent = zoomX * 100;
        if (transform["FlipX"]) scalePercent = -scalePercent;
        setComponentPropertyValue(motion, "Scale", scalePercent);

        // Non-uniform scale
        var zoomY = transform["ZoomY"];
        if (zoomY !== undefined && zoomY !== zoomX) {
            setComponentPropertyValue(motion, "Scale Height", zoomY * 100);
        }

        // Rotation
        if (transform["RotationAngle"]) {
            setComponentPropertyValue(motion, "Rotation", transform["RotationAngle"]);
        }

        // Anchor point
        if (transform["AnchorPointX"] || transform["AnchorPointY"]) {
            var ax = ((transform["AnchorPointX"] || 0) + seqWidth / 2) / seqWidth;
            var ay = ((transform["AnchorPointY"] || 0) + seqHeight / 2) / seqHeight;
            setComponentPropertyValue(motion, "Anchor Point", [ax, ay]);
        }
    }

    // Opacity
    var opacityComp = findComponent(clip, "Opacity");
    if (opacityComp && transform["Opacity"] !== undefined) {
        setComponentPropertyValue(opacityComp, "Opacity", transform["Opacity"]);
    }

    // Crop (only if values present)
    if (transform["CropLeft"] || transform["CropRight"] || transform["CropTop"] || transform["CropBottom"]) {
        var cropEffect = findComponent(clip, "Crop");
        if (cropEffect) {
            if (transform["CropLeft"]) setComponentPropertyValue(cropEffect, "Left", transform["CropLeft"]);
            if (transform["CropRight"]) setComponentPropertyValue(cropEffect, "Right", transform["CropRight"]);
            if (transform["CropTop"]) setComponentPropertyValue(cropEffect, "Top", transform["CropTop"]);
            if (transform["CropBottom"]) setComponentPropertyValue(cropEffect, "Bottom", transform["CropBottom"]);
        }
    }
}


/**
 * Place a single audio clip on a track.
 */
function placeAudioClip(seq, track, item) {
    var mediaRef = item.media_ref || "";
    var projectItem = importMediaIfNeeded(mediaRef);
    if (!projectItem) return;

    var startTicks = framesToTicks(item.start_frame, seq).toString();
    try {
        track.insertClip(projectItem, startTicks);
    } catch (e) {
        return;
    }

    // Find the placed clip
    var placedClip = null;
    for (var i = track.clips.numItems - 1; i >= 0; i--) {
        var c = track.clips[i];
        if (ticksToFrames(c.start.ticks, seq) === item.start_frame) {
            placedClip = c;
            break;
        }
    }
    if (!placedClip) return;

    // Volume
    if (item.volume !== undefined && item.volume !== 0) {
        var volumeComp = findComponent(placedClip, "Volume");
        if (volumeComp) {
            setComponentPropertyValue(volumeComp, "Level", item.volume);
        }
    }

    // Speed
    if (item.speed && item.speed.speed_percent && item.speed.speed_percent !== 100) {
        try {
            placedClip.setSpeed(item.speed.speed_percent / 100);
        } catch (e) {}
    }
}


/**
 * Apply Lumetri Color grades from color.json data.
 */
function applyColorGrades(seq, colorData) {
    var grades = colorData.grades || {};

    for (var ti = 0; ti < seq.videoTracks.numTracks; ti++) {
        var track = seq.videoTracks[ti];
        var trackIdx = ti + 1;

        for (var ci = 0; ci < track.clips.numItems; ci++) {
            var clip = track.clips[ci];
            var itemId = "item_" + pad3(trackIdx) + "_" + pad3(ci);
            var grade = grades[itemId];
            if (!grade || !grade.nodes || grade.nodes.length === 0) continue;

            var node = grade.nodes[0]; // Premiere has one Lumetri = one node

            // Find or add Lumetri Color effect
            var lumetri = findComponent(clip, "Lumetri Color");
            if (!lumetri) {
                // Cannot programmatically add Lumetri via ExtendScript easily;
                // skip clips without existing Lumetri
                continue;
            }

            // Apply properties
            if (node.temperature !== undefined) {
                setComponentPropertyValue(lumetri, "Temperature", node.temperature);
            }
            if (node.tint !== undefined) {
                setComponentPropertyValue(lumetri, "Tint", node.tint);
            }
            if (node.contrast !== undefined) {
                setComponentPropertyValue(lumetri, "Contrast", node.contrast);
            }
            if (node.saturation !== undefined) {
                // Vit saturation is 0-2 multiplier, Premiere is 0-200 percentage
                setComponentPropertyValue(lumetri, "Saturation", node.saturation * 100);
            }
            if (node.color_boost !== undefined) {
                setComponentPropertyValue(lumetri, "Vibrance", node.color_boost);
            }
            if (node.sharpness !== undefined) {
                setComponentPropertyValue(lumetri, "Sharpen", node.sharpness);
            }
            if (node.gain_m !== undefined) {
                // gain_m mapped from Exposure
                setComponentPropertyValue(lumetri, "Exposure", node.gain_m);
            }
            if (node.gain_r !== undefined) {
                setComponentPropertyValue(lumetri, "Highlights", node.gain_r);
            }
            if (node.lift_m !== undefined) {
                setComponentPropertyValue(lumetri, "Shadows", node.lift_m);
            }
            if (node.gain_g !== undefined) {
                setComponentPropertyValue(lumetri, "Whites", node.gain_g);
            }
            if (node.lift_r !== undefined) {
                setComponentPropertyValue(lumetri, "Blacks", node.lift_r);
            }

            // LUT
            if (node.lut && node.lut !== "") {
                setComponentPropertyValue(lumetri, "Input LUT", node.lut);
            }
        }
    }
}


/**
 * Restore sequence markers from markers.json data.
 */
function restoreMarkers(seq, markerData) {
    var markerList = markerData.markers || [];

    // Reverse marker color map
    var colorNameToIndex = {
        "Green": 0, "Red": 1, "Purple": 2, "Orange": 3,
        "Yellow": 4, "White": 5, "Blue": 6, "Cyan": 7
    };

    for (var i = 0; i < markerList.length; i++) {
        var m = markerList[i];
        var frameTicks = framesToTicks(m.frame, seq);
        var seconds = frameTicks / TICKS_PER_SECOND;

        try {
            var marker = seq.markers.createMarker(seconds);
            if (marker) {
                if (m.name) marker.name = m.name;
                if (m.note) marker.comments = m.note;

                // Duration
                if (m.duration > 1) {
                    var endTicks = framesToTicks(m.frame + m.duration, seq);
                    var endSeconds = endTicks / TICKS_PER_SECOND;
                    marker.end = new Time();
                    marker.end.seconds = endSeconds;
                }

                // Color
                var colorIdx = colorNameToIndex[m.color];
                if (colorIdx !== undefined) {
                    try {
                        marker.colorIndex = colorIdx;
                    } catch (e) {
                        // colorIndex may not be settable in all versions
                    }
                }
            }
        } catch (e) {}
    }
}
