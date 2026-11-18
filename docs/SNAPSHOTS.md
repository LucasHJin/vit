# Audit Snapshots

`vit snapshot` records what a timeline looks like right now and commits it, from
outside Resolve. It exists so that an assistant (or a script, or a hook) that
changes a timeline leaves a readable record: what changed, in which domain, and
what was asked for.

It is a second way to use vit, next to the branch/merge workflow, and the two
don't share files.

|  | Branch/merge (`vit commit`, panel) | Audit (`vit snapshot`) |
|---|---|---|
| Runs from | The panel inside Resolve | Anywhere: CLI, agent, hook |
| Stores | One timeline in `timeline/` | Every timeline in `timelines/<key>/` |
| Clip IDs | Positional (`item_001_003`) | Resolve's unique item ID |
| Media refs | SHA-256 of file contents | Hash of the file path (reads nothing) |
| Colour | LUT + DRX per clip, every time | Metadata only; `--color` for the rest |
| Restores timelines | Yes (`checkout`, `merge`) | Never. Read-only |

## Requirements

- Resolve Studio running with a project open.
- Preferences > System > General > "External scripting using" set to **Local**.
- A vit project (`vit init`) to hold the history.
- A Python that Resolve's scripting library accepts. If the module isn't found
  in Blackmagic's default location, set `RESOLVE_SCRIPT_API` and
  `RESOLVE_SCRIPT_LIB`.

## Commands

```bash
# Snapshot the timeline that is open in Resolve
vit snapshot -m "RavenSeek built rough cut v1 from paper edit"

# A named timeline, without switching to it
vit snapshot -m "before trims" --timeline "Promo – rough cut v1"

# Attach what was asked for (a tool call, a script) and get JSON back
vit snapshot -m "tighten trims on V1" --journal call.json --json
echo '{"tool": "run_script", "script": "..."}' | vit snapshot -m "..." --journal -

# Full colour capture (switches to the Color page while it runs)
vit snapshot -m "after grade" --color

vit timelines                       # which timelines have snapshots
vit diff --timeline "Promo – rough cut v1"        # disk vs last snapshot
vit diff HEAD~3 --timeline "Promo – rough cut v1" # disk vs an older commit
```

`-C <dir>` or `$VIT_PROJECT_DIR` selects the vit project when the working
directory is somewhere else.

## Result

With `--json`:

```json
{
  "timeline": "Promo – rough cut v1",
  "key": "5f0c…",
  "commit": "a1b2c3d",
  "changed": true,
  "domains_changed": ["cuts", "markers"],
  "diff": "  CUTS:\n  ~ Trimmed 'Interview_A' end: …",
  "issues": [],
  "journal": "journal/20261118T172501Z-tighten-trims-on-v1.json"
}
```

- `domains_changed` is the scope check. A task that was only meant to change
  audio levels should come back as `["audio"]`.
- `commit` is `null` when nothing was committed. A journal entry is committed
  even if the timeline itself didn't change (`changed: false`), so a script
  that ran and did nothing is still on record.
- `issues` comes from the validator (overlapping clips, orphaned references).

A snapshot commits only its own files. Anything else staged in the repo is
left staged.

## The pattern for an assistant

1. `vit snapshot -m "before: <task>"`
2. Make the change (RavenSeek `make_timeline`, a Resolve `run_script`, …).
3. `vit snapshot -m "<what and why>" --journal <the call> --json`
4. Check `domains_changed` and `diff` against what was intended. If they don't
   match, stop and report.

## Layout

```
timelines/
  index.json              # key -> {name, project}
  <key>/
    timeline/             # cuts.json, color.json, audio.json, effects.json,
                          # markers.json, metadata.json, grades/
    assets/manifest.json  # media ref -> original_path, codec, …
journal/
  <UTC time>-<slug>.json  # {time, message, timeline, timeline_key, entry}
```

`<key>` is the timeline's unique ID in Resolve, so renaming a timeline keeps
its history. `manifest.json` keeps each source's `original_path`, which is the
join to any other tool that knows footage by path.

## What a snapshot does not see

The record is only as wide as the serializer. Not captured: effects and
transitions (`effects.json` is always empty), audio fades and EQ, keyframes,
speed ramps, clip markers (timeline markers are), Media Pool changes, project
settings, and renders. The journal covers intent for those; a snapshot can't
confirm the result.

This is a record, not a rollback. To be able to go back, duplicate the
timeline in Resolve (or export a `.drp`) before changing it.
