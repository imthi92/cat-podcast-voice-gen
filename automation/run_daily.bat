@echo off
REM Cat Podcast Automation - Daily Runner
REM Schedule this in Windows Task Scheduler to run daily

cd /d "C:\Users\Imtiyaz\Documents\New OpenCode Project\automation"
python scheduler.py

REM Log output
echo %date% %time% - Automation completed >> automation_log.txt