/**
 * main.js — Panel logic, UI events, and CSInterface bridge.
 *
 * This is the main entry point for the CEP panel. It:
 *   1. Sets up CSInterface for ExtendScript communication
 *   2. Starts the Python IPC bridge
 *   3. Handles all UI events and orchestrates the serialize->write->commit flow
 */

/* global CSInterface, SystemPath, VitIPC, FileWriter, CommitGraph */

(function () {
    "use strict";

    var csInterface = new CSInterface();
    var projectDir = "";

    // --- Initialization ---

    function init() {
        log("Vit panel loading...");

        // Load ExtendScript files
        // host_utils.jsx is auto-loaded via manifest ScriptPath;
        // serializer + deserializer must be loaded explicitly.
        var extPath = csInterface.getSystemPath(SystemPath.EXTENSION);
        // Replace backslashes with forward slashes for ExtendScript compatibility
        var jsxPath = extPath.replace(/\\/g, "/");
        evalScript('$.evalFile("' + jsxPath + '/jsx/serializer.jsx")');
        evalScript('$.evalFile("' + jsxPath + '/jsx/deserializer.jsx")');

        // Determine project directory
        // Use the Premiere project file location as the base
        evalScript("app.project.path", function (projectPath) {
            if (projectPath && projectPath !== "undefined" && projectPath !== "") {
                var path = require("path");
                var fs = require("fs");

                // Project dir is the directory containing the .prproj file
                var dir = path.dirname(projectPath);

                // Look for existing .vit directory
                var current = dir;
                while (current) {
                    if (fs.existsSync(path.join(current, ".vit"))) {
                        projectDir = current;
                        break;
                    }
                    var parent = path.dirname(current);
                    if (parent === current) break;
                    current = parent;
                }

                if (!projectDir) {
                    // Default to project file directory
                    projectDir = dir;
                }

                log("Project dir: " + projectDir);
                startBridge();
            } else {
                log("No project open. Save your project first.");
                setStatus("Save your Premiere project first, then reopen this panel.");
            }
        });

        // Bind UI events
        bindEvents();
    }

    // --- CSInterface helpers ---

    function evalScript(script, callback) {
        csInterface.evalScript(script, callback || function () {});
    }

    // --- Python bridge ---

    function startBridge() {
        VitIPC.start(projectDir, function (msg) {
            log(msg);
        });

        // Ping to verify connection
        setTimeout(function () {
            VitIPC.sendRequest("ping").then(function (resp) {
                if (resp.ok) {
                    log("Bridge connected.");
                    refreshBranch();
                    refreshChanges();
                }
            }).catch(function (err) {
                log("Bridge ping failed: " + err.message);
                // May need to init the project first
                checkOrInitProject();
            });
        }, 1000);
    }

    function checkOrInitProject() {
        var fs = require("fs");
        var vitDir = require("path").join(projectDir, ".vit");
        if (!fs.existsSync(vitDir)) {
            log("No vit project found. Initializing...");
            VitIPC.sendRequest("init").then(function (resp) {
                if (resp.ok) {
                    log("Initialized vit project.");
                    setStatus("Initialized new vit project.");
                    refreshBranch();
                } else {
                    setStatus("Init failed: " + (resp.error || "unknown"));
                }
            }).catch(function (err) {
                setStatus("Init failed: " + err.message);
            });
        }
    }

    // --- UI state ---

    function setStatus(text) {
        var el = document.getElementById("status-text");
        if (el) el.textContent = text;
    }

    function setBranch(name) {
        var el = document.getElementById("branch-label");
        if (el) el.textContent = name;
    }

    function log(msg) {
        console.log("[vit] " + msg);
        var logEl = document.getElementById("log-area");
        if (logEl) {
            logEl.textContent += msg + "\n";
            logEl.scrollTop = logEl.scrollHeight;
        }
    }

    function setLoading(loading) {
        var btns = document.querySelectorAll("button");
        for (var i = 0; i < btns.length; i++) {
            btns[i].disabled = loading;
        }
    }

    // --- Actions ---

    function refreshBranch() {
        VitIPC.sendRequest("get_branch").then(function (resp) {
            if (resp.ok) {
                setBranch(resp.branch);
            }
        }).catch(function () {});

        // Also refresh branch dropdowns
        VitIPC.sendRequest("list_branches").then(function (resp) {
            if (resp.ok) {
                populateBranchDropdowns(resp.branches, resp.current);
            }
        }).catch(function () {});
    }

    function populateBranchDropdowns(branches, current) {
        var switchSelect = document.getElementById("switch-branch-select");
        var mergeSelect = document.getElementById("merge-branch-select");

        [switchSelect, mergeSelect].forEach(function (select) {
            if (!select) return;
            select.innerHTML = "";
            branches.forEach(function (b) {
                var opt = document.createElement("option");
                opt.value = b;
                opt.textContent = b;
                if (b === current) opt.selected = true;
                select.appendChild(opt);
            });
        });
    }

    function refreshChanges() {
        // Serialize current state, then ask bridge for changes
        setStatus("Checking changes...");

        evalScript("serializeTimeline()", function (result) {
            if (!result || result === "undefined" || result === "EvalScript error.") {
                setStatus("No active sequence.");
                return;
            }

            try {
                var data = JSON.parse(result);

                // Write domain files via Node.js
                FileWriter.writeAll(projectDir, data);

                // Get changes from bridge
                VitIPC.sendRequest("get_changes").then(function (resp) {
                    if (resp.ok) {
                        displayChanges(resp.changes);
                        setStatus("");
                    }
                }).catch(function () {
                    setStatus("");
                });
            } catch (e) {
                log("Serialize error: " + e.message);
                setStatus("Serialize error.");
            }
        });
    }

    function displayChanges(changes) {
        var listEl = document.getElementById("changes-list");
        if (!listEl) return;
        listEl.innerHTML = "";

        var categories = ["video", "audio", "color"];
        var icons = {
            video: "&#9654;",  // play triangle
            audio: "&#9834;",  // music note
            color: "&#9673;"   // circle
        };
        var hasChanges = false;

        categories.forEach(function (cat) {
            var items = changes[cat] || [];
            items.forEach(function (item) {
                hasChanges = true;
                var div = document.createElement("div");
                div.className = "change-item";
                div.innerHTML = '<span class="change-icon">' + icons[cat] + '</span>' +
                    '<span class="change-name">' + escapeHtml(item) + '</span>';
                listEl.appendChild(div);
            });
        });

        if (!hasChanges) {
            var empty = document.createElement("div");
            empty.className = "changes-empty";
            empty.textContent = "No changes";
            listEl.appendChild(empty);
        }
    }

    function saveVersion() {
        var msgInput = document.getElementById("commit-message");
        var message = msgInput ? msgInput.value.trim() : "";
        if (!message) message = "save version";

        setLoading(true);
        setStatus("Serializing...");

        evalScript("serializeTimeline()", function (result) {
            if (!result || result === "undefined" || result === "EvalScript error.") {
                setStatus("No active sequence.");
                setLoading(false);
                return;
            }

            try {
                var data = JSON.parse(result);
                setStatus("Writing files...");
                FileWriter.writeAll(projectDir, data);

                setStatus("Committing...");
                VitIPC.sendRequest("save", { message: message }).then(function (resp) {
                    setLoading(false);
                    if (resp.ok) {
                        var statusMsg = resp.hash
                            ? "Committed: " + resp.hash + " — " + resp.message
                            : resp.message || "Saved.";
                        setStatus(statusMsg);
                        if (msgInput) msgInput.value = "";
                        refreshChanges();
                        refreshHistory();
                    } else {
                        setStatus("Error: " + (resp.error || "unknown"));
                    }
                }).catch(function (err) {
                    setLoading(false);
                    setStatus("Error: " + err.message);
                });
            } catch (e) {
                setLoading(false);
                setStatus("Serialize error: " + e.message);
            }
        });
    }

    function createBranch() {
        var input = document.getElementById("new-branch-input");
        var name = input ? input.value.trim() : "";
        if (!name) {
            setStatus("Enter a branch name.");
            return;
        }

        setLoading(true);
        VitIPC.sendRequest("new_branch", { name: name }).then(function (resp) {
            setLoading(false);
            if (resp.ok) {
                setStatus("Created branch: " + resp.branch);
                if (input) input.value = "";
                refreshBranch();
            } else {
                setStatus("Error: " + (resp.error || "unknown"));
            }
        }).catch(function (err) {
            setLoading(false);
            setStatus("Error: " + err.message);
        });
    }

    function switchBranch() {
        var select = document.getElementById("switch-branch-select");
        var target = select ? select.value : "";
        if (!target) return;

        setLoading(true);
        setStatus("Switching to " + target + "...");

        VitIPC.sendRequest("switch_branch", { branch: target }).then(function (resp) {
            if (resp.ok) {
                setBranch(resp.branch);
                setStatus("Switched to: " + resp.branch + ". Restoring timeline...");

                // Read the domain files and deserialize into Premiere
                var data = FileWriter.readAll(projectDir);
                var jsonStr = JSON.stringify(data);
                evalScript('deserializeTimeline(' + quote(jsonStr) + ')', function (result) {
                    setLoading(false);
                    try {
                        var r = JSON.parse(result);
                        if (r.ok) {
                            setStatus("Restored timeline from: " + resp.branch);
                        } else {
                            setStatus("Restore warning: " + (r.error || "partial"));
                        }
                    } catch (e) {
                        setStatus("Switched to: " + resp.branch);
                    }
                    refreshChanges();
                    refreshHistory();
                });
            } else {
                setLoading(false);
                setStatus("Error: " + (resp.error || "unknown"));
            }
        }).catch(function (err) {
            setLoading(false);
            setStatus("Error: " + err.message);
        });
    }

    function mergeBranch() {
        var select = document.getElementById("merge-branch-select");
        var target = select ? select.value : "";
        if (!target) return;

        setLoading(true);
        setStatus("Merging " + target + "...");

        // Serialize first (auto-save if dirty)
        evalScript("serializeTimeline()", function (result) {
            if (result && result !== "undefined" && result !== "EvalScript error.") {
                try {
                    var data = JSON.parse(result);
                    FileWriter.writeAll(projectDir, data);
                } catch (e) {}
            }

            VitIPC.sendRequest("merge", { branch: target }).then(function (resp) {
                if (resp.ok) {
                    var msg = "Merged " + resp.branch + " into " + resp.current;
                    if (resp.issues) msg += "\nIssues:\n" + resp.issues;
                    setStatus(msg);

                    // Deserialize merged state
                    var mergedData = FileWriter.readAll(projectDir);
                    var jsonStr = JSON.stringify(mergedData);
                    evalScript('deserializeTimeline(' + quote(jsonStr) + ')', function () {
                        setLoading(false);
                        refreshBranch();
                        refreshChanges();
                        refreshHistory();
                    });
                } else {
                    setLoading(false);
                    setStatus("Merge failed: " + (resp.error || "unknown"));
                }
            }).catch(function (err) {
                setLoading(false);
                setStatus("Merge error: " + err.message);
            });
        });
    }

    function pushChanges() {
        setLoading(true);
        setStatus("Pushing...");
        VitIPC.sendRequest("push").then(function (resp) {
            setLoading(false);
            if (resp.ok) {
                setStatus("Pushed " + resp.branch + ". " + (resp.output || ""));
            } else {
                setStatus("Push failed: " + (resp.error || "unknown"));
            }
        }).catch(function (err) {
            setLoading(false);
            setStatus("Push error: " + err.message);
        });
    }

    function pullChanges() {
        setLoading(true);
        setStatus("Pulling...");
        VitIPC.sendRequest("pull").then(function (resp) {
            if (resp.ok) {
                setStatus("Pulled " + resp.branch + ". Restoring...");

                var data = FileWriter.readAll(projectDir);
                var jsonStr = JSON.stringify(data);
                evalScript('deserializeTimeline(' + quote(jsonStr) + ')', function () {
                    setLoading(false);
                    setStatus("Pulled and restored: " + resp.branch);
                    refreshChanges();
                    refreshHistory();
                });
            } else {
                setLoading(false);
                setStatus("Pull failed: " + (resp.error || "unknown"));
            }
        }).catch(function (err) {
            setLoading(false);
            setStatus("Pull error: " + err.message);
        });
    }

    function showStatus() {
        VitIPC.sendRequest("status").then(function (resp) {
            if (resp.ok) {
                setStatus(resp.branch + ": " + resp.status);
                log("Branch: " + resp.branch + "\n" + resp.status + "\n" + resp.log);
            } else {
                setStatus("Status error: " + (resp.error || "unknown"));
            }
        }).catch(function (err) {
            setStatus("Status error: " + err.message);
        });
    }

    function refreshHistory() {
        VitIPC.sendRequest("get_commit_graph", { limit: 30 }).then(function (resp) {
            if (resp.ok) {
                var canvas = document.getElementById("graph-canvas");
                if (canvas) {
                    CommitGraph.render(canvas, resp.commits, resp.branch_colors, resp.head);
                }
            }
        }).catch(function () {});
    }

    // --- Collapsible sections ---

    function toggleSection(sectionId) {
        var content = document.getElementById(sectionId + "-content");
        var chevron = document.getElementById(sectionId + "-chevron");
        if (!content) return;

        var isHidden = content.style.display === "none";
        content.style.display = isHidden ? "block" : "none";
        if (chevron) {
            chevron.style.transform = isHidden ? "rotate(90deg)" : "rotate(0deg)";
        }
    }

    // --- Event binding ---

    function bindEvents() {
        // Commit
        on("commit-btn", "click", saveVersion);
        on("refresh-btn", "click", refreshChanges);

        // Branches
        on("create-branch-btn", "click", createBranch);
        on("switch-branch-btn", "click", switchBranch);
        on("merge-branch-btn", "click", mergeBranch);

        // Push/Pull/Status
        on("push-btn", "click", pushChanges);
        on("pull-btn", "click", pullChanges);
        on("status-btn", "click", showStatus);

        // Collapsible sections
        on("actions-header", "click", function () { toggleSection("actions"); });
        on("changes-header", "click", function () { toggleSection("changes"); });
        on("history-header", "click", function () { toggleSection("history"); });

        // Enter key in commit message
        var msgInput = document.getElementById("commit-message");
        if (msgInput) {
            msgInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    saveVersion();
                }
            });
        }

        // Enter key in new branch input
        var branchInput = document.getElementById("new-branch-input");
        if (branchInput) {
            branchInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    createBranch();
                }
            });
        }
    }

    function on(id, event, handler) {
        var el = document.getElementById(id);
        if (el) el.addEventListener(event, handler);
    }

    // --- Helpers ---

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function quote(str) {
        return "'" + str.replace(/\\/g, "\\\\").replace(/'/g, "\\'") + "'";
    }

    // --- Panel lifecycle ---

    // Clean up on panel close
    csInterface.addEventListener("com.adobe.csxs.events.WindowVisibilityChanged", function (event) {
        if (event.data === "false") {
            VitIPC.stop();
        }
    });

    // Start
    init();

})();
