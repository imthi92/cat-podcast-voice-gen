@echo off
REM ============================================
REM Cat Podcast - Daily Episode Generator
REM Called by n8n or Windows Task Scheduler
REM ============================================

cd /d "C:\Users\Imtiyaz\Documents\New OpenCode Project\automation"

REM Set webhook URLs (update these when Colab/Kaggle restarts)
REM Get the URL from Colab output: "YOUR WEBHOOK URL: https://xxxx.ngrok.io/generate"
set COLAB_WEBHOOK_URL=
set KAGGLE_WEBHOOK_URL=

REM Run the generator
python generate_episode.py

REM Log the result
if %errorlevel% equ 0 (
    echo [%date% %time%] Episode generated successfully >> automation_log.txt
) else (
    echo [%date% %time%] Episode generation FAILED >> automation_log.txt
)
