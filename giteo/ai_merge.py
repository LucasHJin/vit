"""AI-powered semantic merge resolution using Gemini API."""

import json
import os
from typing import Dict, List, Optional

from .validator import ValidationIssue, format_issues


MERGE_SYSTEM_PROMPT = """\
You are a video editing timeline merge resolver. You resolve merge conflicts \
and cross-domain semantic issues in giteo timeline files.

The timeline is split into domain files: cuts.json, color.json, audio.json, \
effects.json, markers.json, metadata.json.

Clips are linked across files by their "id" field (e.g., "item_001_000").

Rules:
- If a clip was deleted in one branch, remove its references from ALL domain files
- Audio clip boundaries must match their corresponding video clip boundaries
- No two clips may overlap on the same track at the same timecode
- Preserve as much work from both branches as possible
- When in doubt, prefer the branch that made the more recent commit

Return ONLY valid JSON. Return a JSON object with keys for each domain file \
that needs changes (e.g., {"cuts": {...}, "color": {...}}).
"""


def _build_merge_prompt(
    base_files: Dict[str, dict],
    ours_files: Dict[str, dict],
    theirs_files: Dict[str, dict],
    issues: List[ValidationIssue],
    conflicted_files: List[str],
) -> str:
    """Build the merge resolution prompt for the LLM."""
    parts = []

    parts.append("BASE (common ancestor):")
    parts.append(json.dumps(base_files, indent=2, sort_keys=True))
    parts.append("")

    parts.append("OURS (current branch):")
    parts.append(json.dumps(ours_files, indent=2, sort_keys=True))
    parts.append("")

    parts.append("THEIRS (incoming branch):")
    parts.append(json.dumps(theirs_files, indent=2, sort_keys=True))
    parts.append("")

    if conflicted_files:
        parts.append("GIT CONFLICTED FILES:")
        for f in conflicted_files:
            parts.append(f"  - {f}")
        parts.append("")

    if issues:
        parts.append("DETECTED ISSUES:")
        parts.append(format_issues(issues))
        parts.append("")

    parts.append(
        "Return the resolved JSON for each domain file that needs changes. "
        "Use the same structure as the input files."
    )

    return "\n".join(parts)


def _load_api_key() -> Optional[str]:
    """Load GEMINI_API_KEY from environment or .env file."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key

    # Try loading from .env in project root
    from .core import find_project_root
    root = find_project_root()
    if root:
        env_path = os.path.join(root, ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        return line.split("=", 1)[1].strip().strip("'\"")

    return None


def ai_merge(
    base_files: Dict[str, dict],
    ours_files: Dict[str, dict],
    theirs_files: Dict[str, dict],
    issues: List[ValidationIssue],
    conflicted_files: Optional[List[str]] = None,
) -> Optional[Dict[str, dict]]:
    """Use Gemini API to resolve merge conflicts.

    Args:
        base_files: Domain files from merge base
        ours_files: Domain files from current branch
        theirs_files: Domain files from incoming branch
        issues: Validation issues detected
        conflicted_files: Files with git merge conflicts

    Returns:
        Dict of resolved domain files, or None if resolution fails
    """
    try:
        import google.generativeai as genai
    except ImportError:
        print("Error: 'google-generativeai' package not installed. Run: pip install google-generativeai")
        return None

    api_key = _load_api_key()
    if not api_key:
        print("Error: GEMINI_API_KEY not set. Add it to .env or set the environment variable.")
        return None

    genai.configure(api_key=api_key)

    prompt = _build_merge_prompt(
        base_files, ours_files, theirs_files, issues, conflicted_files or []
    )

    try:
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=MERGE_SYSTEM_PROMPT,
        )
        response = model.generate_content(prompt)

        # Extract JSON from response
        content = response.text

        # The LLM might wrap it in ```json ... ```
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        resolved = json.loads(content.strip())
        return resolved

    except json.JSONDecodeError as e:
        print(f"Error: AI returned invalid JSON: {e}")
        return None
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None


def merge_with_ai(
    project_dir: str,
    branch: str,
    base_files: Dict[str, dict],
    ours_files: Dict[str, dict],
    theirs_files: Dict[str, dict],
    issues: List[ValidationIssue],
    conflicted_files: List[str],
) -> bool:
    """Full AI merge flow: resolve, show diff, confirm, write.

    Returns True if merge was completed, False if aborted.
    """
    from .differ import format_diff
    from .json_writer import _write_json

    print(f"\n  Sending to AI for semantic merge resolution...")
    resolved = ai_merge(base_files, ours_files, theirs_files, issues, conflicted_files)

    if resolved is None:
        print("  AI merge resolution failed.")
        return False

    # Show what the AI changed
    print("\n  AI proposed the following changes:")
    print("  " + "=" * 50)

    # Build the resolved full state by merging AI changes into ours
    merged_files = dict(ours_files)
    for key, value in resolved.items():
        merged_files[key] = value

    diff_output = format_diff(ours_files, merged_files, branch_info=f"AI merge for '{branch}'")
    print(diff_output)
    print("  " + "=" * 50)

    # Ask for confirmation
    try:
        response = input("\n  Accept AI merge? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        response = "n"

    if response != "y":
        print("  AI merge declined.")
        return False

    # Write resolved files
    file_map = {
        "cuts": os.path.join(project_dir, "timeline", "cuts.json"),
        "color": os.path.join(project_dir, "timeline", "color.json"),
        "audio": os.path.join(project_dir, "timeline", "audio.json"),
        "effects": os.path.join(project_dir, "timeline", "effects.json"),
        "markers": os.path.join(project_dir, "timeline", "markers.json"),
        "metadata": os.path.join(project_dir, "timeline", "metadata.json"),
    }

    for key, filepath in file_map.items():
        if key in resolved:
            _write_json(filepath, resolved[key])

    print("  AI merge resolution applied.")
    return True
