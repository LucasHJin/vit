"""Connect to a running DaVinci Resolve from outside it.

The plugin scripts get a `resolve` object injected by Resolve's Scripts menu.
A headless caller (the CLI, an agent, a hook) has to attach through Resolve's
external scripting API instead. That needs:

  - Resolve running with a project open
  - Preferences > System > General > "External scripting using" set to Local
  - Resolve Studio (the free edition no longer allows external scripting)
"""

import os
import sys


class ResolveConnectionError(Exception):
    """Raised when a running Resolve can't be reached."""
    pass


def _default_paths():
    """Blackmagic's documented default locations: (script API dir, script lib)."""
    if sys.platform == "darwin":
        return (
            "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
            "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so",
        )
    if sys.platform.startswith("win"):
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        return (
            os.path.join(program_data, "Blackmagic Design", "DaVinci Resolve",
                         "Support", "Developer", "Scripting"),
            os.path.join(program_files, "Blackmagic Design", "DaVinci Resolve",
                         "fusionscript.dll"),
        )
    return (
        "/opt/resolve/Developer/Scripting",
        "/opt/resolve/libs/Fusion/fusionscript.so",
    )


def _import_scripting_module():
    try:
        import DaVinciResolveScript
        return DaVinciResolveScript
    except ImportError:
        pass

    default_api, default_lib = _default_paths()
    api_dir = os.environ.get("RESOLVE_SCRIPT_API") or default_api
    os.environ.setdefault("RESOLVE_SCRIPT_API", api_dir)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", default_lib)

    modules_dir = os.path.join(api_dir, "Modules")
    if modules_dir not in sys.path:
        sys.path.append(modules_dir)

    try:
        import DaVinciResolveScript
        return DaVinciResolveScript
    except ImportError as e:
        raise ResolveConnectionError(
            "Couldn't load Resolve's scripting module (DaVinciResolveScript). "
            f"Looked in {modules_dir}. Set RESOLVE_SCRIPT_API and "
            f"RESOLVE_SCRIPT_LIB if Resolve is installed somewhere else. ({e})"
        )


def connect():
    """Return the `resolve` app object for the running Resolve."""
    module = _import_scripting_module()
    try:
        resolve = module.scriptapp("Resolve")
    except Exception as e:
        raise ResolveConnectionError(f"Resolve's scripting module failed: {e}")
    if not resolve:
        raise ResolveConnectionError(
            "Resolve isn't reachable. Check that it is running with a project "
            "open, and that Preferences > System > General > 'External "
            "scripting using' is set to Local (Studio only)."
        )
    return resolve


def current_project(resolve):
    """Return the open project, or raise."""
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        raise ResolveConnectionError("No project is open in Resolve.")
    return project
