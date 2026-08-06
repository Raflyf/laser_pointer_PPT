@echo off
setlocal
cd /d "%~dp0"

echo ===========================================
echo Pointer PPT Server
echo ===========================================

REM --- 1. Siapkan virtualenv lokal proyek ---
set "VENV=%~dp0.venv"
set "PYEXE=%VENV%\Scripts\python.exe"

if not exist "%VENV%\Scripts\activate.bat" (
    echo [Setup] Membuat virtualenv di .venv ...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [Error] Gagal membuat venv. Pastikan Python 3.9+ terinstall dan di PATH.
        pause
        exit /b 1
    )
)

REM --- 2. Cek dependensi; install hanya yang belum ada ---
echo [Setup] Memeriksa dependensi ...
"%PYEXE%" -c "import flask, flask_socketio, pyautogui, pygetwindow, psutil, qrcode, eventlet, pyngrok" 2>nul
if errorlevel 1 (
    echo [Setup] Menginstall dependensi dari requirements.txt ...
    "%PYEXE%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [Error] Gagal install dependensi.
        pause
        exit /b 1
    )
) else (
    echo [Setup] Semua dependensi sudah ada. Skip install.
)

REM --- 3. Jalankan server ---
echo ===========================================
"%PYEXE%" app.py

pause
