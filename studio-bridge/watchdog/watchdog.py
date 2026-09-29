"""Studio Bridge watchdog (Windows, stdlib only).

Keeps Houdini and Cinema 4D alive while nobody sits at the PC:
  * a program that is not running is started again (Houdini through Steam, C4D directly);
  * a program that hangs ("Not Responding") for too long, or whose MCP port stays closed
    long after start, is killed and started again;
  * crash dialogs (WerFault, "Application Error" windows of C4D / Houdini) are closed;
  * if the tunnel (cloudflared) is up but the gateway died, only the gateway is restarted,
    so the public connector URL stays the same.
Houdini re-opens the last scene by itself (see houdini_autostart.py). C4D starts empty:
the scene has to be loaded from the cloud side.

Pause: create the file  Passes/test/watchdog.hold  in the Watch_assembly task folder
(or set HOLD below). Log: Passes/test/_watchdog.log in the same folder.
"""
import ctypes
import ctypes.wintypes as wt
import datetime
import os
import re
import socket
import subprocess
import sys
import time

VAULT = r"G:\todoist_obsidian_claude"
TASK = os.path.join(VAULT, "Projects", "claude", "Watch_assembly", "Passes", "test")
LOG = os.path.join(TASK, "_watchdog.log")
HOLD = os.path.join(TASK, "watchdog.hold")

HOU_EXE = r"F:\Steam\steamapps\common\Houdini Indie\bin\hindie.steam.exe"
HOU_PROC = "hindie.steam.exe"
HOU_APPID = "502570"
HOU_PORT = 19876
C4D_EXE = r"F:\Cinema4d_2026_2\Cinema 4D.exe"
C4D_PROC = "Cinema 4D.exe"
C4D_PORT = 5555
GW_DIR = r"C:\studio\studio-bridge"
GW_PORT = 8765

LOOP_S = 10
DETACHED = 0x00000008 | 0x00000200 | 0x01000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | BREAKAWAY_FROM_JOB
NO_WINDOW = 0x08000000

APPS = {
    "houdini": dict(proc=HOU_PROC, port=HOU_PORT, hang_limit=300, port_limit=420, cooldown=150),
    "c4d": dict(proc=C4D_PROC, port=C4D_PORT, hang_limit=240, port_limit=600, cooldown=150),
}
STATE = {k: dict(last_launch=0.0, port_down=None, hung=None, launches=[]) for k in APPS}
GW = dict(down=None)


def log(msg):
    line = "%s %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 400000:
            with open(LOG, encoding="utf-8", errors="ignore") as f:
                tail = f.readlines()[-300:]
            with open(LOG, "w", encoding="utf-8") as f:
                f.writelines(tail)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW,
                              timeout=30, errors="ignore").stdout
    except Exception:
        return ""


def running_pids():
    out = {}
    for line in run(["tasklist", "/FO", "CSV", "/NH"]).splitlines():
        parts = line.strip().strip('"').split('","')
        if len(parts) >= 2:
            out.setdefault(parts[0].lower(), []).append(parts[1])
    return out


def hung_names():
    names = set()
    for line in run(["tasklist", "/FI", "STATUS eq NOT RESPONDING", "/FO", "CSV", "/NH"]).splitlines():
        if line.startswith('"'):
            names.add(line.strip().strip('"').split('","')[0].lower())
    return names


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def kill(proc):
    run(["taskkill", "/F", "/T", "/IM", proc])


def close_error_windows(pids_by_name):
    """Close 'error' dialogs that belong to C4D / Houdini so a crash does not sit there for hours."""
    user32 = ctypes.windll.user32
    watch = set()
    for p in (HOU_PROC, C4D_PROC):
        for pid in pids_by_name.get(p.lower(), []):
            watch.add(int(pid))
    if not watch:
        return
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in watch:
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value
        if re.search(r"(?i)application error|has stopped working|crash|fatal|unhandled exception", title):
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            log("closed dialog '%s' (pid %d)" % (title, pid.value))
        return True

    user32.EnumWindows(proto(cb), 0)


def launch(name):
    st = STATE[name]
    now = time.time()
    st["launches"] = [t for t in st["launches"] if now - t < 1800]
    if len(st["launches"]) >= 6:
        log("%s: 6 launches in 30 min, pause relaunching" % name)
        st["last_launch"] = now + 1500
        return
    st["launches"].append(now)
    st["last_launch"] = now
    st["port_down"] = None
    st["hung"] = None
    try:
        if name == "houdini":
            try:
                os.startfile("steam://rungameid/%s" % HOU_APPID)
            except OSError:
                subprocess.Popen([HOU_EXE], cwd=os.path.dirname(HOU_EXE), creationflags=DETACHED)
        else:
            subprocess.Popen([C4D_EXE], cwd=os.path.dirname(C4D_EXE), creationflags=DETACHED)
        log("%s: launched" % name)
    except Exception as exc:
        log("%s: launch failed: %s" % (name, exc))


def tick(name, pids, hung):
    cfg, st = APPS[name], STATE[name]
    now = time.time()
    proc = cfg["proc"].lower()
    if proc not in pids:
        if now - st["last_launch"] > cfg["cooldown"]:
            log("%s: not running" % name)
            launch(name)
        return
    if proc in hung:
        st["hung"] = st["hung"] or now
        if now - st["hung"] > cfg["hang_limit"]:
            log("%s: not responding for %ds, killing" % (name, now - st["hung"]))
            kill(cfg["proc"])
            st["hung"] = None
            st["last_launch"] = min(st["last_launch"], now - cfg["cooldown"] + 20)
            return
    else:
        st["hung"] = None
    if port_open(cfg["port"]):
        st["port_down"] = None
    else:
        base = max(st["port_down"] or now, st["last_launch"])
        st["port_down"] = st["port_down"] or now
        if now - base > cfg["port_limit"]:
            log("%s: MCP port %d closed for %ds, killing" % (name, cfg["port"], now - base))
            kill(cfg["proc"])
            st["port_down"] = None
            st["last_launch"] = min(st["last_launch"], now - cfg["cooldown"] + 20)


def gateway_tick(pids):
    now = time.time()
    if port_open(GW_PORT):
        GW["down"] = None
        return
    if "cloudflared.exe" not in pids:
        return  # tunnel gone too: a restart would change the public URL, leave it to the user
    GW["down"] = GW["down"] or now
    if now - GW["down"] < 40:
        return
    py = os.path.join(GW_DIR, "gateway", ".venv", "Scripts", "python.exe")
    cfg = os.path.join(GW_DIR, "gateway", "servers.json")
    logs = os.path.join(GW_DIR, "logs")
    try:
        os.makedirs(logs, exist_ok=True)
        out = open(os.path.join(logs, "gateway.out.log"), "a")
        subprocess.Popen([py, os.path.join(GW_DIR, "gateway", "gateway.py"), "--config", cfg, "--port", str(GW_PORT)],
                         stdout=out, stderr=out, cwd=GW_DIR, creationflags=DETACHED)
        log("gateway: restarted (tunnel is up)")
    except Exception as exc:
        log("gateway: restart failed: %s" % exc)
    GW["down"] = now + 60


def main():
    lock = socket.socket()
    try:
        lock.bind(("127.0.0.1", 19999))
    except OSError:
        return  # already running
    log("watchdog started (pid %d)" % os.getpid())
    while True:
        try:
            if not os.path.exists(HOLD):
                pids = running_pids()
                hung = hung_names()
                for name in APPS:
                    tick(name, pids, hung)
                gateway_tick(pids)
                if "werfault.exe" in pids:
                    time.sleep(4)
                    kill("WerFault.exe")
                close_error_windows(pids)
        except Exception as exc:
            log("loop error: %r" % (exc,))
        time.sleep(LOOP_S)


if __name__ == "__main__":
    main()
