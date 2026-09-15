@echo off
title LoomTrack Reminder Scheduler
cd /d "%~dp0"

echo ==============================================
echo   LoomTrack - Reminder Scheduler
echo ==============================================
echo.
echo   [1] Run checks once now   (recommended)
echo   [2] Run always-on daily   (auto 8:00 AM)
echo.
set /p choice="Choose 1 or 2: "

if "%choice%"=="1" (
  python scheduler.py --now > scheduler-log.txt 2>&1
  type scheduler-log.txt
) else (
  echo Scheduler started. Logs: scheduler-log.txt
  python scheduler.py > scheduler-log.txt 2>&1
)

echo.
echo Done. See scheduler-log.txt for details.
pause