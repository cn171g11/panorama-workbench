@echo off
cd /d "%~dp0.."
start "" http://localhost:8899/_viewer/viewer.html
python -m http.server 8899
