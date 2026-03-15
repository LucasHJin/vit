# Vit — Git for Video Editing

Vit brings git-style version control to video editing. Instead of versioning raw media files, Vit tracks **timeline metadata** — clip placements, color grades, audio levels, effects, and markers — as lightweight JSON, using Git as the backend.

Collaborators (editors, colorists, sound designers) work in parallel on branches and merge changes cleanly, just like developers with code.

## How It Works

Vit serializes your DaVinci Resolve timeline into **domain-split JSON files**:

| File | Contents | Typical Owner |
|------|----------|---------------|
| `cuts.json` | Clip placements, in/out points, transforms | Editor |
| `color.json` | Color grading per clip | Colorist |
| `audio.json` | Levels, panning | Sound Designer |
| `effects.json` | Effects, transitions | Editor / VFX |
| `markers.json` | Markers, notes | Anyone |
| `metadata.json` | Frame rate, resolution, track counts | Rarely changed |

Different roles edit different files, so Git merges them without conflicts. When cross-domain issues arise (e.g., a deleted clip still referenced in `color.json`), an AI-powered semantic merge resolves them.

## Installation

**Requirements:** Python 3.8+, Git, DaVinci Resolve (optional, for Resolve integration)

### One-Line Install (macOS/Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/LucasHJin/vit/main/install.sh | bash
```

### Manual Install

```bash
git clone https://github.com/LucasHJin/vit.git
cd vit
pip install .
vit install-resolve   # symlink plugin scripts into DaVinci Resolve
```

For the optional Qt-based GUI panel inside Resolve:

```bash
pip install ".[qt]"
```

## Quick Start

```bash
# Initialize a project
vit init

# Save a version
vit commit -m "rough cut done"

# Create a branch for color grading
vit branch color-grade
vit checkout color-grade

# Work in Resolve, then commit
vit commit -m "first color pass"

# Merge back
vit checkout main
vit merge color-grade

# View changes
vit diff
vit log

# Note that apart from the first command, all other commands can be run in the GUI in Davinci Resolve
```

## Commands

| Command | Description |
|---------|-------------|
| `vit init` | Initialize a new vit project |
| `vit add` | Serialize timeline and stage changes |
| `vit commit -m "msg"` | Stage + commit |
| `vit branch <name>` | Create a new branch |
| `vit checkout <name>` | Switch branches (restores timeline in Resolve) |
| `vit merge <branch>` | Merge a branch (with AI conflict resolution) |
| `vit diff` | Human-readable timeline diff |
| `vit log` | Formatted version history |
| `vit revert` | Undo the last commit |
| `vit push` / `vit pull` | Sync with a remote |
| `vit status` | Show project status |

## Project Structure

```
vit/                  # Core library
  cli.py              # CLI entry point
  core.py             # Git operations wrapper
  serializer.py       # Resolve timeline -> JSON
  deserializer.py     # JSON -> Resolve timeline
  ai_merge.py         # AI-powered conflict resolution (Gemini)
  differ.py           # Human-readable diff formatting
  validator.py        # Post-merge validation
  models.py           # Data models
  json_writer.py      # Domain-split JSON I/O

resolve_plugin/       # DaVinci Resolve integration scripts
  vit_panel_qt.py     # Qt GUI panel for Resolve
  vit_commit.py       # Script menu: commit
  vit_branch.py       # Script menu: branch
  vit_merge.py        # Script menu: merge
  vit_status.py       # Script menu: status
  vit_restore.py      # Script menu: restore timeline
  ...

tests/                # Test suite
```

## AI Features

Vit uses the **Gemini API** (`gemini-2.5-flash`) to assist with video editing workflows that go beyond what plain Git can handle. Key uses:

- **Semantic merge resolution** — When a merge creates cross-domain conflicts (e.g., one branch deletes a clip while another color-grades it), the AI analyzes BASE/OURS/THEIRS states across all domain files and produces structured per-domain decisions with confidence levels
- **Interactive conflict clarification** — For ambiguous merges (low-confidence decisions), the AI presents options to the user, then resolves the final JSON based on their choices
- **Post-merge validation** — A rule-based validator catches orphaned references, overlapping clips, audio/video sync mismatches, and speed/duration inconsistencies after every merge; these issues feed into the AI prompt for smarter resolution
- **Commit message suggestions** — `vit commit` can auto-generate a descriptive message from the timeline diff using video editing terminology (e.g., "Add B-roll on V2, trim interview end point")
- **Log summaries** — `vit log --summary` produces a natural-language overview of recent commits for the team
- **Branch comparison analysis** — The Resolve GUI panel uses AI to compare two branches and recommend a merge strategy before you commit to it
- **Commit classification** — Commits are auto-categorized as audio, video, or color changes (with a fast heuristic fallback when AI is unavailable)

Set `GEMINI_API_KEY` in your environment or project `.env` file to enable AI features. All AI features degrade gracefully — Vit works fully without an API key, you just lose the smart merge and suggestions.

## DaVinci Resolve Integration

After installation, Vit appears in Resolve under **Workspace > Scripts**. You can run commits, branching, and merging directly from the Resolve UI — either through individual script menu items or the unified Qt panel.

## Testing

```bash
python -m pytest tests/
```

## License

MIT
