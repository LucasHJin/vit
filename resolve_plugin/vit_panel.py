"""Vit: Panel — Redirects to PySide6 panel launcher.

Falls back to tkinter panel if PySide6 is not available.
Run from Workspace > Scripts > Vit - Panel.
"""
import os
import sys
import traceback

# Bootstrap
try:
    _real = os.path.realpath(__file__)
except NameError:
    _real = None
if _real:
    _root = os.path.dirname(os.path.dirname(_real))
    if os.path.isdir(os.path.join(_root, "vit")) and _root not in sys.path:
        sys.path.insert(0, _root)
else:
    _pf = os.path.expanduser("~/.vit/package_path")
    if os.path.exists(_pf):
        with open(_pf) as _f:
            _root = _f.read().strip()
        if _root and os.path.isdir(os.path.join(_root, "vit")) and _root not in sys.path:
            sys.path.insert(0, _root)

# Resolve may inject 'resolve' into the script's globals when run from Workspace > Scripts.
# Imported modules don't see it — inject into builtins so launcher/tkinter can access it.
# Fallback: get it via DaVinciResolveScript (required when injection doesn't happen).
try:
    import builtins
    try:
        builtins.resolve = resolve  # noqa: F821
    except NameError:
        import DaVinciResolveScript as _dvr
        builtins.resolve = _dvr.scriptapp("Resolve")
except Exception:
    pass

try:
    from resolve_plugin.vit_panel_launcher import main
    main()
except Exception:
    # Fallback to tkinter panel
    sys.stderr.write("[vit] Qt panel unavailable, falling back to Tkinter.\n")
    try:
        from resolve_plugin.vit_panel_tkinter import main as tkinter_main
        tkinter_main()
    except Exception:
        print(f"[vit] PANEL ERROR:\n{traceback.format_exc()}")
