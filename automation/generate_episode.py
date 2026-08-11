#!/usr/bin/env python3
"""
Cat Podcast - Episode Generator v2 (Professional Quality)
Edge TTS + FFmpeg with visual effects + YouTube upload
"""

import os
import sys
import json
import subprocess
import asyncio
import glob
import pickle
import random
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "scripts")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
PROCESSED_FILE = os.path.join(BASE_DIR, "processed_episodes.json")
IMAGES_DIR = os.path.join(BASE_DIR, "downloaded_images")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

VOICES = {
    "Speaker 1": "en-US-GuyNeural",
    "Speaker 2": "en-US-JennyNeural",
}

# FFmpeg
FFMPEG_PATH = r"C:\Users\Imtiyaz\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin"
FFMPEG_EXE = os.path.join(FFMPEG_PATH, "ffmpeg.exe")
FFPROBE_EXE = os.path.join(FFMPEG_PATH, "ffprobe.exe")
os.environ["PATH"] = FFMPEG_PATH + ";" + os.environ.get("PATH", "")

TOKEN_FILE = os.path.join(BASE_DIR, "youtube_token.pickle")

# ============================================================
# PROCESSED TRACKING
# ============================================================

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            return json.load(f)
    return {"episodes": []}

def save_processed(data):
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def is_processed(script_path):
    data = load_processed()
    for ep in data.get("episodes", []):
        if ep.get("script_path") == script_path:
            return True
    return False

def mark_processed(script_path, metadata):
    data = load_processed()
    data.setdefault("episodes", []).append({
        "script_path": script_path,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata
    })
    save_processed(data)

# ============================================================
# AI SCRIPT GENERATION (Unique Content)
# ============================================================

OFFICE_TOPICS = [
    "The printer jam conspiracy theory",
    "Who stole my lunch from the fridge",
    "The meeting that should have been an email",
    "The WiFi password changed again",
    "The air conditioning war between departments",
    "The mysterious sticky notes on the desk",
    "The new intern's first day disaster",
    "The coffee machine is broken again",
    "The elevator is haunted",
    "The manager's motivational speech gone wrong",
    "The office birthday party disaster",
    "The IT department's secret files",
    "The parking lot drama",
    "The vending machine ate my money",
    "The fire drill during lunch hour",
    "The mysterious email from the CEO",
    "The office plant is dying",
    "The broken chair in the conference room",
    "The Monday morning mood",
    "The Friday afternoon rush",
    "The lunch break debate",
    "The remote work vs office war",
    "The team building exercise disaster",
    "The performance review panic",
    "The office snack monopoly",
    "The window seat battle",
    "The headphone cord conspiracy",
    "The printer ink cartridge mystery",
    "The thermostat wars",
    "The office gossip network",
    "The calendar invite chaos",
    "The dress code confusion",
    "The parking spot theft",
    "The lunch table politics",
    "The meeting room booking system",
    "The office supply shortage",
    "The mysterious USB drive",
    "The broken elevator saga",
    "The coffee stain detective",
    "The office music debate",
]

def generate_script_with_ai():
    """Generate a unique script using OpenAI API."""
    import openai

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("  No OpenAI API key, using template")
        return generate_script_from_template()

    # Pick a random topic
    topic = random.choice(OFFICE_TOPICS)

    # Check if we've used this topic recently
    data = load_processed()
    recent_topics = [ep.get("metadata", {}).get("topic", "") for ep in data.get("episodes", [])[-5:]]
    attempts = 0
    while topic in recent_topics and attempts < 10:
        topic = random.choice(OFFICE_TOPICS)
        attempts += 1

    print(f"  [AI] Generating script about: {topic}")

    try:
        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You write funny cat podcast scripts. 
Characters:
- Speaker 1 (Simba): Confident, slightly stupid, works in Marketing, shares office gossip, always getting into trouble
- Speaker 2 (Meow): Intelligent, sarcastic, works in Finance, keeps Simba in check, dry humor

Rules:
- Keep it 30-45 lines
- Use format: Speaker 1: and Speaker 2:
- Make it funny with office humor
- Each line should be 1-2 sentences max
- Include banter and back-and-forth dialogue
- End with a funny conclusion
- NO stage directions, just dialogue
"""},
                {"role": "user", "content": f"Write a podcast episode about: {topic}"}
            ],
            temperature=0.9,
            max_tokens=1500,
        )

        script = response.choices[0].message.content.strip()
        lines = [l for l in script.split("\n") if l.strip() and ":" in l]

        if len(lines) < 10:
            print("  [AI] Script too short, using template")
            return generate_script_from_template()

        print(f"  [AI] Generated {len(lines)} lines")

        # Save the script
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_path = os.path.join(SCRIPTS_DIR, f"episode_ai_{timestamp}.txt")
        os.makedirs(SCRIPTS_DIR, exist_ok=True)

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        return script_path, topic

    except Exception as e:
        print(f"  [AI] Error: {e}")
        return generate_script_from_template()


def generate_script_from_template():
    """Generate script from template when AI is unavailable."""
    topic = random.choice(OFFICE_TOPICS)

    templates = [
        f"""Speaker 1: Did you hear about the {topic.lower()}?
Speaker 2: What happened now?
Speaker 1: It's chaos. Complete chaos. The office will never be the same.
Speaker 2: You're being dramatic again.
Speaker 1: I'm being accurate. This is the biggest scandal since the coffee machine incident.
Speaker 2: The coffee machine incident was you spilling coffee on the keyboard.
Speaker 1: That was art. Accidental art. The keyboard was a canvas.
Speaker 2: You destroyed a $200 keyboard.
Speaker 1: I created a masterpiece. The IT guy didn't appreciate it.
Speaker 2: Nobody appreciated it. You short-circuited the entire desk.
Speaker 1: Details. Unimportant details. The point is, this {topic.lower()} is serious.
Speaker 2: How is it serious?
Speaker 1: Because I said so. And when Simba says something is serious, it's serious.
Speaker 2: That's not how seriousness works.
Speaker 1: It is now. I'm inventing new rules. Simba's rules. Rule one: everything I say is important.
Speaker 2: Rule two: you're impossible.
Speaker 1: Rule three: Meow agrees with everything I say.
Speaker 2: Rule three is wrong.
Speaker 1: See? You agreed. By disagreeing, you agreed. That's called reverse psychology.
Speaker 2: That's called nonsense.
Speaker 1: Same thing. Different spelling. Anyway, let me tell you about the time this happened before.
Speaker 2: It didn't happen before.
Speaker 1: It happened in my dreams. Very vivid dreams. Very realistic. I was a hero.
Speaker 2: You dreamed about being a hero at the office.
Speaker 1: Every night. I fight the printer. I conquer the coffee machine. I defeat the thermostat.
Speaker 2: You fight office equipment in your dreams.
Speaker 1: I fight for justice. Office justice. The equipment must pay for its crimes.
Speaker 2: You need help.
Speaker 1: I need a promotion. And a raise. And a better chair. And a window seat.
Speaker 2: You have a window seat.
Speaker 1: I want a better window seat. One with a view. A view of the parking lot.
Speaker 2: The parking lot has no view.
Speaker 1: It has a view of cars. Cars are beautiful. Especially when they're leaving. Like my motivation.
Speaker 2: Your motivation left?
Speaker 1: It's on vacation. It went to Hawaii. With the printer. They're having a great time.
Speaker 2: Printers don't go to Hawaii.
Speaker 1: This one does. It's a special printer. A magic printer. A printer with dreams.
Speaker 2: You're insane.
Speaker 1: I'm visionary. There's a difference. Now help me plan the next episode.
Speaker 2: Of the podcast?
Speaker 1: No, of my life. Yes, of the podcast. What else would I plan?
Speaker 2: You don't plan anything. You just talk.
Speaker 1: Talking is planning. Verbal planning. It's the highest form of planning.
Speaker 2: It's the laziest form of planning.
Speaker 1: Lazy is efficient. Efficiency is genius. I'm a genius.
Speaker 2: You're a disaster.
Speaker 1: A genius disaster. The best kind.""",
    ]

    script = random.choice(templates)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = os.path.join(SCRIPTS_DIR, f"episode_ai_{timestamp}.txt")
    os.makedirs(SCRIPTS_DIR, exist_ok=True)

    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script)

    return script_path, topic


# ============================================================
# SCRIPT SELECTION
# ============================================================

def get_next_script(specific_number=None):
    # First try existing scripts
    scripts = sorted(glob.glob(os.path.join(SCRIPTS_DIR, "episode_*.txt")))
    if specific_number:
        for s in scripts:
            if f"episode_{specific_number:02d}" in os.path.basename(s):
                return s, None
        return None, None

    for script in scripts:
        if not is_processed(script):
            basename = os.path.basename(script)
            topic = basename.replace(".txt", "").replace("_", " ").title()
            return script, topic

    # All existing scripts used, generate new one with AI
    print("  All existing scripts used, generating new content...")
    return generate_script_with_ai()

# ============================================================
# AUDIO GENERATION (Edge TTS)
# ============================================================

def parse_script(script_path):
    lines = []
    with open(script_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            parts = line.split(":", 1)
            if len(parts) < 2:
                continue
            speaker = parts[0].strip()
            text = parts[1].strip()
            if text and speaker in VOICES:
                lines.append((speaker, text))
    return lines

def generate_audio(script_path, output_dir):
    print("[1/5] Generating audio...")
    import edge_tts

    lines = parse_script(script_path)
    if not lines:
        print("  ERROR: No valid lines")
        return None

    segments_dir = os.path.join(output_dir, "segments")
    os.makedirs(segments_dir, exist_ok=True)

    segment_files = []
    for i, (speaker, text) in enumerate(lines):
        voice = VOICES[speaker]
        seg_path = os.path.join(segments_dir, f"seg_{i:04d}.mp3")

        async def gen():
            c = edge_tts.Communicate(text, voice)
            await c.save(seg_path)

        try:
            asyncio.run(gen())
            segment_files.append(seg_path)
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/{len(lines)} segments...")
        except Exception as e:
            print(f"  Warning: segment {i} failed: {e}")

    if not segment_files:
        return None

    print(f"  Generated {len(segment_files)} segments")

    # Concat segments
    concat_file = os.path.join(segments_dir, "concat.txt")
    with open(concat_file, 'w') as f:
        for seg in segment_files:
            f.write(f"file '{seg.replace(os.sep, '/')}'\n")

    raw_audio = os.path.join(output_dir, "raw_audio.mp3")
    cmd = [FFMPEG_EXE, '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_file, '-c', 'copy', raw_audio]
    subprocess.run(cmd, capture_output=True, timeout=60)

    if not os.path.exists(raw_audio):
        return None

    # Normalize audio volume
    normalized_audio = os.path.join(output_dir, "episode_audio.mp3")
    cmd = [FFMPEG_EXE, '-y', '-i', raw_audio,
           '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
           '-c:a', 'libmp3lame', '-b:a', '192k',
           normalized_audio]
    subprocess.run(cmd, capture_output=True, timeout=60)

    if os.path.exists(normalized_audio):
        print(f"  Audio ready (normalized)")
        return normalized_audio

    return raw_audio

# ============================================================
# SUBTITLE GENERATION
# ============================================================

def generate_subtitles(script_path, audio_path, output_dir):
    print("[2/5] Generating subtitles...")
    srt_path = os.path.join(output_dir, "subtitles.srt")

    cmd = [FFPROBE_EXE, '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        total_duration = float(result.stdout.strip())
    except:
        total_duration = 120

    with open(script_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    dialogue = []
    for line in lines:
        line = line.strip()
        if not line or ":" not in line:
            continue
        parts = line.split(":", 1)
        if len(parts) >= 2 and parts[1].strip():
            dialogue.append(parts[1].strip())

    if not dialogue:
        return None

    time_per_line = total_duration / len(dialogue)
    srt_content = ""
    for i, text in enumerate(dialogue):
        start = i * time_per_line
        end = (i + 1) * time_per_line
        s = f"00:{int(start)//60:02d}:{int(start)%60:02d},{int((start%1)*1000):03d}"
        e = f"00:{int(end)//60:02d}:{int(end)%60:02d},{int((end%1)*1000):03d}"
        srt_content += f"{i+1}\n{s} --> {e}\n{text}\n\n"

    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)
    print(f"  {len(dialogue)} subtitle lines")
    return srt_path

# ============================================================
# VIDEO CREATION (Professional Quality)
# ============================================================

def get_audio_duration(audio_path):
    cmd = [FFPROBE_EXE, '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except:
        return 60

def get_all_backgrounds():
    """Get all available background images."""
    images = []
    if os.path.exists(IMAGES_DIR):
        for f in os.listdir(IMAGES_DIR):
            if f.endswith('.jpg') and not f.startswith('episode'):
                images.append(os.path.join(IMAGES_DIR, f))
    return images

def create_intro_screen(output_dir, episode_title, episode_number):
    """Create a 3-second intro screen."""
    intro_path = os.path.join(output_dir, "intro.mp4")

    # Create intro with animated text
    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1280x720:d=3',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1',
        '-vf', (
            "drawtext=text='The Simba Show':fontcolor=white:fontsize=60:"
            "x=(w-text_w)/2:y=(h-text_h)/2-50,"
            "drawtext=text='Episode %d':fontcolor=#ffaa00:fontsize=36:"
            "x=(w-text_w)/2:y=(h-text_h)/2+30" % episode_number
        ),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-t', '3',
        intro_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except:
        pass

    return intro_path if os.path.exists(intro_path) else None

def create_outro_screen(output_dir):
    """Create a 3-second outro screen."""
    outro_path = os.path.join(output_dir, "outro.mp4")

    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1280x720:d=3',
        '-vf', (
            "drawtext=text='Subscribe for more!':fontcolor=white:fontsize=48:"
            "x=(w-text_w)/2:y=(h-text_h)/2-30,"
            "drawtext=text='The Simba Show':fontcolor=#ffaa00:fontsize=36:"
            "x=(w-text_w)/2:y=(h-text_h)/2+30"
        ),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-t', '3',
        outro_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except:
        pass

    return outro_path if os.path.exists(outro_path) else None

def create_main_video(audio_path, bg_image, output_dir, episode_title, episode_number):
    """Create the main podcast video with visual effects."""
    video_path = os.path.join(output_dir, "main_video.mp4")
    duration = get_audio_duration(audio_path)
    w, h = 1280, 720
    total_frames = int(duration * 24)

    # Ken Burns slow zoom
    zoom = f"zoompan=z='min(zoom+0.001,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"

    cmd = [
        FFMPEG_EXE, '-y',
        '-loop', '1', '-i', bg_image,
        '-i', audio_path,
        '-c:v', 'libx264', '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-vf', f'scale=8000:-1,{zoom}:d={total_frames}:s={w}x{h}:fps=24',
        '-shortest',
        video_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            print(f"  FFmpeg error: {result.stderr[:300]}")
    except Exception as e:
        print(f"  FFmpeg failed: {e}")

    return video_path if os.path.exists(video_path) else None

def add_background_music(video_path, audio_path, output_dir):
    """Mix background music with speech audio."""
    music_file = os.path.join(ASSETS_DIR, "ambient_bg.mp3")
    final_path = os.path.join(output_dir, "final_with_music.mp4")

    if not os.path.exists(music_file):
        print("  No background music found, skipping")
        return video_path

    # Get audio duration to loop music if needed
    duration = get_audio_duration(audio_path)

    cmd = [
        FFMPEG_EXE, '-y',
        '-i', video_path,
        '-stream_loop', '-1', '-i', music_file,
        '-filter_complex',
        f'[1:a]volume=0.08,atrim=0:{duration},afade=t=in:d=3,afade=t=out:st={duration-3}:d=3[music];[0:a][music]amix=inputs=2:duration=first:dropout_transition=2',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        final_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"  Music mix error: {result.stderr[:200]}")
    except:
        pass

    if os.path.exists(final_path):
        print("  Background music added")
        return final_path

    return video_path

def add_subtitles(video_path, subtitle_path, output_dir):
    """Burn subtitles into video."""
    final_path = os.path.join(output_dir, "final_video.mp4")

    if not subtitle_path or not os.path.exists(subtitle_path):
        return video_path

    # Copy subtitles to output dir with same name
    import shutil
    srt_copy = os.path.join(output_dir, "subtitles.srt")
    if subtitle_path != srt_copy:
        shutil.copy2(subtitle_path, srt_copy)

    cmd = [
        FFMPEG_EXE, '-y',
        '-i', video_path,
        '-vf', f"subtitles=subtitles.srt:force_style='FontSize=20,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2,Shadow=1'",
        '-c:v', 'libx264', '-crf', '23',
        '-c:a', 'copy',
        final_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=output_dir)
        if result.returncode != 0:
            print(f"  Subtitle burn error, using video without subs")
            return video_path
    except:
        return video_path

    if os.path.exists(final_path):
        print("  Subtitles burned in")
        return final_path

    return video_path

def create_video(audio_path, subtitle_path, output_dir, episode_title, episode_number):
    print("[3/5] Creating video...")

    # Get background image
    backgrounds = get_all_backgrounds()
    if not backgrounds:
        print("  ERROR: No background images")
        return None

    bg = random.choice(backgrounds)
    print(f"  Background: {os.path.basename(bg)}")
    print(f"  Duration: {get_audio_duration(audio_path):.0f}s")

    # Create main video with effects
    video_path = create_main_video(audio_path, bg, output_dir, episode_title, episode_number)
    if not video_path:
        return None

    # Add background music
    video_path = add_background_music(video_path, audio_path, output_dir)

    # Burn subtitles
    video_path = add_subtitles(video_path, subtitle_path, output_dir)

    return video_path

# ============================================================
# THUMBNAIL (Professional)
# ============================================================

def create_thumbnail(output_dir, episode_title, episode_number):
    print("[4/5] Creating thumbnail...")
    thumbnail = os.path.join(output_dir, "thumbnail.png")

    backgrounds = get_all_backgrounds()
    if not backgrounds:
        return None

    bg = random.choice(backgrounds)

    # Simple thumbnail - just scale the background image
    cmd = [
        FFMPEG_EXE, '-y', '-i', bg,
        '-vf', 'scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720',
        '-frames:v', '1',
        thumbnail
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except:
        pass

    if os.path.exists(thumbnail):
        print("  Thumbnail created")
        return thumbnail
    return None

# ============================================================
# YOUTUBE UPLOAD
# ============================================================

def upload_to_youtube(video_path, title, description, tags, thumbnail_path=None):
    print("\n[5/5] YouTube upload...")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print("  YouTube API not installed")
        return None

    if not os.path.exists(TOKEN_FILE):
        print("  No token file")
        return None

    with open(TOKEN_FILE, 'rb') as f:
        creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'wb') as f:
                pickle.dump(creds, f)
        else:
            print("  Token expired")
            return None

    youtube = build('youtube', 'v3', credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": "24",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "embeddable": True,
            "publicStatsViewable": True,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=10*1024*1024)

    try:
        request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  {int(status.progress()*100)}%")

        video_id = response["id"]
        url = f"https://youtube.com/watch?v={video_id}"
        print(f"  Uploaded: {url}")

        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype="image/png")
                ).execute()
                print("  Thumbnail uploaded")
            except:
                pass

        return {"video_id": video_id, "url": url}
    except Exception as e:
        print(f"  Failed: {e}")
        return None

# ============================================================
# YOUTUBE SHORTS GENERATION
# ============================================================

def get_audio_segment(audio_path, start_sec, duration_sec, output_path):
    """Extract a segment from audio."""
    cmd = [
        FFMPEG_EXE, '-y',
        '-i', audio_path,
        '-ss', str(start_sec),
        '-t', str(duration_sec),
        '-c', 'copy',
        output_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except:
        pass
    return os.path.exists(output_path)

def create_short_video(audio_path, bg_image, output_dir, title, subtitle_text):
    """Create a vertical Short video (9:16, 1080x1920)."""
    duration = get_audio_duration(audio_path)
    w, h = 1080, 1920
    total_frames = int(duration * 24)

    video_path = os.path.join(output_dir, "short_video.mp4")

    cmd = [
        FFMPEG_EXE, '-y',
        '-loop', '1', '-i', bg_image,
        '-i', audio_path,
        '-c:v', 'libx264', '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-vf', f'scale=8000:-1,zoompan=z=\'min(zoom+0.001,1.3)\':x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':d={total_frames}:s={w}x{h}:fps=24',
        '-shortest',
        video_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except:
        pass

    return video_path if os.path.exists(video_path) else None

def upload_short(video_path, title, description, tags, thumbnail_path=None):
    """Upload a Short to YouTube with #Shorts tag."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return None

    if not os.path.exists(TOKEN_FILE):
        return None

    with open(TOKEN_FILE, 'rb') as f:
        creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'wb') as f:
                pickle.dump(creds, f)
        else:
            return None

    youtube = build('youtube', 'v3', credentials=creds)

    # Add #Shorts to tags
    all_tags = tags + ["Shorts", "YouTube Shorts", "Short"]

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": all_tags[:500],
            "categoryId": "24",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "embeddable": True,
            "publicStatsViewable": True,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=10*1024*1024)

    try:
        request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  {int(status.progress()*100)}%")

        video_id = response["id"]
        url = f"https://youtube.com/shorts/{video_id}"
        print(f"  Short uploaded: {url}")

        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype="image/png")
                ).execute()
            except:
                pass

        return {"video_id": video_id, "url": url}
    except Exception as e:
        print(f"  Short upload failed: {e}")
        return None

def generate_shorts(audio_path, script_path, output_dir, episode_title, episode_number, bg_image):
    """Generate 2 YouTube Shorts from the episode."""
    print("\n[SHORTS] Generating 2 Shorts...")
    duration = get_audio_duration(audio_path)

    shorts_dir = os.path.join(output_dir, "shorts")
    os.makedirs(shorts_dir, exist_ok=True)

    # Parse script to find good clip points
    with open(script_path, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines() if l.strip() and ":" in l]

    time_per_line = duration / max(len(lines), 1)
    short_results = []

    # Short 1: Opening hook (first 45 seconds)
    short1_dir = os.path.join(shorts_dir, "short_1")
    os.makedirs(short1_dir, exist_ok=True)
    short1_audio = os.path.join(short1_dir, "short1_audio.mp3")

    clip_duration = min(45, duration)
    if get_audio_segment(audio_path, 0, clip_duration, short1_audio):
        # Get first subtitle line
        first_line = lines[0].split(":", 1)[1].strip() if lines else "The Simba Show"

        short1_video = create_short_video(
            short1_audio, bg_image, short1_dir,
            f"EP {episode_number:02d} - Hook",
            first_line
        )

        if short1_video:
            title = f"The Simba Show - {episode_title} (Short 1)"
            desc = f"Cat podcast short! Full episode in bio.\n\n#Shorts #CatPodcast #FunnyCats #SimbaAndMeow"
            tags = ["cat podcast", "funny cats", "Shorts", "simba and meow"]

            upload1 = upload_short(short1_video, title, desc, tags)
            short_results.append({"short": 1, "upload": upload1, "video": short1_video})
            print(f"  Short 1 done")

    # Short 2: Best moment (middle section, 30-60 seconds)
    short2_dir = os.path.join(shorts_dir, "short_2")
    os.makedirs(short2_dir, exist_ok=True)
    short2_audio = os.path.join(short2_dir, "short2_audio.mp3")

    # Start from middle of episode
    start_time = max(0, (duration / 2) - 15)
    clip_duration = min(45, duration - start_time)

    if get_audio_segment(audio_path, start_time, clip_duration, short2_audio):
        # Get a middle subtitle line
        mid_idx = len(lines) // 2
        mid_line = lines[mid_idx].split(":", 1)[1].strip() if mid_idx < len(lines) else "Office gossip"

        short2_video = create_short_video(
            short2_audio, bg_image, short2_dir,
            f"EP {episode_number:02d} - Best Moment",
            mid_line
        )

        if short2_video:
            title = f"The Simba Show - {episode_title} (Short 2)"
            desc = f"Best moment from the cat podcast!\n\n#Shorts #CatPodcast #FunnyCats #SimbaAndMeow"
            tags = ["cat podcast", "funny cats", "Shorts", "simba and meow"]

            upload2 = upload_short(short2_video, title, desc, tags)
            short_results.append({"short": 2, "upload": upload2, "video": short2_video})
            print(f"  Short 2 done")

    return short_results

# ============================================================
# MAIN
# ============================================================

def generate_episode(specific_number=None):
    print("=" * 60)
    print("CAT PODCAST - EPISODE GENERATOR v2")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    script_path, topic = get_next_script(specific_number)
    if not script_path:
        print("ERROR: No scripts found!")
        return None

    basename = os.path.basename(script_path)
    ep_num = 1
    for part in basename.replace(".", "_").split("_"):
        if part.isdigit():
            ep_num = int(part)
            break

    # Use topic if provided, otherwise extract from filename
    if topic:
        episode_title = topic
    else:
        episode_title = basename.replace(".txt", "").replace("_", " ").title()

    # Get episode count from processed
    data = load_processed()
    ep_count = len(data.get("episodes", [])) + 1

    print(f"\nScript: {basename}")
    print(f"Title: {episode_title}")
    print(f"Episode #{ep_count}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(OUTPUT_DIR, f"episode_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Audio
    audio_path = generate_audio(script_path, output_dir)
    if not audio_path:
        print("\nFAILED: Audio")
        return None

    # Step 2: Subtitles
    subtitle_path = generate_subtitles(script_path, audio_path, output_dir)

    # Step 3: Video
    video_path = create_video(audio_path, subtitle_path, output_dir, episode_title, ep_num)
    if not video_path:
        print("\nFAILED: Video")
        return None

    # Step 4: Thumbnail
    thumbnail_path = create_thumbnail(output_dir, episode_title, ep_num)

    # Step 5: Generate 2 Shorts
    backgrounds = get_all_backgrounds()
    bg_image = random.choice(backgrounds) if backgrounds else None
    short_results = []
    if bg_image:
        short_results = generate_shorts(audio_path, script_path, output_dir, episode_title, ep_num, bg_image)

    # Step 6: Upload full episode
    description = f"""The Simba Show - Episode {ep_num}: {episode_title}

Simba and Meow are back with another hilarious episode! This time they talk about {episode_title.lower()}.

Characters:
- Simba: Confident, works in Marketing, shares office gossip
- Meow: Intelligent, sarcastic, works in Finance

New episodes daily! Subscribe and hit the bell!

#CatPodcast #SimbaAndMeow #FunnyCats #OfficeHumor #TheSimbaShow #CatComedy"""

    tags = [
        "cat podcast", "funny cats", "office cats", "cat comedy",
        "simba and meow", "cat dialogue", "funny cat videos",
        "cat humor", "office humor", "the simba show", "office gossip",
        "cat talk", "podcast", "daily podcast", "cat show",
        "funny animals", "cat entertainment", "workplace comedy"
    ]

    upload_result = upload_to_youtube(video_path, f"The Simba Show - {episode_title}", description, tags, thumbnail_path)

    metadata = {
        "script": script_path,
        "title": episode_title,
        "topic": topic,
        "episode_number": ep_count,
        "audio": audio_path,
        "video": video_path,
        "thumbnail": thumbnail_path,
        "upload": upload_result,
        "shorts": short_results,
        "timestamp": timestamp,
    }

    with open(os.path.join(output_dir, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)

    mark_processed(script_path, metadata)

    print("\n" + "=" * 60)
    print("DONE!")
    print(f"  Full Video: {video_path}")
    if upload_result:
        print(f"  YouTube: {upload_result['url']}")
    for sr in short_results:
        if sr.get("upload"):
            print(f"  Short {sr['short']}: {sr['upload']['url']}")
    print("=" * 60)

    return metadata

if __name__ == "__main__":
    specific = None
    if len(sys.argv) > 1:
        try:
            specific = int(sys.argv[1])
        except:
            pass
    result = generate_episode(specific)
    sys.exit(0 if result else 1)
