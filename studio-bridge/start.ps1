# Starts the Studio Bridge gateway and a tunnel, and prints the connector URL
# to paste into claude.ai. Keep this window open; Ctrl+C stops everything.
#
#   start.cmd                                   quick Cloudflare tunnel (no account, URL changes every run)
#   start.cmd -NgrokDomain my-name.ngrok-free.app   ngrok static domain (URL never changes)
#   start.cmd -PublicUrl https://mcp.example.com    you run your own tunnel to 127.0.0.1:8765

param(
    [int]$Port = 8765,
    [string]$NgrokDomain = "",
    [string]$PublicUrl = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

$cfgPath = Join-Path $Root "gateway\servers.json"
$gwPy = Join-Path $Root "gateway\.venv\Scripts\python.exe"
if (-not (Test-Path $cfgPath) -or -not (Test-Path $gwPy)) { throw "Run install.cmd first." }
$token = (Get-Content $cfgPath -Raw | ConvertFrom-Json).token

# Log lines are shown on screen when something fails: never print the secret token.
function Show-Log($path, $lines = 25) {
    if (-not (Test-Path $path)) { Write-Host "    (no log file: $path)" -ForegroundColor DarkGray; return }
    Get-Content $path -Tail $lines -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host ("    | " + $_.Replace($token, "<TOKEN>")) -ForegroundColor DarkGray
    }
}

function Stop-Tree($id) { & taskkill /T /F /PID $id 2>&1 | Out-Null }

# A previous run that was not stopped cleanly keeps the port and a stale tunnel.
# That looks fine on screen but is the old code and an old address - clear it first.
Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -like "$Root*" } | ForEach-Object { Stop-Tree $_.ProcessId }
$owners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
foreach ($id in $owners) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -like "*gateway.py*") {
        Write-Host "Stopping a previous gateway that was still running (pid $id)." -ForegroundColor Yellow
        Stop-Tree $id
        Start-Sleep -Seconds 1
    } else {
        throw "Port $Port is used by another program (pid $id). Close it, or run: start.cmd -Port 8790"
    }
}

# name -> process, so a failure can say which part died.
$procs = [ordered]@{}
function Start-Part($name, $file, $arguments, $errLog, $outLog) {
    $p = Start-Process -FilePath $file -ArgumentList $arguments -PassThru -WindowStyle Hidden `
        -RedirectStandardError $errLog -RedirectStandardOutput $outLog
    $null = $p.Handle  # keeps ExitCode readable after the process ends
    $script:procs[$name] = @{ Process = $p; Log = $errLog; Out = $outLog }
}

try {
    Write-Host "Starting gateway on 127.0.0.1:$Port ..." -ForegroundColor Cyan
    $gwLog = Join-Path $Logs "gateway.log"
    Start-Part "gateway" $gwPy @("`"$(Join-Path $Root 'gateway\gateway.py')`"", "--config", "`"$cfgPath`"", "--port", $Port) `
        $gwLog (Join-Path $Logs "gateway.out.log")

    $up = $false
    for ($i = 0; $i -lt 40 -and -not $up; $i++) {
        Start-Sleep -Milliseconds 500
        if ($procs["gateway"].Process.HasExited) { break }
        try { $c = New-Object Net.Sockets.TcpClient("127.0.0.1", $Port); $c.Close(); $up = $true } catch { }
    }
    if (-not $up) { Show-Log $gwLog; throw "The gateway did not start (log above)." }

    if ($PublicUrl) {
        $base = $PublicUrl.TrimEnd("/")
    } elseif ($NgrokDomain) {
        if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) { throw "ngrok not found: winget install ngrok.ngrok; ngrok config add-authtoken <token>" }
        $tLog = Join-Path $Logs "tunnel.log"
        Start-Part "tunnel" "ngrok" @("http", "--url=$NgrokDomain", "$Port", "--log=stdout") (Join-Path $Logs "tunnel.err.log") $tLog
        $base = "https://$NgrokDomain"
    } else {
        $cf = Join-Path $Root "bin\cloudflared.exe"
        $tLog = Join-Path $Logs "tunnel.log"
        Remove-Item $tLog -ErrorAction SilentlyContinue
        Start-Part "tunnel" $cf @("tunnel", "--no-autoupdate", "--protocol", "http2", "--url", "http://127.0.0.1:$Port") `
            $tLog (Join-Path $Logs "tunnel.out.log")
        $base = $null
        for ($i = 0; $i -lt 60 -and -not $base; $i++) {
            Start-Sleep -Seconds 1
            if ($procs["tunnel"].Process.HasExited) { break }
            if (Test-Path $tLog) {
                $m = Select-String -Path $tLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
                if ($m) { $base = $m.Matches[0].Value }
            }
        }
        if (-not $base) { Show-Log $tLog; throw "The tunnel did not come up (log above)." }
        # The address is printed before the tunnel accepts traffic. cloudflared logs
        # "Registered tunnel connection" when it does (asking the public address from
        # this PC is unreliable: Windows caches a failed DNS lookup for minutes).
        Write-Host "Waiting for the tunnel to connect (up to 30 s) ..." -ForegroundColor Cyan
        $reach = $false
        for ($i = 0; $i -lt 30 -and -not $reach; $i++) {
            if ($procs["tunnel"].Process.HasExited) { break }
            if (Select-String -Path $tLog -Pattern 'Registered tunnel connection' -Quiet) { $reach = $true } else { Start-Sleep -Seconds 1 }
        }
        if (-not $reach) { Write-Host "The tunnel has not reported a connection yet; continuing anyway." -ForegroundColor Yellow }
    }

    $url = "$base/$token/mcp"
    Set-Content -Path (Join-Path $Root "connector-url.txt") -Value $url
    try { Set-Clipboard -Value $url } catch { }

    Write-Host ""
    Write-Host "Connector URL (copied to clipboard, also in connector-url.txt):" -ForegroundColor Green
    Write-Host "  $url" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "claude.ai -> Settings -> Connectors -> Add custom connector -> paste the URL."
    if (-not $NgrokDomain -and -not $PublicUrl) {
        Write-Host "Quick tunnel URL changes on every start: update the connector each time, or use -NgrokDomain." -ForegroundColor DarkYellow
    }
    Write-Host "Logs: $Logs.  Ctrl+C to stop."

    while ($true) {
        Start-Sleep -Seconds 2
        foreach ($name in $procs.Keys) {
            $part = $procs[$name]
            if ($part.Process.HasExited) {
                Write-Host ""
                Write-Host "!! The $name stopped by itself (exit code $($part.Process.ExitCode)). Last log lines:" -ForegroundColor Red
                Show-Log $part.Log
                Show-Log $part.Out 10
                throw "$name stopped (details above). Close this window and run start.cmd again."
            }
        }
    }
}
finally {
    # /T also stops the per-app MCP servers the gateway spawned.
    foreach ($part in $procs.Values) { if (-not $part.Process.HasExited) { Stop-Tree $part.Process.Id } }
    Write-Host "Stopped."
}
