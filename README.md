# Vit — Git for Video Editing

Vit brings git-style version control to video editing. Instead of versioning raw media files, Vit tracks **timeline metadata** as JSON and stores that history in Git.

Vit is built around the idea that editors, colorists, and sound designers should be able to work in parallel on branches, then merge edit decisions the same way software teams merge code.

## Current Build Status

This repo currently supports:

- `vit` CLI workflows on macOS
- DaVinci Resolve integration through `resolve_plugin/`
- Adobe Premiere Pro integration through `premiere_plugin/`
- macOS-first plugin install commands: `vit install-resolve` and `vit install-premiere`

Current constraints:

- plugin installers expect either a source checkout of this repo or the one-line installer layout in `~/.vit/vit-src`
- Premiere support is currently documented and wired as a macOS-first path
- collaboration docs in [`docs/COLLABORATION.md`](docs/COLLABORATION.md) are still Resolve-centric

## How Vit Works

Vit versions **edit decisions**, not media files.

Typical project output looks like this:

```text
my-video-project/
├── .git/
├── .vit/config.json
├── timeline/
│   ├── cuts.json
│   ├── color.json
│   ├── audio.json
│   ├── effects.json
│   ├── markers.json
│   └── metadata.json
└── assets/
```

These files are domain-split so different collaborators can often work without stepping on each other:

| File | Contents | Typical Owner |
|------|----------|---------------|
| `cuts.json` | Clip placements, in/out points, transforms, speed | Editor |
| `color.json` | Color grading per clip | Colorist |
| `audio.json` | Levels, panning | Sound Designer |
| `effects.json` | Effects, transitions | Editor / VFX |
| `markers.json` | Markers, notes | Anyone |
| `metadata.json` | Frame rate, resolution, track counts | Rarely changed |

When branches touch overlapping meaning across domains, Vit can run validation and optional AI-assisted merge flows.

## Requirements

- Python 3.8+
- Git
- macOS for the current installer flow
- DaVinci Resolve if you want the Resolve panel
- Adobe Premiere Pro if you want the Premiere extension

## Install Options

### One-line install

For the fastest setup on macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/LucasHJin/vit/main/install.sh | bash
```

That installer keeps a source checkout in `~/.vit/vit-src`, installs the Python package into `~/.vit/venv`, then attempts both plugin installs non-destructively.

### Source checkout install

If you are developing or modifying Vit itself, use an editable install from a local checkout:

```bash
git clone https://github.com/LucasHJin/vit.git
cd vit
pip install -e .
```

If you want to run tests locally:

```bash
pip install -e ".[dev]"
python -m pytest tests/
```

If you want the optional Qt Resolve panel dependencies:

```bash
pip install ".[qt]"
```

## DaVinci Resolve Install Guide

### Install from a source checkout

```bash
git clone https://github.com/LucasHJin/vit.git
cd vit
pip install -e .
vit install-resolve
```

What this does:

- locates `resolve_plugin/` from the repo checkout or `~/.vit/vit-src`
- symlinks the required scripts into Resolve's Scripts menu directory
- saves the repo path to `~/.vit/package_path` so Resolve-side Python can import `vit`

After install:

1. Restart DaVinci Resolve.
2. Open `Workspace > Scripts > Vit`.
3. Point the panel at your Vit project folder if prompted.

### Start a new Resolve-tracked project

```bash
vit init my-project
cd my-project
vit collab setup
```

Then open Resolve, open the Vit panel, and use **Save Version** to create the first serialized snapshot.

## Adobe Premiere Pro Install Guide

### Install from a source checkout

```bash
git clone https://github.com/LucasHJin/vit.git
cd vit
pip install -e .
vit install-premiere
```

What this does on macOS:

- locates `premiere_plugin/` from the repo checkout or `~/.vit/vit-src`
- symlinks the whole CEP extension into `~/Library/Application Support/Adobe/CEP/extensions/com.vit.premiere`
- enables `PlayerDebugMode` for CSXS 9/10/11
- saves the repo path to `~/.vit/package_path`

After install:

1. Restart Premiere Pro.
2. Open `Window > Extensions > Vit`.
3. Point the extension at your Vit project folder if prompted.

### Start a new Premiere-tracked project

```bash
vit init --nle premiere my-project
cd my-project
vit collab setup
```

The bridge will create `.vit/config.json` with `"nle": "premiere"` so the project is tagged correctly from the start.

## Collaboration Flow

Vit still expects Git to be the system of record for collaboration.

### Project owner

```bash
vit init my-project
cd my-project
vit collab setup
```

Then:

1. Open the project in your NLE.
2. Open the Vit panel/extension.
3. Save the first version.
4. Share the `vit clone ...` command printed by `vit collab setup`.

### Collaborators

```bash
vit clone https://github.com/yourname/your-repo.git
cd your-repo
vit checkout main
vit branch your-name
```

Then open the project in Resolve or Premiere, relink any offline media, and work from your own branch.

Resolve-specific collaboration steps are still documented in [`docs/COLLABORATION.md`](docs/COLLABORATION.md).

## CLI Quick Start

The CLI is the stable cross-NLE surface in this repo.

```bash
vit init                        # initialize a Resolve-tracked project
vit init --nle premiere promo   # initialize a Premiere-tracked project
vit commit -m "rough cut done"
vit branch color-grade
vit checkout color-grade
vit commit -m "first color pass"
vit checkout main
vit merge color-grade
vit diff
vit log
```

Available commands in the current build:

- `vit init`
- `vit add`
- `vit commit`
- `vit branch`
- `vit checkout`
- `vit merge`
- `vit diff`
- `vit log`
- `vit status`
- `vit revert`
- `vit push`
- `vit pull`
- `vit validate`
- `vit clone`
- `vit remote`
- `vit collab setup`
- `vit install-resolve`
- `vit uninstall-resolve`
- `vit install-premiere`
- `vit uninstall-premiere`

## Repository Layout

```text
vit/
├── vit/               # core library and CLI
├── resolve_plugin/    # DaVinci Resolve panel and script entry points
├── premiere_plugin/   # Premiere CEP extension + Python bridge
├── tests/             # test suite
└── docs/              # reference docs
```

Key directories:

- `vit/`: git wrappers, serializer/deserializer, merge logic, validation, diffing
- `resolve_plugin/`: Resolve launcher, panel UIs, and script-menu entry points
- `premiere_plugin/`: CEP HTML/JS assets, ExtendScript, and `premiere_bridge.py`

## AI Features

Vit uses the Gemini API for optional workflow assistance:

- semantic merge resolution for cross-domain conflicts
- commit message suggestions
- log summaries
- branch comparison analysis

Set `GEMINI_API_KEY` in your shell or project `.env` file to enable those features. The CLI and UI degrade to non-AI behavior when the key is missing or an optional AI step fails.

## Testing

```bash
pip install -e ".[dev]"
python -m pytest tests/
```

For a quick non-pytest syntax pass:

```bash
python -m compileall vit tests resolve_plugin premiere_plugin/premiere_bridge.py
```

## License

MIT
