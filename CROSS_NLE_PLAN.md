# Vit Cross-NLE Refinement Plan (macOS first)

## Context

Vit's core Python code was built with DaVinci Resolve as the sole NLE. Now that `premiere_plugin/` exists, the shared core needs refinement so both NLEs work as first-class citizens. This plan is intentionally **macOS-first**: land the shared-core cleanup and a working Premiere install path on macOS without destabilizing existing Resolve workflows, then adapt the installer and bootstrap details for Windows in a follow-up.

**Already NLE-agnostic (no changes needed):** `ai_merge.py`, `validator.py`, `differ.py`, `json_writer.py`, `merge_utils.py`, `models.py`

**Needs changes in this phase:** `core.py`, `cli.py`, `install.sh`, `premiere_bridge.py`, `CLAUDE.md`

**Explicitly deferred to a later phase:** Windows installer/registry work, Windows Premiere bootstrap behavior, and packaging/distribution cleanup beyond the existing source-tree / `~/.vit/vit-src` install path.

---

## Change 1: `vit/core.py` — NLE-aware init and universal gitignore

### 1a. Make gitignore cover both NLEs (line 53)

Add `*.prproj` and `*.prpref` alongside existing `*.drp`. This is purely additive — a Resolve user will never have `.prproj` files, so the extra patterns are harmless.

```
# NLE project files (managed by the NLE, not vit)
*.drp
*.prproj
*.prpref
```

### 1b. Add `nle` parameter to `git_init()` (line 66)

```python
def git_init(project_dir: str, nle: str = "resolve") -> None:
```

Change line 76: `config = {"version": "0.1.0", "nle": nle}`

Default `"resolve"` preserves all existing callers (tests, CLI, Resolve plugin).

### 1c. Add `nle` parameter to `git_clone()` (line 279)

```python
def git_clone(url: str, dest_dir: str, nle: str = "resolve") -> None:
```

Change line 296 to use the parameter. Only fires when cloned repo has no config (edge case — config should always exist in a properly initialized repo).

### 1d. Add `read_nle()` helper (new function near `find_project_root()`)

```python
def read_nle(project_dir: str) -> str:
    """Read the NLE type from .vit/config.json. Returns 'resolve' as default."""
    config_path = os.path.join(project_dir, ".vit", "config.json")
    try:
        with open(config_path) as f:
            return json.load(f).get("nle", "resolve")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return "resolve"
```

---

## Change 2: `vit/cli.py` — macOS Premiere install commands + NLE-agnostic messages

### 2a. Add `--nle` flag to `init` command

```python
p_init.add_argument("--nle", choices=["resolve", "premiere"], default="resolve",
                     help="Target NLE (default: resolve)")
```

Pass through in `cmd_init()`: `git_init(project_dir, nle=args.nle)`

### 2b. Add macOS Premiere CEP path and `cmd_install_premiere()` (new, after `cmd_install_resolve`)

```python
if sys.platform == "darwin":
    PREMIERE_CEP_DIR = os.path.expanduser("~/Library/Application Support/Adobe/CEP/extensions")
else:
    PREMIERE_CEP_DIR = ""

PREMIERE_EXTENSION_ID = "com.vit.premiere"
```

**`cmd_install_premiere()` — key differences from Resolve installer:**

Unlike Resolve (which symlinks individual `.py` scripts), CEP extensions are loaded as entire directories. The installer must:

1. **Find `premiere_plugin/` directory** — same two-location fallback as Resolve:
   - `../../premiere_plugin` relative to `cli.py`
   - `~/.vit/vit-src/premiere_plugin` (curl installer location)

2. **Fail fast outside macOS** for this phase:
   ```python
   if sys.platform != "darwin":
       print("  Premiere install is currently supported on macOS only.")
       sys.exit(1)
   ```

3. **Symlink the entire directory** into the CEP extensions folder:
   ```
   ~/Library/Application Support/Adobe/CEP/extensions/com.vit.premiere → /path/to/premiere_plugin/
   ```

4. **Enable PlayerDebugMode** (required for unsigned extensions to load):
   ```python
   if sys.platform == "darwin":
       import subprocess
       for version in range(9, 12):  # CSXS 9, 10, 11
           subprocess.run(
               ["defaults", "write", f"com.adobe.CSXS.{version}", "PlayerDebugMode", "1"],
               capture_output=True,
           )
   ```

5. **Save `package_path`** to `~/.vit/package_path` (same as Resolve installer). This preserves the existing source-tree assumptions used by the symlinked plugin layout on macOS.

**`cmd_uninstall_premiere()`:** Remove the symlink at `PREMIERE_CEP_DIR/com.vit.premiere`. If called outside macOS, print that Premiere uninstall is not yet supported there.

### 2c. Register new subcommands (after `uninstall-resolve`)

```python
p_install_pr = subparsers.add_parser("install-premiere", help="Install Vit extension for Adobe Premiere Pro")
p_install_pr.set_defaults(func=cmd_install_premiere)

p_uninstall_pr = subparsers.add_parser("uninstall-premiere", help="Remove Vit extension from Adobe Premiere Pro")
p_uninstall_pr.set_defaults(func=cmd_uninstall_premiere)
```

### 2d. Make user messages NLE-agnostic

- Line 565 (`cmd_clone`): `"Open the project in Resolve and relink"` → `"Open the project in your NLE and relink"`
- Line 642 (`cmd_collab_setup`): `"Open the project folder in DaVinci Resolve"` → `"Open the project folder in your NLE (Resolve or Premiere)"`

### 2e. Add `read_nle` to imports from core

---

## Change 3: `install.sh` — Add Premiere install + NLE-aware next steps

After the existing Resolve install block (line 96-107), add:

```bash
echo "  Installing Adobe Premiere Pro extension..."
"$VIT_BIN/vit" install-premiere 2>/dev/null || true
```

`|| true` makes Premiere failure non-fatal (most users only have one NLE).

Update "Next steps" (lines 111-124) to mention both NLEs:

```bash
echo "  Next steps:"
echo "    1. Restart your terminal (or run: source ~/.zshrc)"
echo "    2. Create and open your project in DaVinci Resolve or Adobe Premiere Pro"
echo "    3. Run: vit init your-project-name"
echo "       For Premiere projects, add: vit init --nle premiere your-project-name"
echo "    4. Run: vit collab setup"
echo "       (connect to a GitHub repo so your team can share the project)"
echo "    5. In Resolve:  Workspace > Scripts > Vit"
echo "       In Premiere: Window > Extensions > Vit"
echo "    6. The panel handles everything from there (save, branch, merge, push, pull)"
```

---

## Deferred: `install.ps1` and packaging

This phase does **not** modify `install.ps1` or add `MANIFEST.in`.

- **Windows installer work is deferred.** The Premiere CEP install path on Windows needs a different strategy (directory copy, registry changes, and bridge bootstrap validation) and should be handled as a dedicated follow-up.
- **Packaging cleanup is deferred.** The current macOS plan relies on the existing source-tree install model (`repo checkout` or `~/.vit/vit-src`) that `cmd_install_resolve()` already uses as a fallback. Making top-level plugin assets consistently available from sdists/wheels is worthwhile, but it is orthogonal to landing the shared-core and macOS CLI changes safely.

---

## Change 4: `premiere_plugin/premiere_bridge.py` — Simplify init handler

The `init` action currently does a post-hoc config patch (7 lines). With Change 1, simplify to:

```python
elif action == "init":
    from vit.core import git_init
    git_init(project_dir, nle="premiere")
    return {"ok": True}
```

---

## Change 5: `CLAUDE.md` — Reflect dual-NLE support

### 5a. System Architecture

Replace:
```
Resolve Panel (primary)  → vit-core (Python) → Git (system binary)
CLI (`vit` command)      → vit-core (Python) → Git (system binary)  [power users / fallback]
```

With:
```
Resolve Panel   → vit-core (Python) → Git (system binary)
Premiere Panel  → vit-core (Python) → Git (system binary)
CLI (`vit`)     → vit-core (Python) → Git (system binary)  [power users / fallback]
```

Add Premiere bullet to the interface list:
```
- **Premiere interface:** CEP extension (`premiere_plugin/`), accessed via Window > Extensions > Vit.
  Node.js spawns `premiere_bridge.py` as subprocess; ExtendScript handles serialize/deserialize.
```

### 5b. Repository Structure

Add `premiere_plugin/` alongside `resolve_plugin/`:
```
├── resolve_plugin/  # vit_panel.py — PySide6 panel for Resolve
├── premiere_plugin/ # CEP extension — ExtendScript + Node.js + Python bridge
```

### 5c. Scope Boundaries

Move "other NLEs" from out-of-scope to in-scope:
- **In scope:** Add "Adobe Premiere Pro CEP extension (serialize/deserialize via ExtendScript, git ops via premiere_bridge.py)"
- **Out of scope:** Change "other NLEs (fallback only)" → "NLEs beyond Resolve and Premiere, plus Windows-specific Premiere installation/bootstrap work"

### 5d. Resolve Plugin Scripts section

Rename to "NLE Plugins" or similar. Add a Premiere subsection explaining the CEP architecture (Node.js IPC, ExtendScript serialization, no direct Python serialize/deserialize).

---

## Implementation Order

1. **`core.py`** (Change 1) — foundation, all other changes depend on this
2. **`cli.py`** (Change 2) — depends on Change 1 (`git_init` signature, `read_nle`)
3. **`premiere_bridge.py`** (Change 4) — depends on Change 1
4. **`install.sh`** (Change 3) — depends on Change 2 (`install-premiere` must exist)
5. **`CLAUDE.md`** (Change 5) — independent, can parallel with any step
6. **Tests** — run existing suite after each change, add new tests at end

---

## Files Modified

| File | Type of Change |
|------|---------------|
| `vit/core.py` | Add `nle` param to `git_init`/`git_clone`, add `read_nle()`, expand gitignore |
| `vit/cli.py` | Add macOS-only `install-premiere`/`uninstall-premiere`, `--nle` flag, NLE-agnostic messages |
| `install.sh` | Add Premiere install step, update next-steps text |
| `premiere_plugin/premiere_bridge.py` | Simplify init handler (remove 7-line workaround) |
| `CLAUDE.md` | Update architecture, repo structure, scope boundaries for dual-NLE |

## Files NOT Modified

- `resolve_plugin/*` — zero changes
- `install.ps1` — Windows follow-up
- `setup.py` — packaging/distribution cleanup deferred
- `MANIFEST.in` — packaging/distribution cleanup deferred
- `vit/models.py`, `vit/serializer.py`, `vit/deserializer.py` — NLE-specific by design, untouched
- `vit/ai_merge.py`, `vit/validator.py`, `vit/differ.py`, `vit/json_writer.py` — already NLE-agnostic
- most `tests/*` — existing tests pass unchanged (default `nle="resolve"`); add targeted core/CLI coverage only where behavior changed

---

## New Tests

```python
# test_core.py additions
def test_init_with_nle_premiere():
    git_init(tmpdir, nle="premiere")
    config = json.load(open(os.path.join(tmpdir, ".vit", "config.json")))
    assert config["nle"] == "premiere"

def test_init_default_nle_is_resolve():
    git_init(tmpdir)
    config = json.load(open(os.path.join(tmpdir, ".vit", "config.json")))
    assert config["nle"] == "resolve"

def test_read_nle_returns_config_value(project_dir):
    assert read_nle(project_dir) == "resolve"

def test_read_nle_missing_config_defaults():
    assert read_nle(empty_dir) == "resolve"

def test_gitignore_contains_both_nle_patterns():
    git_init(tmpdir)
    gitignore = open(os.path.join(tmpdir, ".gitignore")).read()
    assert "*.drp" in gitignore
    assert "*.prproj" in gitignore
    assert "*.prpref" in gitignore

# test_cli.py additions
def test_install_premiere_rejects_non_macos(...):
    ...

def test_install_premiere_uses_repo_or_vit_src_plugin_dir_on_macos(...):
    ...
```

---

## Verification

1. `python -m pytest tests/` — all existing tests pass (zero regression)
2. `vit init --nle premiere /tmp/test-pr` — config shows `"nle": "premiere"`
3. `vit init /tmp/test-resolve` — config shows `"nle": "resolve"` (default)
4. `vit install-premiere` on macOS — symlink created in `~/Library/Application Support/Adobe/CEP/extensions/` as `com.vit.premiere`
5. `defaults read com.adobe.CSXS.9 PlayerDebugMode` (and 10/11) returns `1`
6. `readlink ~/Library/Application\ Support/Adobe/CEP/extensions/com.vit.premiere` points at the source-tree `premiere_plugin/` directory
7. Bridge test from the symlinked extension tree: `echo '{"action":"init"}' | python -u ~/Library/Application\\ Support/Adobe/CEP/extensions/com.vit.premiere/premiere_bridge.py --project-dir /tmp/test` — config shows `"nle": "premiere"` without post-hoc patch
8. `vit install-resolve` — unchanged behavior
9. CLAUDE.md reflects both NLEs in architecture, scope, and repo structure

## Follow-up Phase (Windows + packaging)

After the macOS rollout is stable:

1. Add Windows Premiere install/uninstall support in `vit/cli.py`
2. Validate bridge bootstrap when the CEP extension directory is copied instead of symlinked
3. Add Windows PlayerDebugMode registry writes
4. Decide whether packaging should support plugin assets from sdists/wheels, then update `setup.py` / `MANIFEST.in` accordingly
