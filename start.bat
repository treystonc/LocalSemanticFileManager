@echo off
REM Socrates - Local Semantic File Manager
REM Start both Streamlit UI and File Watcher

echo Starting Socrates...
echo.

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Start watcher in background
echo [1/2] Starting File Watcher...
start "Socrates Watcher" cmd /k "call .venv\Scripts\activate.bat && python -m src.main watch"

REM Wait a moment for watcher to start
timeout /t 2 /nobreak >nul

REM Start Streamlit UI
echo [2/2] Starting Streamlit UI...
start "Socrates UI" call .venv\Scripts\activate.bat && streamlit run ui/app.py

echo.
echo Socrates is starting!
echo.
echo - Watcher: Running in separate window
echo - UI: Will open in browser shortly
echo.
echo Press any key to close this window (watcher and UI will continue running)...
pause >nul
