/**
 * host_utils.jsx — Time conversion helpers for Premiere Pro ExtendScript.
 *
 * Premiere uses ticks internally (254016000000 ticks/sec).
 * Vit uses frame numbers. These helpers convert between the two.
 */

// Premiere's internal tick rate (constant across all versions)
var TICKS_PER_SECOND = 254016000000;

/**
 * Get the frame rate of a sequence as a float.
 * Premiere stores timebase as ticks-per-frame.
 */
function getFps(sequence) {
    var timebase = parseInt(sequence.timebase, 10);
    if (!timebase || timebase <= 0) return 24.0;
    return TICKS_PER_SECOND / timebase;
}

/**
 * Get ticks-per-frame for a sequence.
 */
function getTicksPerFrame(sequence) {
    return parseInt(sequence.timebase, 10) || Math.round(TICKS_PER_SECOND / 24);
}

/**
 * Convert ticks to frame number.
 */
function ticksToFrames(ticks, sequence) {
    var tpf = getTicksPerFrame(sequence);
    return Math.round(parseInt(ticks, 10) / tpf);
}

/**
 * Convert frame number to ticks.
 */
function framesToTicks(frames, sequence) {
    var tpf = getTicksPerFrame(sequence);
    return frames * tpf;
}

/**
 * Convert ticks to timecode string (HH:MM:SS:FF).
 */
function ticksToTimecode(ticks, sequence) {
    var fps = getFps(sequence);
    var ifps = Math.round(fps);
    var totalFrames = ticksToFrames(ticks, sequence);
    if (totalFrames < 0) totalFrames = 0;

    var ff = totalFrames % ifps;
    var totalSecs = Math.floor(totalFrames / ifps);
    var ss = totalSecs % 60;
    var totalMins = Math.floor(totalSecs / 60);
    var mm = totalMins % 60;
    var hh = Math.floor(totalMins / 60);

    return pad2(hh) + ":" + pad2(mm) + ":" + pad2(ss) + ":" + pad2(ff);
}

/**
 * Zero-pad a number to 2 digits.
 */
function pad2(n) {
    return (n < 10 ? "0" : "") + n;
}

/**
 * Zero-pad a number to 3 digits.
 */
function pad3(n) {
    if (n < 10) return "00" + n;
    if (n < 100) return "0" + n;
    return "" + n;
}

/**
 * Safely read a component property value by name.
 * Returns the static value (no keyframe support).
 */
function getComponentPropertyValue(component, propName) {
    if (!component || !component.properties) return undefined;
    for (var i = 0; i < component.properties.numItems; i++) {
        var prop = component.properties[i];
        if (prop.displayName === propName) {
            return prop.getValue();
        }
    }
    return undefined;
}

/**
 * Set a component property value by name.
 */
function setComponentPropertyValue(component, propName, value) {
    if (!component || !component.properties) return false;
    for (var i = 0; i < component.properties.numItems; i++) {
        var prop = component.properties[i];
        if (prop.displayName === propName) {
            prop.setValue(value, true);
            return true;
        }
    }
    return false;
}

/**
 * Find a component (effect) by displayName on a clip.
 */
function findComponent(clip, componentName) {
    if (!clip.components) return null;
    for (var i = 0; i < clip.components.numItems; i++) {
        if (clip.components[i].displayName === componentName) {
            return clip.components[i];
        }
    }
    return null;
}

/**
 * Get the sequence's start timecode as a string.
 */
function getStartTimecode(sequence) {
    var startTicks = parseInt(sequence.zeroPoint, 10);
    return ticksToTimecode(Math.abs(startTicks), sequence);
}

/**
 * Escape a string for safe JSON embedding.
 */
function jsonEscape(str) {
    if (str === undefined || str === null) return "";
    return String(str)
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\n/g, "\\n")
        .replace(/\r/g, "\\r")
        .replace(/\t/g, "\\t");
}
