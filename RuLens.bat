@echo off
chcp 65001 >nul
cd /d C:\Tools\RuLens
venv\Scripts\python.exe -m rulens
pause
