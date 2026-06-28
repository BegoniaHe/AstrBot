param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("run-backend", "run-dashboard", "stop-backend", "stop-dashboard", "status", "clean")]
    [string]$Action
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $repoRoot ".make"
$dashboardDir = Join-Path $repoRoot "dashboard"
$backendPidFile = Join-Path $runDir "backend.pid"
$dashboardPidFile = Join-Path $runDir "dashboard.pid"
$backendLog = Join-Path $repoRoot "backend_run.log"
$backendErrLog = Join-Path $repoRoot "backend_run.err.log"
$dashboardLog = Join-Path $repoRoot "frontend_run.log"
$dashboardErrLog = Join-Path $repoRoot "frontend_run.err.log"
$dashboardDist = Join-Path $dashboardDir "dist"
$dashboardViteCache = Join-Path $dashboardDir "node_modules/.vite"

function Ensure-RunDir {
    if (-not (Test-Path $runDir)) {
        New-Item -ItemType Directory -Path $runDir | Out-Null
    }
}

function Remove-IfExists {
    param([string]$Path)
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function New-EmptyFile {
    param([string]$Path)

    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    Set-Content -Path $Path -Value "" -NoNewline
}

function Invoke-TaskKill {
    param([int]$TargetPid)

    $taskkill = Start-Process `
        -FilePath "taskkill.exe" `
        -ArgumentList @("/PID", $TargetPid, "/T", "/F") `
        -WindowStyle Hidden `
        -Wait `
        -PassThru

    if ($taskkill.ExitCode -in @(0, 128, 255)) {
        return
    }

    if (-not (Get-Process -Id $TargetPid -ErrorAction SilentlyContinue)) {
        return
    }

    throw "taskkill failed for PID $TargetPid with exit code $($taskkill.ExitCode)"
}

function Stop-FromPidFile {
    param([string]$PidFile)
    if (-not (Test-Path $PidFile)) {
        return
    }

    $pidValue = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pidValue) {
        try {
            Invoke-TaskKill -Pid ([int]$pidValue)
        }
        catch {
            if (Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue) {
                throw
            }
        }
    }
    Remove-IfExists $PidFile
}

function Stop-ByPort {
    param([int]$Port)

    $pids = @()
    try {
        $pids += Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique
    }
    catch {
        $netstatLines = netstat -ano -p tcp | Select-String ":$Port "
        foreach ($line in $netstatLines) {
            $parts = ($line.Line -split "\s+") | Where-Object { $_ }
            if ($parts.Length -ge 5 -and $parts[3] -eq "LISTENING") {
                $pids += $parts[4]
            }
        }
    }

    $pids = $pids | Where-Object { $_ } | Select-Object -Unique
    foreach ($procId in $pids) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
        }
        catch {
            Invoke-TaskKill -Pid ([int]$procId)
        }
    }
}

function Start-ManagedProcess {
    param(
        [string]$PidFile,
        [string]$WorkingDirectory,
        [string]$Command,
        [string]$StdoutPath,
        [string]$StderrPath,
        [int]$WarmupSeconds
    )

    Ensure-RunDir
    Stop-FromPidFile -PidFile $PidFile
    Remove-IfExists $StdoutPath
    Remove-IfExists $StderrPath
    New-EmptyFile -Path $StdoutPath
    New-EmptyFile -Path $StderrPath

    $proc = Start-Process `
        -FilePath "powershell" `
        -ArgumentList @("-NoProfile", "-Command", $Command) `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -Path $PidFile -Value $proc.Id
    Start-Sleep -Seconds $WarmupSeconds
}

function Test-Url {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -Method Head -TimeoutSec 10
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 10
            return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
        }
        catch {
            return $false
        }
    }
}

function Show-DashboardCredentials {
    param(
        [string]$LogPath,
        [int]$TimeoutSeconds = 30
    )

    # The backend runs hidden with stdout redirected to the log, so the
    # initial username/password printed at startup never reaches this console.
    # Poll the log until the credentials banner shows up, then surface it.
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $pattern = "Initial username:|Initial password:|Change it after logging in|Username:"

    while ((Get-Date) -lt $deadline) {
        if (Test-Path $LogPath) {
            $lines = Get-Content -LiteralPath $LogPath -ErrorAction SilentlyContinue |
                Select-String -Pattern $pattern
            if ($lines) {
                Write-Host ""
                Write-Host "Dashboard credentials (from $(Split-Path -Leaf $LogPath)):"
                foreach ($line in $lines) {
                    Write-Host "  $($line.Line.Trim())"
                }
                Write-Host ""
                return
            }
        }
        Start-Sleep -Milliseconds 500
    }

    Write-Host "Dashboard credentials not found in $(Split-Path -Leaf $LogPath) yet."
    Write-Host "Check the log directly: $LogPath"
}

switch ($Action) {
    "run-backend" {
        Start-ManagedProcess `
            -PidFile $backendPidFile `
            -WorkingDirectory $repoRoot `
            -Command "Set-Location '$repoRoot'; uv run main.py" `
            -StdoutPath $backendLog `
            -StderrPath $backendErrLog `
            -WarmupSeconds 6
        Show-DashboardCredentials -LogPath $backendLog
    }
    "run-dashboard" {
        Start-ManagedProcess `
            -PidFile $dashboardPidFile `
            -WorkingDirectory $dashboardDir `
            -Command "Set-Location '$dashboardDir'; corepack pnpm dev" `
            -StdoutPath $dashboardLog `
            -StderrPath $dashboardErrLog `
            -WarmupSeconds 8
    }
    "stop-backend" {
        Stop-FromPidFile -PidFile $backendPidFile
        Stop-ByPort -Port 6185
        Remove-IfExists $backendPidFile
    }
    "stop-dashboard" {
        Stop-FromPidFile -PidFile $dashboardPidFile
        Stop-ByPort -Port 3000
        Remove-IfExists $dashboardPidFile
    }
    "status" {
        $backendOk = Test-Url -Url "http://127.0.0.1:6185/api/v1/openapi.json"
        $dashboardOk = Test-Url -Url "http://127.0.0.1:3000"

        Write-Host "Backend  : $(Split-Path -Leaf $backendPidFile) -> $(if ($backendOk) { 'up' } else { 'down' })"
        Write-Host "Dashboard: $(Split-Path -Leaf $dashboardPidFile) -> $(if ($dashboardOk) { 'up' } else { 'down' })"
    }
    "clean" {
        Stop-FromPidFile -PidFile $dashboardPidFile
        Stop-FromPidFile -PidFile $backendPidFile
        Stop-ByPort -Port 3000
        Stop-ByPort -Port 6185
        Remove-IfExists $runDir
        Remove-IfExists $backendLog
        Remove-IfExists $backendErrLog
        Remove-IfExists $dashboardLog
        Remove-IfExists $dashboardErrLog
        Remove-IfExists $dashboardDist
        Remove-IfExists $dashboardViteCache
    }
}
