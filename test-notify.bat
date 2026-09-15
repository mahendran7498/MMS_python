@echo off
title LoomTrack - Test SMS/WhatsApp/Email
cd /d "%~dp0"
python test_notify.py
echo.
pause