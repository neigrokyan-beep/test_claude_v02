# Studio Bridge: goes to  Documents\houdini21.0\scripts\123.py  (runs once when Houdini starts without a file).
# 1) starts the Houdini MCP server together with Houdini (no shelf button);
# 2) after a crash/relaunch by the watchdog, re-opens the last scene named in
#    G:\todoist_obsidian_claude\Projects\claude\Watch_assembly\Passes\test\houdini_autoload.txt
#    (one line: full path of a .hip/.hiplc). Crash-loop guard: at most 3 loads in 15 minutes.
# A failure here must never stop Houdini from opening.
try:
    import hou
    if hou.isUIAvailable():
        import hdefereval
        import os
        import time

        _AUTOLOAD = r"G:\todoist_obsidian_claude\Projects\claude\Watch_assembly\Passes\test\houdini_autoload.txt"
        _AUTOLOG = _AUTOLOAD + ".log"

        def _studio_bridge_autostart():
            try:
                import houdini_mcp
                houdini_mcp.start_server()
                hou.ui.setStatusMessage("HoudiniMCP listening on localhost:19876")
            except Exception as exc:
                print("Studio Bridge autostart failed:", exc)

        def _studio_bridge_autoload():
            try:
                if not os.path.exists(_AUTOLOAD):
                    return
                path = open(_AUTOLOAD, encoding="utf-8").read().strip()
                if not path or not os.path.exists(path):
                    return
                now = time.time()
                recent = []
                if os.path.exists(_AUTOLOG):
                    for s in open(_AUTOLOG).read().split():
                        try:
                            if now - float(s) < 900:
                                recent.append(s)
                        except ValueError:
                            pass
                if len(recent) >= 3:
                    print("Studio Bridge autoload skipped: crash loop guard")
                    return
                recent.append(str(now))
                open(_AUTOLOG, "w").write(" ".join(recent))
                hou.hipFile.load(path, suppress_save_prompt=True, ignore_load_warnings=True)
                hou.ui.setStatusMessage("Studio Bridge reopened " + path)
            except Exception as exc:
                print("Studio Bridge autoload failed:", exc)

        hdefereval.executeDeferred(_studio_bridge_autostart)
        hdefereval.executeDeferred(_studio_bridge_autoload)
except Exception as exc:
    print("Studio Bridge autostart skipped:", exc)
