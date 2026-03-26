/**
 * graph.js — Canvas-based commit graph rendering.
 *
 * Ported from the Qt panel's CommitGraphWidget. Renders a git-log-style
 * graph with branch lines and commit nodes onto an HTML <canvas>.
 */

var CommitGraph = (function () {

    // Layout constants (matching Qt panel)
    var ROW_HEIGHT = 42;
    var LANE_WIDTH = 30;
    var FIRST_LANE_X = 15;
    var NODE_SIZE = 10;

    // Colors
    var BRANCH_COLORS = {
        0: "#F24E1E",   // Red
        1: "#00C851",   // Green
        2: "#1ABCFE",   // Blue
        3: "#E07603"    // Orange (main)
    };

    var NODE_COLOR = "#FFBA6B";
    var NODE_OPACITY = 0.86;
    var LINE_OPACITY = 0.25;
    var TEXT_COLOR = "#4A4A4A";
    var PILL_BG = "#FFB463";
    var PILL_TEXT = "#000000";

    /**
     * Assign lanes to commits using a standard git-graph algorithm.
     *
     * @param {Array} commits - Array of commit objects with hash, parents, is_main_commit
     * @returns {Object} Map of commit hash -> lane index
     */
    function assignLanes(commits) {
        var lanes = {}; // hash -> lane index
        var activeLanes = []; // array of expected hash per lane (null = free)

        for (var i = 0; i < commits.length; i++) {
            var commit = commits[i];
            var hash = commit.hash;

            // Find which lane this commit should go in
            var myLane = -1;
            for (var l = 0; l < activeLanes.length; l++) {
                if (activeLanes[l] === hash) {
                    myLane = l;
                    break;
                }
            }

            if (myLane === -1) {
                // New lane needed — find first free or append
                var found = false;
                for (var f = 0; f < activeLanes.length; f++) {
                    if (activeLanes[f] === null) {
                        myLane = f;
                        activeLanes[f] = hash;
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    myLane = activeLanes.length;
                    activeLanes.push(hash);
                }
            }

            lanes[hash] = myLane;

            // Update active lanes: this lane now expects the first parent
            var parents = commit.parents || [];
            if (parents.length > 0) {
                activeLanes[myLane] = parents[0];
            } else {
                activeLanes[myLane] = null; // Root commit
            }

            // Additional parents get new lanes
            for (var p = 1; p < parents.length; p++) {
                var parentHash = parents[p];
                // Check if this parent already has a lane
                var parentLane = -1;
                for (var pl = 0; pl < activeLanes.length; pl++) {
                    if (activeLanes[pl] === parentHash) {
                        parentLane = pl;
                        break;
                    }
                }
                if (parentLane === -1) {
                    // Assign a new lane
                    var foundFree = false;
                    for (var ff = 0; ff < activeLanes.length; ff++) {
                        if (activeLanes[ff] === null) {
                            activeLanes[ff] = parentHash;
                            foundFree = true;
                            break;
                        }
                    }
                    if (!foundFree) {
                        activeLanes.push(parentHash);
                    }
                }
            }
        }

        return lanes;
    }

    /**
     * Render the commit graph onto a canvas.
     *
     * @param {HTMLCanvasElement} canvas
     * @param {Array} commits - Commit objects from get_commit_graph
     * @param {Object} branchColors - branch name -> color index
     * @param {string} headHash - Current HEAD hash
     */
    function render(canvas, commits, branchColors, headHash) {
        if (!commits || commits.length === 0) return;

        var dpr = window.devicePixelRatio || 1;
        var lanes = assignLanes(commits);

        // Calculate max lane for canvas width
        var maxLane = 0;
        for (var h in lanes) {
            if (lanes[h] > maxLane) maxLane = lanes[h];
        }

        var graphWidth = FIRST_LANE_X + (maxLane + 1) * LANE_WIDTH + 20;
        var textOffsetX = graphWidth;
        var totalWidth = canvas.parentElement ? canvas.parentElement.clientWidth : 320;
        var totalHeight = commits.length * ROW_HEIGHT;

        canvas.width = totalWidth * dpr;
        canvas.height = totalHeight * dpr;
        canvas.style.width = totalWidth + "px";
        canvas.style.height = totalHeight + "px";

        var ctx = canvas.getContext("2d");
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, totalWidth, totalHeight);

        // Build hash -> row index map
        var hashToRow = {};
        for (var i = 0; i < commits.length; i++) {
            hashToRow[commits[i].hash] = i;
        }

        // --- Draw connections ---
        for (var ci = 0; ci < commits.length; ci++) {
            var commit = commits[ci];
            var myLane = lanes[commit.hash] || 0;
            var myX = FIRST_LANE_X + myLane * LANE_WIDTH;
            var myY = ci * ROW_HEIGHT + ROW_HEIGHT / 2;

            var parents = commit.parents || [];
            for (var pi = 0; pi < parents.length; pi++) {
                var parentHash = parents[pi];
                var parentRow = hashToRow[parentHash];
                if (parentRow === undefined) continue;

                var parentLane = lanes[parentHash] || 0;
                var parentX = FIRST_LANE_X + parentLane * LANE_WIDTH;
                var parentY = parentRow * ROW_HEIGHT + ROW_HEIGHT / 2;

                // Get branch color for line
                var branchName = commit.branch || "main";
                var colorIdx = branchColors[branchName];
                if (colorIdx === undefined) colorIdx = 3;
                var lineColor = BRANCH_COLORS[colorIdx] || BRANCH_COLORS[3];

                ctx.save();
                ctx.strokeStyle = lineColor;
                ctx.globalAlpha = (myLane === 0 && parentLane === 0) ? NODE_OPACITY : LINE_OPACITY;
                ctx.lineWidth = (myLane === 0 && parentLane === 0) ? 2 : 1;

                if (myLane !== 0 || parentLane !== 0) {
                    ctx.setLineDash([2, 2]);
                }

                ctx.beginPath();
                if (myLane === parentLane) {
                    // Straight line
                    ctx.moveTo(myX, myY);
                    ctx.lineTo(parentX, parentY);
                } else {
                    // Curved connection
                    var midY = myY + (parentY - myY) * 0.5;
                    ctx.moveTo(myX, myY);
                    ctx.bezierCurveTo(myX, midY, parentX, midY, parentX, parentY);
                }
                ctx.stroke();
                ctx.restore();
            }
        }

        // --- Draw nodes ---
        for (var ni = 0; ni < commits.length; ni++) {
            var nodeCommit = commits[ni];
            var nodeLane = lanes[nodeCommit.hash] || 0;
            var nodeX = FIRST_LANE_X + nodeLane * LANE_WIDTH;
            var nodeY = ni * ROW_HEIGHT + ROW_HEIGHT / 2;
            var isHead = nodeCommit.is_head || nodeCommit.hash === headHash;

            // Node circle
            ctx.save();
            ctx.fillStyle = NODE_COLOR;
            ctx.globalAlpha = NODE_OPACITY;

            if (isHead) {
                // Ring node (outline only)
                ctx.beginPath();
                ctx.arc(nodeX, nodeY, NODE_SIZE / 2, 0, Math.PI * 2);
                ctx.fill();
                // Inner cutout
                ctx.globalCompositeOperation = "destination-out";
                ctx.beginPath();
                ctx.arc(nodeX, nodeY, NODE_SIZE / 2 - 2, 0, Math.PI * 2);
                ctx.fill();
                ctx.globalCompositeOperation = "source-over";
            } else {
                // Filled circle
                ctx.beginPath();
                ctx.arc(nodeX, nodeY, NODE_SIZE / 2, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.restore();

            // --- Draw text ---
            var textX = textOffsetX;
            ctx.save();

            // Branch pill for HEAD
            if (isHead && nodeCommit.branch) {
                ctx.font = "bold 10px 'SF Pro Display', 'Segoe UI', sans-serif";
                var pillText = nodeCommit.branch;
                var pillWidth = ctx.measureText(pillText).width + 12;
                var pillHeight = 16;
                var pillY = nodeY - pillHeight / 2;

                ctx.fillStyle = PILL_BG;
                ctx.globalAlpha = 1;
                roundRect(ctx, textX, pillY, pillWidth, pillHeight, 3);
                ctx.fill();

                ctx.fillStyle = PILL_TEXT;
                ctx.fillText(pillText, textX + 6, nodeY + 4);
                textX += pillWidth + 8;
            }

            // Commit message
            ctx.font = "11px 'SF Pro Display', 'Segoe UI', sans-serif";
            ctx.fillStyle = TEXT_COLOR;
            ctx.globalAlpha = 1;

            var maxTextWidth = totalWidth - textX - 10;
            var message = nodeCommit.message || "";
            if (ctx.measureText(message).width > maxTextWidth) {
                while (message.length > 3 && ctx.measureText(message + "...").width > maxTextWidth) {
                    message = message.substring(0, message.length - 1);
                }
                message += "...";
            }
            ctx.fillText(message, textX, nodeY + 4);

            ctx.restore();
        }
    }

    /**
     * Draw a rounded rectangle path.
     */
    function roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.arcTo(x + w, y, x + w, y + r, r);
        ctx.lineTo(x + w, y + h - r);
        ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
        ctx.lineTo(x + r, y + h);
        ctx.arcTo(x, y + h, x, y + h - r, r);
        ctx.lineTo(x, y + r);
        ctx.arcTo(x, y, x + r, y, r);
        ctx.closePath();
    }

    return {
        render: render,
        ROW_HEIGHT: ROW_HEIGHT
    };
})();
