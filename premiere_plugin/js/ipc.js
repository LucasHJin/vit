/**
 * ipc.js — Node.js <-> Python subprocess communication.
 *
 * Spawns premiere_bridge.py as a child process and communicates via
 * newline-delimited JSON over stdin/stdout.
 */

/* global require */
var child_process = require("child_process");
var path = require("path");
var os = require("os");

var VitIPC = (function () {
    var _process = null;
    var _buffer = "";
    var _pendingResolve = null;
    var _onLog = null;

    /**
     * Find the system Python 3 binary.
     */
    function findPython() {
        var candidates = [];
        var platform = os.platform();
        var homeDir = os.homedir();

        // Check vit installer venv first
        var vitVenvBin = platform === "win32" ? "Scripts\\python.exe" : "bin/python3";
        var vitVenvPy = path.join(homeDir, ".vit", "venv", vitVenvBin);
        candidates.push(vitVenvPy);

        if (platform === "win32") {
            candidates.push("py");
            candidates.push("python3");
            candidates.push("python");
        } else {
            candidates.push("/usr/local/bin/python3");
            candidates.push("/opt/homebrew/bin/python3");
            candidates.push("/usr/bin/python3");
            candidates.push(path.join(homeDir, ".pyenv", "shims", "python3"));
            candidates.push("python3");
            candidates.push("python");
        }

        for (var i = 0; i < candidates.length; i++) {
            try {
                var result = child_process.spawnSync(candidates[i], ["--version"], {
                    timeout: 5000,
                    stdio: "pipe"
                });
                if (result.status === 0) {
                    return candidates[i];
                }
            } catch (e) {
                // skip
            }
        }
        return null;
    }

    /**
     * Start the Python vit-core subprocess.
     * @param {string} projectDir - Path to the vit project directory
     * @param {function} logCallback - Optional callback for log messages
     */
    function start(projectDir, logCallback) {
        if (_process) return;
        _onLog = logCallback || function () {};

        var python = findPython();
        if (!python) {
            _onLog("ERROR: Python 3 not found. Install Python 3 and ensure it's on PATH.");
            return;
        }

        var bridgeScript = path.join(__dirname, "..", "premiere_bridge.py");

        _onLog("Starting vit bridge: " + python + " " + bridgeScript);

        _process = child_process.spawn(python, ["-u", bridgeScript, "--project-dir", projectDir], {
            stdio: ["pipe", "pipe", "pipe"],
            env: Object.assign({}, process.env, { PYTHONUNBUFFERED: "1" })
        });

        _process.stdout.on("data", function (data) {
            _buffer += data.toString();
            // Process complete JSON messages
            var lines = _buffer.split("\n");
            _buffer = lines.pop(); // Keep incomplete last line in buffer

            for (var i = 0; i < lines.length; i++) {
                var line = lines[i].trim();
                if (!line) continue;
                try {
                    var response = JSON.parse(line);
                    if (_pendingResolve) {
                        var resolve = _pendingResolve;
                        _pendingResolve = null;
                        resolve(response);
                    }
                } catch (e) {
                    _onLog("Bad JSON from bridge: " + line);
                }
            }
        });

        _process.stderr.on("data", function (data) {
            _onLog(data.toString().trim());
        });

        _process.on("exit", function (code) {
            _onLog("Bridge exited with code " + code);
            _process = null;
        });

        _process.on("error", function (err) {
            _onLog("Bridge error: " + err.message);
            _process = null;
        });
    }

    /**
     * Send a request to the Python bridge.
     * @param {string} action - The action name
     * @param {object} params - Additional parameters
     * @returns {Promise} Resolves with the response object
     */
    function sendRequest(action, params) {
        return new Promise(function (resolve, reject) {
            if (!_process || !_process.stdin.writable) {
                reject(new Error("Bridge not running"));
                return;
            }

            var request = Object.assign({ action: action }, params || {});
            _pendingResolve = resolve;

            try {
                _process.stdin.write(JSON.stringify(request) + "\n");
            } catch (e) {
                _pendingResolve = null;
                reject(e);
            }

            // Timeout after 30 seconds
            setTimeout(function () {
                if (_pendingResolve === resolve) {
                    _pendingResolve = null;
                    reject(new Error("Request timed out: " + action));
                }
            }, 30000);
        });
    }

    /**
     * Stop the Python subprocess.
     */
    function stop() {
        if (_process) {
            try {
                _process.stdin.write(JSON.stringify({ action: "quit" }) + "\n");
            } catch (e) {}
            setTimeout(function () {
                if (_process) {
                    _process.kill();
                    _process = null;
                }
            }, 2000);
        }
    }

    /**
     * Check if the bridge is running.
     */
    function isRunning() {
        return _process !== null;
    }

    return {
        start: start,
        sendRequest: sendRequest,
        stop: stop,
        isRunning: isRunning,
        findPython: findPython
    };
})();

// Node.js module export (no-op in CEP browser context)
if (typeof module !== "undefined" && module.exports) {
    module.exports = VitIPC;
}
