@echo off
title Hostel Management System (HMS) - Live Server
echo ============================================================
echo   HOSTEL MANAGEMENT SYSTEM (AKTU B.Tech Final Project)
echo   Starting Application Server on http://127.0.0.1:5000
echo ============================================================
echo.

:: Check virtual environment
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found! Please run setup first.
    pause
    exit /b
)

:: Activate Virtual Environment
call .\venv\Scripts\activate.bat

:: Launch default web browser automatically
start http://127.0.0.1:5000

:: Run Flask Application Server
python run.py

pause

