param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$toolUrl = 'http://127.0.0.1:8501/'
function Test-Workbench {
    try {
        $reply = Invoke-WebRequest ($toolUrl + '_stcore/health') -UseBasicParsing -TimeoutSec 2
        return $reply.StatusCode -eq 200 -and $reply.Content.Trim() -eq 'ok'
    } catch { return $false }
}
try {
    if (-not (Test-Workbench)) {
        $pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $pythonPath)) {
            throw 'Run VideoSubtitleExtraction.Setup.ps1 once to install the Python environment first.'
        }
        $dataPath = Join-Path $PSScriptRoot 'data'
        New-Item -ItemType Directory -Force -Path $dataPath | Out-Null
        Start-Process -FilePath $pythonPath -ArgumentList @('-m','streamlit','run','app.py','--server.address','127.0.0.1','--server.port','8501','--server.headless','true') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dataPath 'server.stdout.log') -RedirectStandardError (Join-Path $dataPath 'server.stderr.log')
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            if (Test-Workbench) { break }
            Start-Sleep -Milliseconds 500
        }
        if (-not (Test-Workbench)) { throw 'Startup failed. Check data/server.stderr.log.' }
    }
    if (-not $NoBrowser) { Start-Process $toolUrl }
    Write-Host ('Workbench ready: ' + $toolUrl)
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
