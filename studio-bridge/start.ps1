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

$procs = @()
try {
    Write-Host "Starting gateway on 127.0.0.1:$Port ..." -ForegroundColor Cyan
    $gwLog = Join-Path $Logs "gateway.log"
    $procs += Start-Process -FilePath $gwPy -PassThru -WindowStyle Hidden `
        -ArgumentList @("`"$(Join-Path $Root 'gateway\gateway.py')`"", "--config", "`"$cfgPath`"", "--port", $Port) `
        -RedirectStandardError $gwLog -RedirectStandardOutput (Join-Path $Logs "gateway.out.log")

    $up = $false
    for ($i = 0; $i -lt 40 -and -not $up; $i++) {
        Start-Sleep -Milliseconds 500
        if ($procs[0].HasExited) { break }
        try { $c = New-Object Net.Sockets.TcpClient("127.0.0.1", $Port); $c.Close(); $up = $true } catch { }
    }
    if (-not $up) { Get-Content $gwLog -Tail 30; throw "Gateway did not start (see $gwLog)" }

    if ($PublicUrl) {
        $base = $PublicUrl.TrimEnd("/")
    } elseif ($NgrokDomain) {
        if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) { throw "ngrok not found: winget install ngrok.ngrok; ngrok config add-authtoken <token>" }
        $procs += Start-Process -FilePath "ngrok" -PassThru -WindowStyle Hidden `
            -ArgumentList @("http", "--url=$NgrokDomain", "$Port", "--log=stdout") `
            -RedirectStandardOutput (Join-Path $Logs "tunnel.log")
        $base = "https://$NgrokDomain"
    } else {
        $cf = Join-Path $Root "bin\cloudflared.exe"
        $tLog = Join-Path $Logs "tunnel.log"
        Remove-Item $tLog -ErrorAction SilentlyContinue
        $procs += Start-Process -FilePath $cf -PassThru -WindowStyle Hidden `
            -ArgumentList @("tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:$Port") `
            -RedirectStandardError $tLog -RedirectStandardOutput (Join-Path $Logs "tunnel.out.log")
        $base = $null
        for ($i = 0; $i -lt 60 -and -not $base; $i++) {
            Start-Sleep -Seconds 1
            if (Test-Path $tLog) {
                $m = Select-String -Path $tLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
                if ($m) { $base = $m.Matches[0].Value }
            }
        }
        if (-not $base) { Get-Content $tLog -Tail 30; throw "Tunnel did not come up (see $tLog)" }
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
        foreach ($p in $procs) {
            if ($p.HasExited) { throw "$($p.ProcessName) exited (code $($p.ExitCode)); see logs in $Logs" }
        }
    }
}
finally {
    # /T also stops the per-app MCP servers the gateway spawned.
    foreach ($p in $procs) { if ($p -and -not $p.HasExited) { & taskkill /T /F /PID $p.Id 2>&1 | Out-Null } }
    Write-Host "Stopped."
}
