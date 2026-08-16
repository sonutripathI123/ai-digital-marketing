@echo off
cd /d "%~dp0"
"C:\Python314\python.exe" blog_agent.py write --site ccm >> logs\cron.log 2>&1
