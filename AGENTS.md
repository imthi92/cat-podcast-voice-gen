# CatHub Podcast — Memory

## Overview
- **Repo:** imthi92/cat-podcast-voice-gen
- **Channel:** @CatHubPodcast
- **Schedule:** Daily shorts (Mon-Fri 10AM UTC) + Weekly long video (Monday 10AM UTC)

## Key Files
- `automation/generate_short.py` — Shorts generator (vertical 1080x1920, 6 topics)
- `automation/generate_episode.py` — Long episode generator
- `automation/youtube_upload.py` — YouTube upload with OAuth2
- `automation/youtube_token.pickle` — **NEVER commit** (in .gitignore)
- `automation/client_secret.json` — **NEVER commit** (in .gitignore)

## Important Notes
- Token pickle EOFError fix applied: `youtube_upload.py`, `generate_short.py`, `generate_episode.py`
- All three files now handle `EOFError` and `pickle.UnpicklingError` gracefully
- Edge TTS >=7.2.0 required, Groq model: llama-3.1-70b-versatile
- SSML pauses added for natural voice (0.4s mid, 0.6s long)
- 11 background images pre-cached in `downloaded_images/`

## YouTube Schedule
- Shorts: Mon-Fri 10AM UTC (vertical 1080x1920)
- Long-form: Monday 10AM UTC (horizontal 1920x1080)
