# Cat Podcast — Fallback Plan

> Every step: Method 1 (best) → Method 2 (backup) → Method 3 (emergency)
> All tools: 100% free, open-source

---

## Script Generation

| Priority | Tool | Where | Quality | Cost |
|---|---|---|---|---|
| **1** | Groq (Llama 3.3) | API | Excellent | Free (generous) |
| **2** | HuggingFace models | API | Good | Free |
| **3** | Template scripts | Local | Good | Free |

**Note:** Groq replaced Gemini (Gemini charges after free tier, Groq is truly free).

---

## Audio Generation

| Priority | Tool | Where | Quality | GPU |
|---|---|---|---|---|
| **1** | Coqui XTTS-v2 | Colab | Premium | Yes |
| **2** | Edge TTS | Deepnote | Very Good | No |
| **3** | gTTS | Deepnote | Basic | No |

## Talking Head Video

| Priority | Tool | Where | Quality | GPU |
|---|---|---|---|---|
| **1** | SadTalker | Colab | Excellent | Yes |
| **2** | DAWN | Colab | Good | Yes |
| **3** | FFmpeg Ken Burns | Deepnote | Professional | No |

## Subtitles

| Priority | Tool | Where | Quality | GPU |
|---|---|---|---|---|
| **1** | Whisper medium | Colab | Excellent | Yes |
| **2** | faster-whisper | Deepnote | Same quality | No |
| **3** | whisper.cpp | Deepnote | Good | No |

## YouTube Upload

| Priority | Tool | Where |
|---|---|---|
| **1** | YouTube API | Deepnote |
| **2** | yt-dlp | Deepnote |
| **3** | Manual upload | Browser |

## Free GPU Sources

| Source | GPU | Free Limit |
|---|---|---|
| Google Colab | T4/A100 | ~5-8 hrs/day |
| Kaggle | P100/T4 | 30 hrs/week |
| Lightning AI | T4 | 22 GPU hrs/month |

---

## Server Loss Recovery

**If Deepnote server dies:**
1. Get new Deepnote server
2. Run: `bash <(curl -s https://raw.githubusercontent.com/imthi92/cat-podcast-voice-gen/master/setup.sh)`
3. Everything is restored from GitHub

**What's on GitHub (permanent):**
- All scripts (automation/, scripts/)
- Colab notebooks (SadTalker, VibeVoice)
- Fallback plan
- Episode history (processed_episodes.json)

**What's NOT on GitHub (regeneratable):**
- Generated audio files (regenerate from scripts)
- Generated videos (regenerate from audio)
- YouTube OAuth token (re-authenticate)
