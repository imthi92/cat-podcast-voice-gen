@echo off
REM ============================================
REM Cat Podcast - Daily Episode Generator
REM Run via Task Scheduler or manually
REM ============================================

cd /d "C:\Users\Imtiyaz\Documents\New OpenCode Project\automation"

echo [%date% %time%] Starting episode generation...

python generate_episode.py

if %errorlevel% equ 0 (
    echo [%date% %time%] SUCCESS >> automation_log.txt
) else (
    echo [%date% %time%] FAILED >> automation_log.txt
)

echo [%date% %time%] Done.
