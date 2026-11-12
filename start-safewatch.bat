@echo off
rem Double-click this file to start SafeWatch (backend, detector and website).
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0start-safewatch.ps1"
