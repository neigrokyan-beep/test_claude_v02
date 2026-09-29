"""Weaver MCP server: the Obsidian vault and the Greyscalegorilla (GSG) library.

Runs on the user's PC as one of the Studio Bridge apps. It gives a cloud Claude
session what a local Claude Code session has: the Weaver vault (read / write with
guard rails) and the GSG material, model and HDRI library (read only).

Environment:
    WEAVER_VAULT  vault root            (default G:\\todoist_obsidian_claude)
    WEAVER_GSG    GSG library root      (default E:\\assets\\Greyscalegorilla Studio\\assets\\Greyscalegorilla_Library)

Rules baked in (from the vault's own MAP.md / gsg-library skill):
  - the GSG library is never written to;
  - nothing is deleted; an overwritten file is first copied to Agent/History/<date>/;
  - files that steer the local agent or are generated are not writable from here
    (CLAUDE.md, AGENTS.md, .claude/, .agents/, Agent/Scripts, STATE.md, PROJECTS.md,
    Eagle_lib, .obsidian, .git).
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import base64

import mcp.types as mtypes
from mcp.server.fastmcp import FastMCP, Image

VAULT = Path(os.environ.get("WEAVER_VAULT", r"G:\todoist_obsidian_claude"))
GSG = Path(
    os.environ.get(
        "WEAVER_GSG", r"E:\assets\Greyscalegorilla Studio\assets\Greyscalegorilla_Library"
    )
)

TEXT_EXT = {".md", ".txt", ".json", ".py", ".js", ".yml", ".yaml", ".csv", ".canvas", ".css"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif"}
# Steer the local agent (which has a shell) or are generated / managed elsewhere.
WRITE_BLOCK = (
    "claude.md", "agents.md", ".claude", ".agents", ".git", ".obsidian", "eagle_lib",
    "agent/history", "agent/scripts", "agent/state.md", "agent/projects.md",
    "library/tutorial/houdini",
)
SEARCH_SKIP_DIRS = {".git", ".obsidian", "eagle_lib", "node_modules", "history"}
MAX_WRITE_CHARS = 500_000

mcp = FastMCP(
    "Weaver",
    instructions=(
        "Obsidian vault (Weaver) and Greyscalegorilla library of the user's PC. "
        "Start with weaver_context. Materials for scenes come from the GSG library: "
        "gsg_find -> gsg_preview -> gsg_show (Redshift recipe with map paths)."
    ),
)


# ------------------------------------------------------------------ helpers


def _vroot() -> Path:
    if not VAULT.is_dir():
        raise FileNotFoundError(f"Vault folder not found: {VAULT} (set WEAVER_VAULT)")
    return VAULT.resolve()


def _gsg_root() -> Path:
    if not GSG.is_dir():
        raise FileNotFoundError(f"GSG library folder not found: {GSG} (set WEAVER_GSG)")
    return GSG.resolve()


def _vpath(rel: str) -> Path:
    root = _vroot()
    rel = (rel or "").replace("\\", "/").strip().lstrip("/")
    if re.match(r"^[A-Za-z]:", rel):
        raise ValueError("Use a path relative to the vault root, e.g. 'Projects/claude'")
    p = (root / rel).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        raise ValueError("Path is outside the vault") from None
    return p


def _rel(p: Path) -> str:
    return p.relative_to(_vroot()).as_posix()


def _writable(p: Path) -> None:
    rel = _rel(p).lower()
    for blocked in WRITE_BLOCK:
        if rel == blocked or rel.startswith(blocked + "/"):
            raise PermissionError(
                f"'{_rel(p)}' is protected (agent instructions, generated or managed by another tool). "
                "Ask the user to change it."
            )
    if p.suffix.lower() not in TEXT_EXT:
        raise PermissionError(f"Only text files can be written ({', '.join(sorted(TEXT_EXT))}).")


def _backup(p: Path) -> str | None:
    if not p.exists():
        return None
    now = datetime.now()
    folder = _vroot() / "Agent" / "History" / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    name = "__".join(p.relative_to(_vroot()).parts)
    dst = folder / name
    if dst.exists():
        dst = folder / f"{now:%H%M%S}_{name}"
    shutil.copy2(p, dst)
    return dst.relative_to(_vroot()).as_posix()


def _read_text(p: Path) -> str:
    data = p.read_bytes()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _as_image(p: Path, max_px: int) -> Image:
    from PIL import Image as PILImage

    try:
        im = PILImage.open(p)
        im.load()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Cannot open {p.name} as an image ({type(exc).__name__}); EXR/HDR are not supported") from exc
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = PILImage.new("RGB", im.size, (128, 128, 128))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    im.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return Image(data=buf.getvalue(), format="jpeg")


# ------------------------------------------------------------------ vault


@mcp.tool()
def weaver_context() -> str:
    """Load the vault's entry context: CLAUDE.md with its @-imported files (START, STATE, MAP, PROJECTS).
    Call this first when starting work. Note: it is written for a local Claude Code on the PC; in this
    cloud session use the weaver__ tools instead of direct file access."""
    root = _vroot()
    entry = root / "CLAUDE.md"
    if not entry.is_file():
        raise FileNotFoundError(f"CLAUDE.md not found in {root}")
    out: list[str] = []
    for line in _read_text(entry).splitlines():
        m = re.match(r"^@(\S+\.md)\s*$", line.strip())
        if not m:
            out.append(line)
            continue
        sub = (root / m.group(1)).resolve()
        try:
            sub.relative_to(root)
            body = _read_text(sub)[:40_000]
        except (ValueError, OSError):
            body = "(unavailable)"
        out.append(f"\n----- {m.group(1)} -----\n{body}\n----- end {m.group(1)} -----\n")
    return "\n".join(out)


@mcp.tool()
def vault_list(path: str = "", depth: int = 1, max_entries: int = 300) -> str:
    """List a vault folder. path is relative to the vault root ('' = root). depth 1-3."""
    base = _vpath(path)
    if not base.is_dir():
        raise NotADirectoryError(f"Not a folder: {path}")
    depth = max(1, min(depth, 3))
    lines: list[str] = []

    def walk(d: Path, level: int) -> None:
        try:
            entries = sorted(os.scandir(d), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError as exc:
            lines.append("  " * level + f"(unreadable: {exc})")
            return
        for e in entries:
            if len(lines) >= max_entries:
                return
            if e.is_dir():
                lines.append("  " * level + e.name + "/")
                # Eagle_lib holds tens of thousands of items: show it, don't descend.
                if level + 1 < depth and e.name.lower() != "eagle_lib":
                    walk(Path(e.path), level + 1)
            else:
                try:
                    size = e.stat().st_size
                except OSError:
                    size = -1
                lines.append("  " * level + f"{e.name}  ({size} B)")

    walk(base, 0)
    if len(lines) >= max_entries:
        lines.append(f"... truncated at {max_entries} entries; list a subfolder")
    return "\n".join(lines) or "(empty)"


@mcp.tool()
def vault_read(path: str, offset: int = 0, limit: int = 60000) -> str:
    """Read a text file from the vault (path relative to the vault root). Long files: use offset/limit (characters)."""
    p = _vpath(path)
    if not p.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    if p.suffix.lower() in IMAGE_EXT:
        raise ValueError("This is an image: use view_image")
    if p.stat().st_size > 5_000_000:
        raise ValueError("File is larger than 5 MB")
    text = _read_text(p)
    chunk = text[offset : offset + limit]
    tail = "" if offset + limit >= len(text) else f"\n[... {len(text) - offset - limit} more characters; call again with offset={offset + limit}]"
    return chunk + tail


@mcp.tool()
def vault_search(query: str, folder: str = "", regex: bool = False, max_results: int = 60) -> str:
    """Search text inside vault notes and scripts (case-insensitive). folder narrows the search."""
    base = _vpath(folder)
    pat = re.compile(query if regex else re.escape(query), re.IGNORECASE)
    hits: list[str] = []
    started = time.monotonic()
    root = _vroot()
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d.lower() not in SEARCH_SKIP_DIRS]
        for name in filenames:
            if Path(name).suffix.lower() not in TEXT_EXT:
                continue
            fp = Path(dirpath) / name
            try:
                if fp.stat().st_size > 1_500_000:
                    continue
                for i, line in enumerate(_read_text(fp).splitlines(), 1):
                    if pat.search(line):
                        hits.append(f"{fp.relative_to(root).as_posix()}:{i}: {line.strip()[:200]}")
                        if len(hits) >= max_results:
                            return "\n".join(hits) + f"\n[stopped at {max_results} results]"
            except OSError:
                continue
        if time.monotonic() - started > 25:
            return "\n".join(hits) + "\n[stopped: 25 s limit, narrow the folder]"
    return "\n".join(hits) or "no matches"


@mcp.tool()
def vault_write(path: str, content: str, mode: str = "create") -> str:
    """Write a text note or script in the vault.
    mode: 'create' (fails if the file exists), 'overwrite' (the old version is copied to
    Agent/History/<date>/ first), 'append'. Nothing can be deleted. Protected: CLAUDE.md, AGENTS.md,
    .claude/, .agents/, Agent/Scripts, Agent/STATE.md, Agent/PROJECTS.md, Eagle_lib, .obsidian, .git."""
    if mode not in ("create", "overwrite", "append"):
        raise ValueError("mode must be create, overwrite or append")
    if len(content) > MAX_WRITE_CHARS:
        raise ValueError(f"Content is larger than {MAX_WRITE_CHARS} characters")
    p = _vpath(path)
    _writable(p)
    if p.is_dir():
        raise IsADirectoryError(path)
    backup = None
    if p.exists() and mode == "create":
        raise FileExistsError(f"{path} exists; use mode='overwrite' or 'append'")
    if p.exists() and mode in ("overwrite", "append"):
        backup = _backup(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append":
        with open(p, "a", encoding="utf-8", newline="") as f:
            f.write(content)
    else:
        tmp = p.with_name(p.name + ".tmp-weaver")
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        os.replace(tmp, p)
    return f"written {_rel(p)} ({mode})" + (f"; previous version saved to {backup}" if backup else "")


@mcp.tool()
def view_image(path: str, max_px: int = 900) -> Image:
    """Look at an image: a vault file (relative path) or a file inside the GSG library (absolute path
    from gsg_show). Returned downscaled. PNG/JPG/TIF/WEBP only, no EXR/HDR."""
    raw = (path or "").strip()
    p: Path | None = None
    if re.match(r"^[A-Za-z]:|^/", raw) and Path(raw).is_absolute():
        cand = Path(raw).resolve()
        for root in (_gsg_root(), _vroot()):
            try:
                cand.relative_to(root)
                p = cand
                break
            except ValueError:
                continue
        if p is None:
            raise ValueError("Only files inside the vault or the GSG library can be viewed")
    else:
        p = _vpath(raw)
    if not p.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    if p.suffix.lower() not in IMAGE_EXT:
        raise ValueError(f"Not a supported image type: {p.suffix}")
    return _as_image(p, max(128, min(max_px, 2000)))


# ------------------------------------------------------------------ video reference

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi", ".gif"}


def _jpeg(data: bytes) -> Any:
    return mtypes.ImageContent(type="image", data=base64.b64encode(data).decode("ascii"), mimeType="image/jpeg")


def _text(t: str) -> Any:
    return mtypes.TextContent(type="text", text=t)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise FileNotFoundError("ffmpeg not found in PATH on the PC (winget install Gyan.FFmpeg)")
    return exe


def _video_path(path: str) -> Path:
    p = _vpath(path)
    if not p.is_file() or p.suffix.lower() not in VIDEO_EXT:
        raise FileNotFoundError(f"Not a video file in the vault: {path}")
    return p


def _run_ffmpeg(args: list[str], timeout: int = 90) -> bytes:
    proc = subprocess.run([_ffmpeg(), "-hide_banner", "-loglevel", "error", *args],
                          capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + proc.stderr.decode("utf-8", "replace")[-400:])
    return proc.stdout


@mcp.tool()
def video_info(path: str) -> str:
    """Duration, frame size and frame rate of a video in the vault (path relative to the vault root)."""
    p = _video_path(path)
    proc = subprocess.run([_ffmpeg(), "-hide_banner", "-i", str(p)], capture_output=True, timeout=30)
    text = proc.stderr.decode("utf-8", "replace")
    dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", text)
    vid = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", text)
    fps = re.search(r"([\d.]+)\s*fps", text)
    seconds = int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3]) if dur else None
    return json.dumps({"file": p.name, "seconds": seconds, "size": f"{vid[1]}x{vid[2]}" if vid else None,
                       "fps": float(fps[1]) if fps else None}, ensure_ascii=False)


@mcp.tool()
def video_frames(path: str, times: list[float], max_px: int = 960) -> list[Any]:
    """Frames of a video at the given times in seconds (up to 12 per call), returned as images in that order.
    Use it to study a reference: motion, timing, what appears when."""
    p = _video_path(path)
    if not times or len(times) > 12:
        raise ValueError("give 1 to 12 times")
    out: list[Any] = []
    px = max(160, min(max_px, 1600))
    for t in times:
        if not (0 <= float(t) < 36000):
            raise ValueError(f"bad time {t}")
        data = _run_ffmpeg(["-ss", f"{float(t):.3f}", "-i", str(p), "-frames:v", "1",
                            "-vf", f"scale='min({px},iw)':-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "3", "-"])
        if not data:
            raise ValueError(f"no frame at {t}s (past the end?)")
        out.append(_text(f"t = {float(t):.3f} s"))
        out.append(_jpeg(data))
    return out


@mcp.tool()
def video_sheet(path: str, start: float = 0.0, end: float = 0.0, cols: int = 4, rows: int = 4, tile_px: int = 420) -> list[Any]:
    """One contact sheet of evenly spaced frames from start to end (end 0 = whole video), left to right,
    top to bottom. Cheapest way to see the whole motion; then video_frames for the moments that matter.
    The text lists the time of every tile."""
    p = _video_path(path)
    cols, rows = max(1, min(cols, 8)), max(1, min(rows, 8))
    info = json.loads(video_info(path))
    total = float(info["seconds"] or 0)
    end = float(end) if end and end > 0 else total
    end = min(end, total) if total else end
    if end <= start:
        raise ValueError("end must be greater than start")
    n = cols * rows
    step = (end - start) / n
    times = [start + step * (i + 0.5) for i in range(n)]
    px = max(120, min(tile_px, 800))
    data = _run_ffmpeg(["-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(p),
                        "-vf", f"fps={n / (end - start):.6f},scale={px}:-2,tile={cols}x{rows}",
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "3", "-"], timeout=180)
    if not data:
        raise ValueError("no frames produced")
    lines = [f"{i + 1}: {t:.2f}s" for i, t in enumerate(times)]
    return [_text("tiles (left to right, top to bottom): " + "  ".join(lines)), _jpeg(data)]


def _next_day_index(task: Path, day: str) -> int:
    """Next NNN of the task's per-day counter, shared by Output/Images, Videos, Refs and Claude_refs."""
    best = 0
    for sub in ("Images", "Videos", "Refs", "Claude_refs"):
        d = task / "Output" / sub
        if d.is_dir():
            for f in d.iterdir():
                m = re.match(rf"^{day}_(\d{{3}})\.", f.name)
                if m:
                    best = max(best, int(m[1]))
    return best + 1


@mcp.tool()
def ref_save_frames(path: str, times: list[float], task: str, max_px: int = 1600) -> str:
    """Save frames of a reference video into the task, apart from the user's own shots and renders: full frame in
    <task>/Output/Claude_refs/YYYYMMDD_NNN.jpg and a 320 px preview in <task>/Output/Claude_refs/Thumbs/ with the same name;
    NNN continues the task's day counter. Every call is a new batch, earlier refs are never overwritten.
    path: the video (vault-relative); task: e.g. 'Projects/claude/Yogo_pro_keyboard'; up to 24 times."""
    from PIL import Image as PILImage

    p = _video_path(path)
    t_dir = _vpath(task)
    parts = t_dir.relative_to(_vroot()).parts
    if len(parts) != 3 or parts[0] != "Projects" or not t_dir.is_dir():
        raise ValueError("task must be an existing 'Projects/<branch>/<task>' folder")
    if not times or len(times) > 24:
        raise ValueError("give 1 to 24 times")
    day = datetime.now().strftime("%Y%m%d")
    n = _next_day_index(t_dir, day)
    refs = t_dir / "Output" / "Claude_refs"
    thumbs = refs / "Thumbs"
    refs.mkdir(parents=True, exist_ok=True)
    thumbs.mkdir(parents=True, exist_ok=True)
    px = max(320, min(max_px, 2400))
    saved = []
    for t in times:
        if not (0 <= float(t) < 36000):
            raise ValueError(f"bad time {t}")
        data = _run_ffmpeg(["-ss", f"{float(t):.3f}", "-i", str(p), "-frames:v", "1",
                            "-vf", f"scale='min({px},iw)':-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "2", "-"])
        if not data:
            raise ValueError(f"no frame at {t}s")
        name = f"{day}_{n:03d}.jpg"
        (refs / name).write_bytes(data)
        im = PILImage.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((320, 320))
        im.save(thumbs / name, "JPEG", quality=82)
        saved.append(f"{name}  <- {float(t):.2f}s")
        n += 1
    return f"saved {len(saved)} refs from {p.name} into {_rel(refs)} (+ previews in Thumbs):\n" + "\n".join(saved)


# ------------------------------------------------------------------ GSG library

ASSET_RE = re.compile(r"^GSG_(?P<coll>[A-Za-z]{1,4}\d{2,4})_(?P<num>[A-Za-z]?\d{1,4})_(?P<name>.+)$")
MAP_RE = re.compile(r"_(?P<res>\d+k)_(?P<map>[A-Za-z0-9_]+?)\.(?P<ext>jpg|jpeg|png|tif|tiff|exr)$", re.IGNORECASE)
KINDS = ("materials", "models", "hdris", "textures", "gobos", "bokeh")


@dataclass
class Asset:
    kind: str
    path: str
    folder: str
    coll: str
    num: str
    name: str
    category: str = ""

    @property
    def code(self) -> str:
        return f"{self.coll}_{self.num}".upper()


_INDEX: dict[str, list[Asset]] | None = None


def _index() -> dict[str, list[Asset]]:
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    root = _gsg_root()
    idx: dict[str, list[Asset]] = {}
    for kind in KINDS:
        base = root / kind
        items: list[Asset] = []

        def walk(d: str, depth: int, cat: str) -> None:
            try:
                entries = list(os.scandir(d))
            except OSError:
                return
            for e in entries:
                if not e.is_dir():
                    continue
                m = ASSET_RE.match(e.name)
                if m:
                    items.append(Asset(kind, e.path, e.name, m["coll"].upper(), m["num"].upper(),
                                       m["name"].replace("_", " "), cat))
                elif depth < 2:
                    walk(e.path, depth + 1, e.name if depth == 0 else cat)

        if base.is_dir():
            walk(str(base), 0, "")
        items.sort(key=lambda a: (a.coll, a.num))
        idx[kind] = items
    _INDEX = idx
    return idx


def _describe(a: Asset) -> str:
    cat = f" [{a.category}]" if a.category else ""
    return f"{a.code}  {a.name}{cat}  ({a.kind})"


def _find_asset(ref: str) -> Asset:
    ref = ref.strip()
    up = ref.upper()
    for items in _index().values():
        for a in items:
            if a.code == up or a.folder.lower() == ref.lower():
                return a
    raise KeyError(f"No GSG asset '{ref}'. Use gsg_find to search.")


@mcp.tool()
def gsg_stats() -> str:
    """Overview of the GSG library: asset counts per kind and the biggest collections."""
    idx = _index()
    lines = [f"library: {_gsg_root()}"]
    for kind, items in idx.items():
        if not items:
            continue
        colls: dict[str, int] = {}
        for a in items:
            colls[a.coll] = colls.get(a.coll, 0) + 1
        top = ", ".join(f"{c}({n})" for c, n in sorted(colls.items(), key=lambda x: -x[1])[:8])
        lines.append(f"{kind}: {len(items)} assets in {len(colls)} collections; biggest: {top}")
    return "\n".join(lines)


@mcp.tool()
def gsg_guide() -> str:
    """The user's own guide to the GSG library (which collection has what: metals, plastics, wood, HDRI ...
    and how to apply materials in Redshift). Read it before choosing materials."""
    p = _vroot() / ".claude" / "skills" / "gsg-library" / "SKILL.md"
    if not p.is_file():
        raise FileNotFoundError("Guide not found: .claude/skills/gsg-library/SKILL.md in the vault")
    return _read_text(p)


@mcp.tool()
def gsg_find(query: str, kind: str = "materials", collection: str = "", n: int = 25) -> str:
    """Search GSG assets by words in the English name, e.g. 'anodized aluminum', 'oak', 'studio'.
    kind: materials | models | hdris | textures | gobos | bokeh | all. collection: e.g. MC005.
    Returns codes for gsg_show / gsg_preview."""
    idx = _index()
    kinds = list(idx) if kind == "all" else [kind]
    if any(k not in idx for k in kinds):
        raise ValueError(f"kind must be one of {', '.join(idx)} or all")
    tokens = [t for t in re.split(r"\s+", query.lower().strip()) if t]
    scored: list[tuple[int, Asset]] = []
    for k in kinds:
        for a in idx[k]:
            if collection and a.coll != collection.upper():
                continue
            hay = f"{a.name} {a.code} {a.coll} {a.category}".lower()
            words = set(re.split(r"[^a-z0-9]+", hay))
            if all(t in hay for t in tokens):
                scored.append((sum(2 if t in words else 1 for t in tokens), a))
    scored.sort(key=lambda x: (-x[0], x[1].code))
    total = len(scored)
    rows = [_describe(a) for _, a in scored[: max(1, min(n, 100))]]
    if not rows:
        return "no matches (try fewer or different words, or gsg_guide / gsg_collection)"
    return f"{total} match(es), showing {len(rows)}:\n" + "\n".join(rows)


@mcp.tool()
def gsg_collection(code: str, kind: str = "") -> str:
    """List every asset of one collection, e.g. MC005 (Tech materials) or HC005 (HDRI Studio vol.2)."""
    up = code.upper()
    rows = [
        _describe(a)
        for k, items in _index().items()
        if not kind or k == kind
        for a in items
        if a.coll == up
    ]
    if not rows:
        return f"no assets in collection {up}"
    return f"{len(rows)} asset(s) in {up}:\n" + "\n".join(rows)


def _colorspace(map_name: str) -> str:
    # Colour maps are sRGB; data maps (roughness, normal, height, metallic, weights) are Raw.
    return "sRGB" if map_name.lower().endswith("color") else "Raw"


@mcp.tool()
def gsg_show(code: str) -> str:
    """Full card of one asset: files, texture maps by resolution with colour space, .gsgm parameters
    (Autodesk Standard Surface, maps 1:1 onto Redshift Standard Material), preview path, FBX/EXR paths."""
    a = _find_asset(code)
    folder = Path(a.path)
    maps: dict[str, dict[str, str]] = {}
    other: list[str] = []
    preview = None
    gsgm: dict[str, Any] | None = None
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        low = f.name.lower()
        if low.endswith(".gsgm"):
            try:
                gsgm = json.loads(_read_text(f))
            except (OSError, ValueError):
                gsgm = None
        elif "_preview." in low:
            preview = str(f)
        else:
            m = MAP_RE.search(f.name)
            if m and a.kind in ("materials", "textures", "hdris"):
                maps.setdefault(m["map"].lower(), {})[m["res"].lower()] = str(f)
            else:
                other.append(str(f))

    def res_key(r: str) -> int:
        return int(r[:-1]) if r[:-1].isdigit() else 0

    card: dict[str, Any] = {
        "code": a.code, "name": a.name, "kind": a.kind, "collection": a.coll,
        "folder": a.path, "preview": preview,
    }
    if maps:
        card["maps"] = {
            name: {
                "colorspace": _colorspace(name),
                "resolutions": sorted(files, key=res_key, reverse=True),
                "best": files[max(files, key=res_key)],
                "files": files,
            }
            for name, files in sorted(maps.items())
        }
    if gsgm:
        params = gsgm.get("params", gsgm)
        card["gsgm"] = {"name": gsgm.get("name"), "params": params}
    if other:
        card["files"] = other
    if a.kind == "materials":
        card["redshift_notes"] = [
            "standard_surface names map 1:1 to RS Standard Material (base_color, specular_roughness, specular_IOR, coat, sheen, subsurface, transmission...)",
            "transmission depth: GSG is in metres, Redshift in mm (multiply by 1000)",
            "no usable UVs: use TriPlanar in object space; tile size in mm matched to the real object size",
            "normal map = tangent space, via RS Bump Map (input type Tangent-Space Normal), texture colour space Raw",
            "texture levels: 4k close-up, 2k/1k mid shot, reduced copies for scatter; copy reduced maps into the task's Assets/Textures, never write to the library",
        ]
    return json.dumps(card, ensure_ascii=False, indent=1)


@mcp.tool()
def gsg_preview(code: str, max_px: int = 640) -> Image:
    """See what an asset looks like (its _preview image, downscaled)."""
    a = _find_asset(code)
    folder = Path(a.path)
    cands = sorted(folder.glob("*_preview.*")) or sorted(
        f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXT
    )
    if not cands:
        raise FileNotFoundError(f"{a.code} has no preview image")
    return _as_image(cands[0], max(128, min(max_px, 1600)))


@mcp.tool()
def gsg_sheet(kind: str = "materials", collection: str = "", page: int = 0) -> Any:
    """Contact sheets of previews from the vault (Agent/gsg_sheets/<kind>/<collection>_NN.jpg): a grid
    of a whole collection with code + name captions, the fastest way to choose by eye. Without a
    page it lists the available sheets; with page N it returns that sheet as an image."""
    folder = _vroot() / "Agent" / "gsg_sheets" / kind
    if not folder.is_dir():
        raise FileNotFoundError(f"No sheets for '{kind}' (Agent/gsg_sheets/{kind}); ask the user to run gsg_tools.py sheets")
    files = sorted(f.name for f in folder.glob("*.jpg") if not collection or f.name.upper().startswith(collection.upper() + "_"))
    if not page:
        return "\n".join(files) or "no sheets match"
    want = [f for f in files if f.rsplit("_", 1)[-1].split(".")[0].lstrip("0") == str(page)]
    if not want:
        return "sheet not found; available:\n" + "\n".join(files)
    return _as_image(folder / want[0], 1800)


# ------------------------------------------------------------------ Redshift material in Cinema 4D

# The user's own loader (GSG asset -> Redshift Standard node material). Used as is, not rewritten.
C4D_LOADER = "Projects/claude/Yogo_pro_keyboard/C4D/src/ykb_gsg.py"
ASCII_NAME = re.compile(r"^[A-Za-z0-9_.\- ]{1,60}$")
CODE_RE = re.compile(r"^[A-Z]{2}\d{3}_[A-Z]\d{3}$")


def _num(v: Any, label: str, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not (lo <= float(v) <= hi):
        raise ValueError(f"{label} must be a number in {lo}..{hi}")
    return float(v)


def _tuple3(v: Any, label: str, lo: float, hi: float) -> list[float]:
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise ValueError(f"{label} must be a list of 3 numbers")
    return [_num(x, label, lo, hi) for x in v]


def _clean_spec(raw: dict[str, Any]) -> dict[str, Any]:
    allowed = {"code", "name", "tile_mm", "space", "tint", "sss", "viewport_color", "apply_to"}
    extra = set(raw) - allowed
    if extra:
        raise ValueError(f"unknown keys {sorted(extra)}; allowed: {sorted(allowed)}")
    code = str(raw.get("code", "")).strip().upper()
    if not CODE_RE.match(code):
        raise ValueError(f"code must look like MC005_A012, got '{code}'")
    asset = _find_asset(code)
    if asset.kind != "materials":
        raise ValueError(f"{code} is a {asset.kind} asset, not a material")
    name = str(raw.get("name") or f"GSG_{code}")
    if not ASCII_NAME.match(name):
        raise ValueError(f"material name '{name}': use ASCII letters, digits, space, _ . - only (non-ASCII text crashes the C4D bridge)")
    space = str(raw.get("space", "object"))
    if space not in ("object", "world"):
        raise ValueError("space must be 'object' (moving parts) or 'world' (static parts / instances)")
    sss = raw.get("sss")
    if sss is not None and sss is not False and sss is not True:
        sss = _tuple2(sss, "sss")
    targets = [str(t) for t in (raw.get("apply_to") or [])]
    for t in targets:
        if not ASCII_NAME.match(t):
            raise ValueError(f"object name '{t}' in apply_to must be ASCII")
    return {
        "code": code,
        "name": name,
        "tile": _num(raw.get("tile_mm", 50.0), "tile_mm", 0.1, 100000),
        "space": space,
        "tint": None if raw.get("tint") is None else _tuple3(raw["tint"], "tint", 0.0, 4.0),
        "sss": sss,
        "vp": None if raw.get("viewport_color") is None else _tuple3(raw["viewport_color"], "viewport_color", 0, 255),
        "apply": targets,
    }


def _tuple2(v: Any, label: str) -> list[float]:
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        raise ValueError(f"{label} must be true, false, null or [amount, radius_mm]")
    return [_num(v[0], label, 0.0, 1.0), _num(v[1], label, 0.0, 100.0)]


def build_c4d_material_script(specs: list[dict[str, Any]], loader_dir: str, module: str, document: str) -> str:
    """Python for the C4D bridge's execute_python. ASCII only, no 'import os' / exec / eval
    (the bridge rejects those), never saves or renders."""
    body = f'''import sys
import importlib
LOADER = {loader_dir!r}
if LOADER not in sys.path:
    sys.path.insert(0, LOADER)
import {module} as gsg
importlib.reload(gsg)

DOC_NAME = {document!r}
SPECS = {specs!r}

target = doc
if DOC_NAME:
    target = None
    d = c4d.documents.GetFirstDocument()
    while d:
        if d.GetDocumentName() == DOC_NAME:
            target = d
            break
        d = d.GetNext()
    if target is None:
        raise RuntimeError("document is not open: " + DOC_NAME)


def find_obj(o, name):
    while o:
        if o.GetName() == name:
            return o
        hit = find_obj(o.GetDown(), name)
        if hit:
            return hit
        o = o.GetNext()
    return None


print("document: " + str(target.GetDocumentName()))
for s in SPECS:
    mats = [m for m in target.GetMaterials() if m.GetName() == s["name"]]
    if mats:
        mat = mats[0]
        print("exists, reused: " + s["name"])
    else:
        vp = tuple(s["vp"]) if s["vp"] else None
        tint = tuple(s["tint"]) if s["tint"] else None
        sss = tuple(s["sss"]) if isinstance(s["sss"], list) else s["sss"]
        mat = gsg.make(target, s["name"], s["code"], s["tile"], s["space"], tint, sss, vp)
        print("created: " + s["name"] + " <- " + s["code"] + " tile " + str(s["tile"]) + " mm, " + s["space"] + " space")
    for oname in s["apply"]:
        obj = find_obj(target.GetFirstObject(), oname)
        if obj is None:
            print("object not found: " + oname)
            continue
        tag = obj.MakeTag(c4d.Ttexture)
        tag[c4d.TEXTURETAG_MATERIAL] = mat
        print("  applied to: " + oname)
c4d.EventAdd()
print("done")
'''
    body.encode("ascii")  # fails loudly if anything non-ASCII slipped in
    for banned in ("import os", "from os import", "os.system", "subprocess", "exec(", "eval("):
        if banned in body:
            raise ValueError(f"generated script contains '{banned}', which the C4D bridge rejects")
    return body


@mcp.tool()
def c4d_material_script(materials: list[dict[str, Any]], document: str = "") -> str:
    """EXPERIMENTAL - the first live run closed the C4D bridge connection (cause not found yet). Ask the user
    before running the result, and never in a scene with unsaved work.
    Build the Python script that creates Redshift materials from GSG library assets in Cinema 4D,
    using the user's own loader (Projects/claude/Yogo_pro_keyboard/C4D/src/ykb_gsg.py). Run the returned
    text with c4d__execute_python_script. Nothing is executed here.

    materials: list of {code, name?, tile_mm?, space?, tint?, sss?, viewport_color?, apply_to?}
      code            GSG material code, e.g. 'MC005_A004' (see gsg_find)
      name            material name in C4D, ASCII only (default 'GSG_<code>')
      tile_mm         one texture repeat in mm, match the real part size (default 50)
      space           'object' for moving parts, 'world' for static parts / instances (default 'object')
      tint            [r, g, b] multiplier on the base colour map, e.g. [0.83, 0.69, 0.61]
      sss             null = automatic (plastics with scatter maps), false = off, [amount, radius_mm]
      viewport_color  [r, g, b] 0..255, colour in the C4D viewport
      apply_to        names of objects that get a texture tag with this material
    document: name of the open .c4d document (e.g. 'Yogo_pro_keyboard_v005.c4d'); empty = the active one.
    Prefer naming the document: the active one may not be the scene you mean. An existing material with the
    same name is reused, never overwritten."""
    if not materials:
        raise ValueError("materials is empty")
    if len(materials) > 40:
        raise ValueError("at most 40 materials per script; split the work")
    if document and not re.match(r"^[A-Za-z0-9_.\- ]{1,120}\.c4d$", document):
        raise ValueError("document must be an ASCII file name ending in .c4d")
    loader = _vpath(C4D_LOADER)
    if not loader.is_file():
        raise FileNotFoundError(f"Loader not found in the vault: {C4D_LOADER}")
    specs = [_clean_spec(m) for m in materials]
    return build_c4d_material_script(specs, str(loader.parent), loader.stem, document)


@mcp.tool()
def gsg_reindex() -> str:
    """Rescan the library folders (after the user downloaded new assets)."""
    global _INDEX
    _INDEX = None
    return gsg_stats()


if __name__ == "__main__":
    mcp.run()
