/**
 * file_writer.js — Domain-split JSON file writing via Node.js.
 *
 * Mirrors vit/json_writer.py: writes JSON with indent=2, sort_keys=true,
 * trailing newline. Uses Node.js fs for file I/O and crypto for SHA256.
 */

/* global require */
var fs = require("fs");
var path = require("path");
var crypto = require("crypto");

var FileWriter = (function () {

    /**
     * JSON.stringify with sorted keys (matching Python's sort_keys=True).
     */
    function jsonStringifySorted(obj, indent) {
        return JSON.stringify(obj, function (key, value) {
            if (value && typeof value === "object" && !Array.isArray(value)) {
                var sorted = {};
                Object.keys(value).sort().forEach(function (k) {
                    sorted[k] = value[k];
                });
                return sorted;
            }
            return value;
        }, indent);
    }

    /**
     * Write JSON to a file with consistent formatting.
     * Creates parent directories as needed.
     */
    function writeJson(filepath, data) {
        var dir = path.dirname(filepath);
        fs.mkdirSync(dir, { recursive: true });
        var content = jsonStringifySorted(data, 2) + "\n";
        fs.writeFileSync(filepath, content, "utf8");
    }

    /**
     * Write timeline/cuts.json
     */
    function writeCuts(projectDir, videoTracks) {
        writeJson(path.join(projectDir, "timeline", "cuts.json"), {
            video_tracks: videoTracks
        });
    }

    /**
     * Write timeline/audio.json
     */
    function writeAudio(projectDir, audioTracks) {
        writeJson(path.join(projectDir, "timeline", "audio.json"), {
            audio_tracks: audioTracks
        });
    }

    /**
     * Write timeline/color.json
     */
    function writeColor(projectDir, grades) {
        writeJson(path.join(projectDir, "timeline", "color.json"), {
            grades: grades
        });
    }

    /**
     * Write timeline/effects.json
     */
    function writeEffects(projectDir, effects) {
        writeJson(path.join(projectDir, "timeline", "effects.json"), effects || {});
    }

    /**
     * Write timeline/markers.json
     */
    function writeMarkers(projectDir, markers) {
        writeJson(path.join(projectDir, "timeline", "markers.json"), {
            markers: markers
        });
    }

    /**
     * Write timeline/metadata.json
     */
    function writeMetadata(projectDir, metadata) {
        writeJson(path.join(projectDir, "timeline", "metadata.json"), metadata);
    }

    /**
     * Compute SHA256 hash of a file (first 12 hex chars).
     * Returns "sha256:<hash>" or path-based fallback.
     */
    function computeMediaHash(filepath) {
        try {
            var hash = crypto.createHash("sha256");
            var buffer = fs.readFileSync(filepath);
            hash.update(buffer);
            return "sha256:" + hash.digest("hex").substring(0, 12);
        } catch (e) {
            // File may not be accessible — use path-based fallback
            var pathHash = crypto.createHash("sha256").update(filepath).digest("hex").substring(0, 12);
            return "sha256:" + pathHash;
        }
    }

    /**
     * Build and write assets/manifest.json from a list of media file paths.
     * Returns the path->hash mapping for use as media_ref in cuts.json.
     */
    function writeManifest(projectDir, assetPaths) {
        var assets = {};
        var pathToRef = {};

        // Deduplicate paths
        var uniquePaths = [];
        var seen = {};
        for (var i = 0; i < assetPaths.length; i++) {
            if (!seen[assetPaths[i]]) {
                seen[assetPaths[i]] = true;
                uniquePaths.push(assetPaths[i]);
            }
        }

        for (var j = 0; j < uniquePaths.length; j++) {
            var mediaPath = uniquePaths[j];
            var ref = computeMediaHash(mediaPath);
            pathToRef[mediaPath] = ref;

            if (!assets[ref]) {
                var filename = path.basename(mediaPath);
                var durationFrames = 0;
                var codec = "unknown";
                var resolution = "unknown";

                assets[ref] = {
                    filename: filename,
                    original_path: mediaPath,
                    duration_frames: durationFrames,
                    codec: codec,
                    resolution: resolution
                };
            }
        }

        writeJson(path.join(projectDir, "assets", "manifest.json"), {
            assets: assets
        });

        return pathToRef;
    }

    /**
     * Write all domain-split JSON files from serialized data.
     *
     * @param {string} projectDir - Path to vit project
     * @param {object} data - Parsed serialized data with keys:
     *   metadata, cuts (with video_tracks + asset_paths), audio, color, markers
     */
    function writeAll(projectDir, data) {
        // Parse sub-objects (they come as JSON strings from ExtendScript)
        var metadata = typeof data.metadata === "string" ? JSON.parse(data.metadata) : data.metadata;
        var cuts = typeof data.cuts === "string" ? JSON.parse(data.cuts) : data.cuts;
        var audio = typeof data.audio === "string" ? JSON.parse(data.audio) : data.audio;
        var color = typeof data.color === "string" ? JSON.parse(data.color) : data.color;
        var markers = typeof data.markers === "string" ? JSON.parse(data.markers) : data.markers;

        // Build asset manifest and get path->ref mapping
        var assetPaths = cuts.asset_paths || [];
        var pathToRef = writeManifest(projectDir, assetPaths);

        // Replace media_ref paths with SHA256 hashes in video tracks
        var videoTracks = cuts.video_tracks || [];
        for (var ti = 0; ti < videoTracks.length; ti++) {
            var items = videoTracks[ti].items || [];
            for (var ci = 0; ci < items.length; ci++) {
                var item = items[ci];
                if (item.media_ref && pathToRef[item.media_ref]) {
                    item.media_ref = pathToRef[item.media_ref];
                }
            }
        }

        // Replace media_ref paths in audio tracks
        var audioTracks = (audio.audio_tracks) || [];
        for (var ati = 0; ati < audioTracks.length; ati++) {
            var aItems = audioTracks[ati].items || [];
            for (var aci = 0; aci < aItems.length; aci++) {
                var aItem = aItems[aci];
                if (aItem.media_ref && pathToRef[aItem.media_ref]) {
                    aItem.media_ref = pathToRef[aItem.media_ref];
                }
            }
        }

        // Write all domain files
        writeMetadata(projectDir, metadata);
        writeCuts(projectDir, videoTracks);
        writeAudio(projectDir, audioTracks);
        writeColor(projectDir, (color.grades) || {});
        writeMarkers(projectDir, (markers.markers) || []);
        writeEffects(projectDir, {});
    }

    /**
     * Read all domain JSON files.
     */
    function readAll(projectDir) {
        function readJson(filepath) {
            try {
                return JSON.parse(fs.readFileSync(filepath, "utf8"));
            } catch (e) {
                return {};
            }
        }

        return {
            metadata: readJson(path.join(projectDir, "timeline", "metadata.json")),
            cuts: readJson(path.join(projectDir, "timeline", "cuts.json")),
            audio: readJson(path.join(projectDir, "timeline", "audio.json")),
            color: readJson(path.join(projectDir, "timeline", "color.json")),
            effects: readJson(path.join(projectDir, "timeline", "effects.json")),
            markers: readJson(path.join(projectDir, "timeline", "markers.json")),
            manifest: readJson(path.join(projectDir, "assets", "manifest.json"))
        };
    }

    return {
        writeJson: writeJson,
        writeCuts: writeCuts,
        writeAudio: writeAudio,
        writeColor: writeColor,
        writeEffects: writeEffects,
        writeMarkers: writeMarkers,
        writeMetadata: writeMetadata,
        writeManifest: writeManifest,
        writeAll: writeAll,
        readAll: readAll,
        computeMediaHash: computeMediaHash,
        jsonStringifySorted: jsonStringifySorted
    };
})();

// Node.js module export (no-op in CEP browser context)
if (typeof module !== "undefined" && module.exports) {
    module.exports = FileWriter;
}
