# CatHub Podcast - AGENTS.md

## What
YouTube channel producing animated cat podcast episodes. Simba and Meow characters discuss cat life in a podcast format.

## Tech Stack
- Python 3.11+
- edge-tts >= 7.2.0 (voice generation with SSML pauses)
- Groq API (llama-3.1-70b-versatile for script generation)
- moviepy (video assembly)
- Pollinations.ai (background images)
- YouTube Data API v3 (upload via OAuth2)

## Key Files
- automation/generate_short.py - Shorts generator (1080x1920 vertical, 6 topics)
- automation/generate_episode.py - Long episode generator (1920x1080 horizontal)
- automation/youtube_upload.py - YouTube OAuth2 upload
- automation/youtube_token.pickle - NEVER COMMIT
- automation/client_secret.json - NEVER COMMIT
- automation/downloaded_images/ - Pre-cached 11 podcast studio backgrounds

## How to Deploy
1. Push to master branch
2. GitHub Actions triggers daily_shorts.yml (Mon-Fri 10AM UTC) or weekly_long.yml (Monday 10AM UTC)
3. Workflow runs generate_short.py or generate_episode.py
4. Video uploaded to YouTube as private, then published

## How to Run Locally
```
cd automation
pip install edge-tts>=7.2.0 groq moviepy requests
export GROQ_API_KEY=your_key_here
python generate_short.py
```

## Known Issues
1. EOFError on youtube_token.pickle: Fix applied in all 3 files (catches EOFError and pickle.UnpicklingError)
2. edge-tts version: MUST be >= 7.2.0 for SSML support. Older versions fail silently.
3. Groq model: Must be llama-3.1-70b-versatile. Other models return 404.
4. Picsum backgrounds fail sometimes: 11 images pre-cached in downloaded_images/

## Environment
- GROQ_API_KEY: Required for script generation (set in GitHub Actions secrets)
- YouTube OAuth: client_secret.json + youtube_token.pickle in automation/

## YouTube Schedule
- Shorts: Mon-Fri 10AM UTC (vertical 1080x1920, 6 topics per day)
- Long-form: Monday 10AM UTC (horizontal 1920x1080)

## .gitignore
automation/youtube_token.pickle
automation/client_secret.json
automation/__pycache__/
output/
automation/downloaded_images/
