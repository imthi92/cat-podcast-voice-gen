# Video Pipeline Plan - Cat Podcast YouTube Channel

## Overview

Turn VibeVoice audio into YouTube-ready videos with:
- Animated cat characters
- Subtitles/captions
- Background music
- Podcast studio visual

---

## Pipeline Architecture

```
Audio (.wav)
    |
    v
[Subtitle Generation] --> SRT file (timestamps + text)
    |
    v
[Cat Visual Generation] --> Static/animated cat images
    |
    v
[Video Assembly] --> Combine audio + visuals + subtitles + music
    |
    v
YouTube Upload
```

---

## Step 1: Subtitle Generation

### Option A: Whisper (Free, Local)
- Use OpenAI Whisper to transcribe audio
- Generate SRT file with timestamps
- Run on Colab GPU (free)

### Option B: Whisper API (Paid, $0.006/min)
- Faster processing
- Better accuracy
- Use when scaling

### Command (Colab):
```python
!pip install openai-whisper
!whisper episode.wav --model base --output_format srt
```

---

## Step 2: Cat Character Visuals

### Option A: Static Character Images (Easiest)
- Create 2-3 cat character PNGs (transparent background)
- Simba: Orange tabby, office shirt
- Meow: Black cat, glasses
- Use these same images every episode
- Tools: Canva, DALL-E, Midjourney, or free AI generators

### Option B: Simple Animation (Medium)
- Use cat images with basic mouth movement
- Sync mouth to audio amplitude
- Add head bobbing on speech
- Tools: Python + moviepy, or After Effects templates

### Option C: AI Animation (Advanced)
- RunwayML or Pika for animated clips
- Generate 5-10 second clips per scene
- Higher quality but more expensive

### Recommended: Start with Option A
- Create consistent brand identity
- Fast to produce
- Easy to maintain
- Can upgrade later

---

## Step 3: Podcast Studio Background

### Options:
1. **Canva** - Free podcast studio templates
2. **DALL-E / Midjourney** - AI-generated studio background
3. **Stock image** - Free podcast studio photos
4. **Custom design** - Hire on Fiverr ($5-20)

### Recommended Elements:
- Podcast desk with two microphones
- Cat-themed decor
- Warm lighting
- Consistent brand colors

---

## Step 4: Video Assembly

### Tool: FFmpeg (Free, Command Line)
```bash
ffmpeg -i audio.wav -i background.png -i subtitles.srt \
  -filter_complex "[0:a]volume=1.0[a];[1:v]loop=loop=-1:size=1:start=0[v];[v][0:a]concat=n=1:v=1:a=1[out]" \
  -map "[out]" -map "0:a" -c:v libx264 -c:a aac output.mp4
```

### Tool: Python + moviepy (Easier)
```python
from moviepy.editor import *

audio = AudioFileClip("episode.wav")
background = ImageClip("studio_background.png").set_duration(audio.duration)
subtitles = TextClip("subtitles.srt")

video = CompositeVideoClip([background, subtitles])
video = video.set_audio(audio)
video.write_videofile("output.mp4", fps=24)
```

### Tool: CapCut (Free, GUI)
- Import audio + background + subtitles
- Add transitions and effects
- Export as MP4
- Beginner-friendly

---

## Step 5: Background Music

### Free Music Sources:
- YouTube Audio Library
- Pixabay Music
- Free Music Archive
- Incompetech

### Volume Rule:
- Music at 10-15% volume
- Dialogue at 100% volume
- Music should not overpower speech

### FFmpeg command:
```bash
ffmpeg -i episode.wav -i music.mp3 -filter_complex "[1:a]volume=0.12[m];[0:a]volume=1.0[v];[m][v]amix=inputs=2" output_mixed.wav
```

---

## Step 6: Thumbnail

### Elements:
- Cat character (Simba or Meow)
- Episode title (large text)
- Bright colors
- Expressive face
- Office/corporate background

### Tools:
- Canva (Free templates)
- Photoshop
- Fiverr ($5-10)

### Size: 1280 x 720 px

---

## Complete Workflow (Simplified)

```
1. Write episode script
         |
2. Generate audio (VibeVoice on Colab)
         |
3. Generate subtitles (Whisper on Colab)
         |
4. Add subtitles to video (CapCut/moviepy)
         |
5. Add background music (FFmpeg/CapCut)
         |
6. Create thumbnail (Canva)
         |
7. Upload to YouTube
```

---

## Time Estimate (Per Episode)

| Step | Time |
|------|------|
| Script writing | 30 min |
| Audio generation | 5-10 min |
| Subtitle generation | 5 min |
| Video assembly | 15-20 min |
| Thumbnail | 10 min |
| **Total** | **~60-75 min** |

---

## Future Automation

Once workflow is proven:
1. Script generation (AI) -> 5 min
2. Audio generation (VibeVoice) -> 10 min
3. Subtitle generation (Whisper) -> 5 min
4. Video assembly (moviepy script) -> 10 min
5. Thumbnail (template + text swap) -> 5 min
6. YouTube upload (API) -> 2 min
7. **Total automated: ~37 min per episode**

---

## Free Tools Summary

| Tool | Purpose | Cost |
|------|---------|------|
| Google Colab | Audio + subtitle generation | Free |
| VibeVoice | TTS | Free |
| Whisper | Subtitles | Free |
| CapCut | Video editing | Free |
| Canva | Thumbnails | Free |
| FFmpeg | Video processing | Free |
| moviepy | Python video editing | Free |

---

## Recommended First Episode Setup

1. Create Simba and Meow PNG images (Canva/DALL-E)
2. Create podcast studio background
3. Use Episode 1 audio (already done)
4. Generate subtitles with Whisper
5. Assemble in CapCut
6. Create thumbnail
7. Upload to YouTube

This gives you one complete video to test the pipeline before automating.