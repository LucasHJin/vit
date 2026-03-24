# Collaborating with Vit

Vit shares the **edit** — timeline cuts, color grades, audio levels. It does **not** upload video files. Share footage the way you already do (shared drive, Dropbox, server).

**Prerequisites:** Vit installed, Git installed, `vit install-resolve` run once, Resolve restarted. See the main [README](../README.md) if any command is not found.

---

## Before anyone starts

1. On **GitHub** (or GitLab, etc.), create a **new empty repository** — no README, no license file.
2. Copy the **HTTPS clone URL** (e.g. `https://github.com/yourname/your-repo.git`).

---

## Person who starts the project (once, in Terminal)

1. Navigate to where you want the project folder:
   ```bash
   cd ~/Documents
   ```
2. Create and enter the Vit project:
   ```bash
   vit init my-project
   cd my-project
   ```
3. Open **DaVinci Resolve**, open your project and timeline.
4. Open the **Vit Panel** (`Workspace → Scripts → Vit Panel`). If it asks for a folder, choose the `my-project` folder (the one containing `.vit`).
   - If the panel doesn't appear, quit Resolve, run `export VIT_PROJECT_DIR="$HOME/Documents/my-project"` in Terminal, then reopen Resolve.
5. In the panel, click **Save Version** to create the first snapshot.
6. Back in Terminal, connect to your shared repo:
   ```bash
   vit collab setup
   ```
   Paste the empty repo URL when prompted. Sign in to GitHub if asked.
7. Send the `vit clone …` line Terminal prints to your collaborators.

---

## Collaborators joining (once, in Terminal)

1. Navigate to where you want the project folder:
   ```bash
   cd ~/Documents
   ```
2. Clone using the command your lead sent:
   ```bash
   vit clone https://github.com/yourname/your-repo.git
   cd your-repo
   ```
3. Pull the latest timeline state:
   ```bash
   vit checkout main
   ```
4. Copy your team's footage onto your machine (any local path is fine — you can relink in Resolve).
5. Open **DaVinci Resolve**, open your project.
6. Open the **Vit Panel** (`Workspace → Scripts → Vit Panel`), click **Switch Branch**, and choose `main` to restore the timeline.
7. **Relink** any offline clips in Resolve if you see red media.
8. Create your own branch (agree on a naming convention with your team):
   ```bash
   vit branch your-name
   ```

From here, everything happens in the Vit Panel inside Resolve.

---

## Every work session (Vit Panel)

1. Open the **Vit Panel** in Resolve.
2. Click **Pull** to fetch the latest changes from the team.
3. Click **Switch Branch** → select your branch to restore the timeline.
4. Edit in Resolve as usual.
5. Click **Save Version** to record your changes.
6. Click **Push** to share your work.

---

## Merging work (lead / editor, Vit Panel)

1. Click **Pull** to get everyone's latest commits.
2. Click **Switch Branch** → select `main` (or whichever branch your team merges into).
3. Click **Merge** → select the branch to bring in. The panel shows a summary of changes and flags any conflicts.
4. Click **Push** to share the merged result.
5. Tell teammates to **Pull** and **Switch Branch** in their panels to see the merged timeline.

For complex cross-domain conflicts (e.g., a clip deleted on one branch while color-graded on another), use the CLI for full AI-assisted resolution:
```bash
vit merge other-persons-branch
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Not a vit project" | Make sure you're in the folder that contains `.vit`. |
| "No vit project" in Resolve | Open the panel and pick the correct folder, or set `VIT_PROJECT_DIR` to that folder and restart Resolve. |
| Timeline looks wrong after clone | Run `vit checkout main` in Terminal, then **Switch Branch** in the panel. |
| `vit collab setup` fails | Make sure the GitHub repo is **empty** (no files), then try again. Check you're logged in to GitHub. |
| Red media after switching branches | Footage paths differ — use Resolve's **Relink** to point clips at your local footage. |

For anything else, see the main [README](../README.md).
