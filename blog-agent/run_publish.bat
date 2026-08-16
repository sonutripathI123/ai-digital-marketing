@echo off
cd /d "%~dp0"
"C:\Python314\python.exe" blog_agent.py publish >> logs\cron.log 2>&1
