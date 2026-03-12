# Socrates - Local Semantic File Manager
# Start both Streamlit UI and File Watcher

$venvPath = Join-Path $PSScriptRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"
$streamlitPath = Join-Path $venvPath "Scripts\streamlit.exe"

Write-Host "Starting Socrates..." -ForegroundColor Green
Write-Host ""

# Check if venv exists
if (-not (Test-Path $pythonPath)) {
    Write-Host "Virtual environment not found at: $venvPath" -ForegroundColor Red
    Write-Host "Please create the venv first:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Start watcher in background
Write-Host "[1/2] Starting File Watcher..." -ForegroundColor Cyan
Start-Process -FilePath $pythonPath -ArgumentList "-m src.main watch" -WindowStyle Normal -WorkingDirectory $PSScriptRoot

# Wait a moment for watcher to start
Start-Sleep -Seconds 2

# Start Streamlit UI
Write-Host "[2/2] Starting Streamlit UI..." -ForegroundColor Cyan
Start-Process -FilePath $streamlitPath -ArgumentList "run ui/app.py" -WindowStyle Normal -WorkingDirectory $PSScriptRoot

Write-Host ""
Write-Host "Socrates is starting!" -ForegroundColor Green
Write-Host ""
Write-Host "- Watcher: Running in background" -ForegroundColor Yellow
Write-Host "- UI: Will open in browser shortly" -ForegroundColor Yellow
Write-Host ""
