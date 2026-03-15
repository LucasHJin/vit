# Graph Debug Reference — giteo-test-project

Cross-reference for fixing the commit graph display. Data captured from your test project.

---

## Your Branches (Local)

| Branch   | Points to commit | Message        |
|----------|-------------------|----------------|
| **Hi** (HEAD) | f9f17ae        | giteo: Saved   |
| New      | 1731698           | giteo: Hi      |
| Lebron   | 5669a84           | giteo: 1       |
| Tester   | 840fb18           | giteo: New     |
| master   | a7e77fa           | giteo: saved   |
| speed    | 99d40e2           | giteo: save 'Timeline 1' |

---

## Full Commit Chain (Parent → Child, Top = Most Recent)

```
INDEX   HASH      BRANCH*   MESSAGE
----    ------    ------    ------
 0      f9f17ae   Hi        giteo: Saved                    ← HEAD (current)
 1      fd47c17   Hi        giteo: removed clip
 2      38290b3   Hi        giteo: hello
 3      4284e62   Hi        giteo: hi
 4      1731698   New       giteo: Hi                       ← branch tip: New
 5      1834589   Hi        giteo: jhi
 6      5669a84   Lebron    giteo: 1                         ← branch tip: Lebron
 7      56f244f   Hi        giteo: save version
 8      840fb18   Tester    giteo: New                       ← branch tip: Tester
 9      a7e77fa   master    giteo: saved                     ← branch tip: master
10      9e2def0   Hi        giteo: init commit
11      d468855   Hi        giteo: save 'Timeline 1'
12      4722aef   Hi        giteo: save 'Timeline 1'
13      99d40e2   speed     giteo: save 'Timeline 1'         ← branch tip: speed
14      7acecf6   Hi        giteo: initial snapshot          ← root
```

\* Branch = which ref(s) point to this commit (from `git log %D`). Commits with no ref get `current_branch` (Hi).

---

## Raw Git Log Format (What `git_log_with_topology` Receives)

```
hash|parent(s)|message|refs
```

Sample rows:

| Hash     | Parent  | Message            | Refs                     |
|----------|---------|--------------------|--------------------------|
| f9f17ae  | fd47c17 | giteo: Saved       | HEAD -> Hi               |
| fd47c17  | 38290b3 | giteo: removed clip| (none → Hi)              |
| 38290b3  | 4284e62 | giteo: hello       | origin/Hi                |
| 4284e62  | 1731698 | giteo: hi          | (none → Hi)              |
| 1731698  | 1834589 | giteo: Hi          | New                      |
| 1834589  | 5669a84 | giteo: jhi         | origin/New               |
| 5669a84  | 56f244f | giteo: 1           | Lebron                   |
| 56f244f  | 840fb18 | giteo: save version| (none → Hi)              |
| 840fb18  | a7e77fa | giteo: New         | origin/Tester, Tester    |
| a7e77fa  | 9e2def0 | giteo: saved       | origin/master, master    |
| 9e2def0  | d468855 | giteo: init commit | (none → Hi)              |
| d468855  | 4722aef | giteo: save 'Timeline 1' | (none → Hi)      |
| 4722aef  | 99d40e2 | giteo: save 'Timeline 1' | (none → Hi)      |
| 99d40e2  | 7acecf6 | giteo: save 'Timeline 1' | speed             |
| 7acecf6  | (root)  | giteo: initial snapshot | (none → Hi)       |

---

## Graph Topology: Important Detail

**Your history is linear.** Every commit has exactly one parent. There are no merges and no forks.

- **master** points at `a7e77fa`
- **Tester** points at `840fb18` (one commit ahead of master)
- **Lebron** points at `5669a84` (ahead of Tester)
- **New** points at `1731698` (ahead of Lebron)
- **Hi** points at `f9f17ae` (ahead of New)

So all branch tips are just labels along one straight line. There is no “branch popping out to the right” in the true git sense — nothing actually diverges.

---

## What the Graph Logic Currently Uses

From `giteo/core.py` and `giteo_panel_qt.py`:

1. **Branch for a commit**
   - From `%D`: if `HEAD -> X`, branch = X
   - Otherwise first local ref (no `/`) in the refs list
   - Fallback: `current_branch` (e.g. Hi)

2. **Main vs branch commits**
   - “Main” = branch name is `main` or `master`
   - “Branch” = everything else

3. **Drawing**
   - Main commits: drawn on the left vertical line
   - Branch commits: drawn offset to the right with curves
   - But with your data, only `a7e77fa` is “main” (master). Most others get “Hi” (fallback), so they look like “main” commits.

---

## Suggested Graph Fixes (Aligned with Your Layout)

Given this linear history, here are options:

1. **Treat branch tips as “branches”**
   - Treat commits that are **ref tips** (New, Lebron, Tester, master, speed) as branch commits and offset them to the right.
   - Draw fork curves from the previous commit to each tip, and merge curves back (even though they’re still on the same line).

2. **Use first-parent walk**
   - Walk the first parent from HEAD and mark that as main.
   - Everything else (other parents of merges) would be branches. In your project there are no merges, so everything stays on main.

3. **Match GitHub semantics**
   - Use `git log --graph`-style logic (or similar) to assign columns/lanes.
   - For linear history, everything stays in the same column.

---

## Quick Reference: Which Commits Are Branch Tips

| Index | Hash    | Message        | Branch  | Is branch tip? |
|-------|---------|----------------|---------|----------------|
| 0     | f9f17ae | Saved          | Hi      | Yes (HEAD)     |
| 1     | fd47c17 | removed clip   | Hi      | No             |
| 2     | 38290b3 | hello          | Hi      | No             |
| 3     | 4284e62 | hi             | Hi      | No             |
| 4     | 1731698 | Hi             | New     | Yes            |
| 5     | 1834589 | jhi            | Hi      | No             |
| 6     | 5669a84 | 1              | Lebron  | Yes            |
| 7     | 56f244f | save version   | Hi      | No             |
| 8     | 840fb18 | New            | Tester  | Yes            |
| 9     | a7e77fa | saved          | master  | Yes            |
| 10    | 9e2def0 | init commit    | Hi      | No             |
| 11    | d468855 | save 'Timeline 1' | Hi   | No             |
| 12    | 4722aef | save 'Timeline 1' | Hi   | No             |
| 13    | 99d40e2 | save 'Timeline 1' | speed | Yes            |
| 14    | 7acecf6 | initial snapshot | Hi   | No (root)      |
