@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PY=%ROOT%.venv\Scripts\python.exe"
) else (
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
        set "PY=py -3"
    ) else (
        set "PY=python"
    )
)

echo Using: %PY%
"%PY%" -m bxsimulator ui %*
