# Studio Bridge installer (Windows).
# Installs MCP servers for Cinema 4D, Houdini and Fusion, the gateway that
# joins them into one endpoint, and cloudflared for the tunnel.
# Safe to re-run: it updates what is already there and keeps your token.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 -FusionDll "D:\Fusion 20\fusionscript.dll"

param(
    [string]$Python = "",
    [string]$FusionDll = "",
    [switch]$SkipC4D,
    [switch]$SkipHoudini,
    [switch]$SkipFusion,
    [switch]$SkipNuke,
    [switch]$SkipWeaver,
    [string]$Vault = "G:\todoist_obsidian_claude",
    [string]$Gsg = "E:\assets\Greyscalegorilla Studio\assets\Greyscalegorilla_Library"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Apps = Join-Path $Root "apps"
New-Item -ItemType Directory -Force -Path $Apps, (Join-Path $Root "bin"), (Join-Path $Root "logs") | Out-Null

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Warn($msg) { Write-Host "    ! $msg" -ForegroundColor Yellow }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Info($msg) { Write-Host "    $msg ..." -ForegroundColor DarkGray }

# Clicking inside a classic console window enters "select" mode and freezes the script.
Write-Host "Tip: don't click inside this window while installing (press Esc if it looks stuck)." -ForegroundColor DarkYellow

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments | Out-Host  # keep tool output out of function return values
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Exe $($Arguments -join ' ')" }
}

# ---------------------------------------------------------------- prerequisites
Step "Checking prerequisites"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git not found. Install it: winget install Git.Git   (then reopen PowerShell)"
}
$PyExe = $null; $PyArgs = @()
if ($Python) { $PyExe = $Python }
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($v in "-3.12", "-3.11", "-3.13") {
        try { & py $v -c "import sys" 2>&1 | Out-Null } catch { }
        if ($LASTEXITCODE -eq 0) { $PyExe = "py"; $PyArgs = @($v); break }
    }
}
if (-not $PyExe -and (Get-Command python -ErrorAction SilentlyContinue)) { $PyExe = "python" }
if (-not $PyExe) { throw "Python 3.11+ not found. Install it: winget install Python.Python.3.12" }
$ver = & $PyExe @PyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$ver -lt [version]"3.11") { throw "Python $ver found, 3.11+ is required (winget install Python.Python.3.12)" }
Ok "git ok, Python $ver ($PyExe $PyArgs)"

function New-Venv($dir) {
    Info "preparing Python environment in $dir"
    $py = Join-Path $dir ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { Invoke-Checked $PyExe ($PyArgs + @("-m", "venv", (Join-Path $dir ".venv"))) }
    Invoke-Checked $py @("-m", "pip", "install", "-q", "--upgrade", "pip")
    return $py
}

function Sync-Repo($url, $dir) {
    Info "downloading $url"
    if (Test-Path (Join-Path $dir ".git")) {
        Invoke-Checked git @("-C", $dir, "checkout", "-q", "--", ".")  # drop our local patches before updating
        Invoke-Checked git @("-C", $dir, "pull", "-q", "--ff-only")
    } else {
        Invoke-Checked git @("clone", "-q", "--depth", "1", $url, $dir)
    }
}

$servers = [ordered]@{}

# ---------------------------------------------------------------- gateway
Step "Gateway"
$GwPy = New-Venv (Join-Path $Root "gateway")
Invoke-Checked $GwPy @("-m", "pip", "install", "--progress-bar", "on", "-r", (Join-Path $Root "gateway\requirements.txt"))
Ok "installed"

# ---------------------------------------------------------------- Cinema 4D
if (-not $SkipC4D) {
    Step "Cinema 4D MCP (github.com/ttiimmaacc/cinema4d-mcp)"
    $dir = Join-Path $Apps "cinema4d-mcp"
    Sync-Repo "https://github.com/ttiimmaacc/cinema4d-mcp.git" $dir
    $py = New-Venv $dir
    # cinema4d-mcp uses the mcp 1.x FastMCP API; mcp 2.x removed it.
    Invoke-Checked $py @("-m", "pip", "install", "--progress-bar", "on", "-e", $dir, "mcp>=1.2,<2")

    $plugin = Join-Path $dir "c4d_plugin\mcp_server_plugin.pyp"
    $prefs = Get-ChildItem (Join-Path $env:APPDATA "Maxon") -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*Cinema 4D*" -and $_.Name -notmatch '_[a-z]$' }  # skip _c/_x/_w (cmdline, team render)
    if (-not $prefs) {
        Warn "Cinema 4D preferences folder not found in %APPDATA%\Maxon (start C4D once, then re-run)."
        Warn "Or copy manually: $plugin -> <C4D prefs>\plugins\cinema4d-mcp\"
    }
    foreach ($p in $prefs) {
        $dst = Join-Path $p.FullName "plugins\cinema4d-mcp"
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Copy-Item $plugin $dst -Force
        Ok "plugin -> $dst"
    }
    $servers["c4d"] = [ordered]@{
        command = $py; args = @("main.py"); cwd = $dir; timeout = 180
        env = [ordered]@{ C4D_HOST = "127.0.0.1"; C4D_PORT = "5555" }
    }
}

# ---------------------------------------------------------------- Houdini
if (-not $SkipHoudini) {
    Step "Houdini MCP (github.com/eetumartola/houdini-mcp)"
    $dir = Join-Path $Apps "houdini-mcp"
    Sync-Repo "https://github.com/eetumartola/houdini-mcp.git" $dir
    $py = New-Venv $dir
    # The repo's pyproject.toml is malformed, so install the dependency directly.
    Invoke-Checked $py @("-m", "pip", "install", "--progress-bar", "on", "mcp[cli]>=1.2,<2")
    # Fix the repo for current mcp 1.x and move it off port 9876, which other Houdini
    # bridges commonly use (two listeners on one port made Houdini hang on every call).
    $HPort = "19876"
    $srv = Join-Path $dir "houdini_mcp_server.py"
    $code = Get-Content $srv -Raw -Encoding UTF8
    $code = $code -replace '(\n\s*)description=', '$1instructions='   # FastMCP(description=) was renamed
    $code = $code -replace 'port=9876', 'port=int(os.environ.get("HOUDINI_PORT", "9876"))'
    Set-Content -Path $srv -Value $code -NoNewline -Encoding UTF8
    $mod = Join-Path $dir "houdini_mcp.py"
    $code = Get-Content $mod -Raw -Encoding UTF8
    Set-Content -Path $mod -Value ($code -replace 'port=9876', "port=$HPort") -NoNewline -Encoding UTF8
    Invoke-Checked $py @((Join-Path $PSScriptRoot "patches\patch_houdini.py"), $srv)   # retry on dead socket, return plugin output
    Ok "patched houdini-mcp (mcp 1.x fix, port $HPort, retry)"

    $docs = [Environment]::GetFolderPath("MyDocuments")
    $hPrefs = Get-ChildItem $docs -Directory -Filter "houdini*" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^houdini\d+\.\d+$' }
    if (-not $hPrefs) {
        Warn "No Documents\houdiniXX.X folder found (start Houdini once, then re-run)."
    }
    $shelf = @'
<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <toolshelf name="studio_bridge" label="Studio Bridge">
    <memberTool name="studio_bridge_mcp_start"/>
    <memberTool name="studio_bridge_mcp_stop"/>
  </toolshelf>
  <tool name="studio_bridge_mcp_start" label="MCP Start" icon="MISC_python">
    <script scriptType="python"><![CDATA[import houdini_mcp
houdini_mcp.start_server()
hou.ui.setStatusMessage("HoudiniMCP listening on localhost:19876")]]></script>
  </tool>
  <tool name="studio_bridge_mcp_stop" label="MCP Stop" icon="MISC_python">
    <script scriptType="python"><![CDATA[import houdini_mcp
houdini_mcp.stop_server()]]></script>
  </tool>
</shelfDocument>
'@
    foreach ($h in $hPrefs) {
        # Different Houdini builds use different Python versions; the module is tiny, put it in each.
        foreach ($pv in "python3.9libs", "python3.10libs", "python3.11libs", "python3.12libs") {
            $dst = Join-Path $h.FullName $pv
            New-Item -ItemType Directory -Force -Path $dst | Out-Null
            Copy-Item (Join-Path $dir "houdini_mcp.py") $dst -Force
        }
        $tb = Join-Path $h.FullName "toolbar"
        New-Item -ItemType Directory -Force -Path $tb | Out-Null
        Set-Content -Path (Join-Path $tb "studio_bridge.shelf") -Value $shelf -Encoding UTF8
        Ok "module + 'Studio Bridge' shelf -> $($h.FullName)"
    }
    $servers["houdini"] = [ordered]@{
        command = $py; args = @("houdini_mcp_server.py"); cwd = $dir; timeout = 300
        env = [ordered]@{ HOUDINI_PORT = $HPort }
    }
}

# ---------------------------------------------------------------- Fusion
if (-not $SkipFusion) {
    Step "Fusion MCP (github.com/bigsbypuglise/fusion-studio-mcp)"
    $dir = Join-Path $Apps "fusion-studio-mcp"
    Sync-Repo "https://github.com/bigsbypuglise/fusion-studio-mcp.git" $dir
    $py = New-Venv $dir
    Invoke-Checked $py @("-m", "pip", "install", "--progress-bar", "on", "-e", $dir)

    if (-not $FusionDll) {
        $cands = @()
        $bmd = Join-Path $env:ProgramFiles "Blackmagic Design"
        if (Test-Path $bmd) {
            $cands = @(Get-ChildItem $bmd -Recurse -Depth 2 -Filter "fusionscript.dll" -ErrorAction SilentlyContinue |
                Sort-Object FullName -Descending)
        }
        # Prefer standalone Fusion Studio (newest first), fall back to DaVinci Resolve's copy.
        $pick = @($cands | Where-Object { $_.FullName -match '\\Fusion[^\\]*\\' }) + $cands
        if ($pick) { $FusionDll = $pick[0].FullName }
    }
    if ($FusionDll -and (Test-Path $FusionDll)) {
        Ok "fusionscript.dll: $FusionDll"
    } else {
        Warn "fusionscript.dll not found. Re-run with: install.ps1 -FusionDll 'C:\...\fusionscript.dll'"
    }
    $shim = Join-Path $Root "fusion-shim"
    $servers["fusion"] = [ordered]@{
        command = $py; args = @("-m", "fusion_mcp.server"); cwd = $dir; timeout = 600
        env = [ordered]@{
            PYTHONPATH        = "$shim;$(Join-Path $dir 'src')"
            FUSION_SCRIPT_LIB = $shim
            FUSION_DLL        = "$FusionDll"
            FUSION_APP_NAME   = "Fusion"
            FUSION_MCP_LOG_DIR = (Join-Path $Root "logs")
        }
    }
}

# ---------------------------------------------------------------- Nuke
if (-not $SkipNuke) {
    Step "Nuke MCP server (github.com/kleer001/nuke-mcp)"
    $dir = Join-Path $Apps "nuke-mcp"
    Sync-Repo "https://github.com/kleer001/nuke-mcp.git" $dir
    $py = New-Venv $dir
    Invoke-Checked $py @("-m", "pip", "install", "--progress-bar", "on", "-e", $dir)
    # Only the server side is installed here. The panel inside Nuke ("NukeMCP", port 54321)
    # is the addon from the same project and is started from Nuke itself.
    $servers["nuke"] = [ordered]@{
        command = $py
        args    = @("-c", "from nukemcp.server import main; main()", "--port", "54321")
        cwd     = $dir; timeout = 300
    }
}

# ---------------------------------------------------------------- Weaver (vault + GSG library)
if (-not $SkipWeaver) {
    Step "Weaver server (Obsidian vault + GSG library)"
    $dir = Join-Path $Root "weaver-server"
    $py = New-Venv $dir
    Invoke-Checked $py @("-m", "pip", "install", "--progress-bar", "on", "mcp>=1.26,<2", "pillow")
    if (-not (Test-Path $Vault)) { Warn "Vault folder not found: $Vault  (re-run with -Vault 'X:\path')" } else { Ok "vault: $Vault" }
    if (-not (Test-Path $Gsg))   { Warn "GSG library not found: $Gsg  (re-run with -Gsg 'X:\path')" } else { Ok "GSG library: $Gsg" }
    $servers["weaver"] = [ordered]@{
        command = $py; args = @("weaver_server.py"); cwd = $dir; timeout = 120
        env = [ordered]@{ WEAVER_VAULT = $Vault; WEAVER_GSG = $Gsg; PYTHONUTF8 = "1" }
    }
}

# ---------------------------------------------------------------- cloudflared
Step "cloudflared (tunnel)"
$cf = Join-Path $Root "bin\cloudflared.exe"
if (-not (Test-Path $cf)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -OutFile $cf `
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
}
Ok $cf

# ---------------------------------------------------------------- config
Step "Writing gateway config"
$cfgPath = Join-Path $Root "gateway\servers.json"
$token = $null
if (Test-Path $cfgPath) {
    try { $token = (Get-Content $cfgPath -Raw | ConvertFrom-Json).token } catch { }
}
if (-not $token) {
    $bytes = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $token = -join ($bytes | ForEach-Object { $_.ToString("x2") })
}
$cfg = [ordered]@{ token = $token; servers = $servers }
Set-Content -Path $cfgPath -Value ($cfg | ConvertTo-Json -Depth 6) -Encoding UTF8
Ok "$cfgPath  (the token in it is your password - keep it private)"

Write-Host "`nDone. Next: open C4D / Houdini / Fusion, start their MCP listeners (see README), then run start.cmd" -ForegroundColor Green
