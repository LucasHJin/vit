"""Bootstrap the giteo package path for Resolve scripts.

Resolve runs scripts via symlink, so __file__ may point to the symlink
location (Resolve's Scripts/Edit dir) rather than the actual repo.
This module resolves the real path to find the giteo package.
"""

import os
import sys


def setup():
    """Add the giteo repo root to sys.path so 'import giteo' works."""
    repo_root = None

    # Method 1: resolve symlink via realpath on this file
    try:
        real_path = os.path.realpath(__file__)
        candidate = os.path.dirname(os.path.dirname(real_path))
        if os.path.isdir(os.path.join(candidate, "giteo")):
            repo_root = candidate
    except (NameError, OSError):
        pass

    # Method 2: fallback to saved path from 'giteo install-resolve'
    if not repo_root:
        path_file = os.path.expanduser("~/.giteo/package_path")
        if os.path.exists(path_file):
            with open(path_file) as f:
                candidate = f.read().strip()
            if candidate and os.path.isdir(os.path.join(candidate, "giteo")):
                repo_root = candidate

    if repo_root and repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    return repo_root
