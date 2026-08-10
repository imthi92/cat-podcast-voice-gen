#!/usr/bin/env python3
"""
Cat Podcast - Episode Generator (Fully Automated)
Edge TTS + FFmpeg podcast-style video + YouTube upload
"""

import os
import sys
import json
import subprocess
import asyncio
import glob
import pickle
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

# Edge TTS voices
VOICES = {
    "Speaker 1": "en-US-GuyNeural",
    "Speaker 2": "en-US-JennyNeural",
}

# FFmpeg
FFMPEG_PATH = r"C:\Users\Imtiyaz\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin"
FFMPEG_EXE = os.path.join(FFMPEG_PATH, "ffmpeg.exe")
FFPROBE_EXE = os.path.join(FFMPEG_PATH, "ffprobe.exe")
os.environ["PATH"] = FFMPEG_PATH + ";" + os.environ.get("PATH", "")

# YouTube
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
# SCRIPT SELECTION
# ============================================================

def get_next_script(specific_number=None):
    scripts = sorted(glob.glob(os.path.join(SCRIPTS_DIR, "episode_*.txt")))
    if specific_number:
        for s in scripts:
            if f"episode_{specific_number:02d}" in os.path.basename(s):
                return s
        return None
    for script in scripts:
        if not is_processed(script):
            return script
    if scripts:
        return scripts[0]
    return None

# ============================================================
# AUDIO GENERATION (Edge TTS - FREE)
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
    print("[1/4] Generating audio...")
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

    # Concat with FFmpeg
    concat_file = os.path.join(segments_dir, "concat.txt")
    with open(concat_file, 'w') as f:
        for seg in segment_files:
            f.write(f"file '{seg.replace(os.sep, '/')}'\n")

    audio_output = os.path.join(output_dir, "episode_audio.mp3")
    cmd = [FFMPEG_EXE, '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_file, '-c', 'copy', audio_output]

    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except:
        return None

    if os.path.exists(audio_output):
        print(f"  Audio ready")
        return audio_output
    return None

# ============================================================
# SUBTITLE GENERATION
# ============================================================

def generate_subtitles(script_path, audio_path, output_dir):
    print("[2/4] Generating subtitles...")
    srt_path = os.path.join(output_dir, "subtitles.srt")

    # Get audio duration
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
# VIDEO CREATION (Podcast Style)
# ============================================================

def get_audio_duration(audio_path):
    cmd = [FFPROBE_EXE, '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except:
        return 60

def find_background():
    if os.path.exists(IMAGES_DIR):
        # Priority: the two-cat podcast image
        for f in os.listdir(IMAGES_DIR):
            if 'Two_cartoon_cats' in f and f.endswith('.jpg') and '(' not in f:
                return os.path.join(IMAGES_DIR, f)
        for f in os.listdir(IMAGES_DIR):
            if 'Wide' in f and f.endswith('.jpg'):
                return os.path.join(IMAGES_DIR, f)
    return None

def create_video(audio_path, subtitle_path, output_dir, episode_title, episode_number):
    print("[3/4] Creating video...")

    video_output = os.path.join(output_dir, "final_video.mp4")
    duration = get_audio_duration(audio_path)
    w, h = 1280, 720

    bg = find_background()
    if not bg:
        print("  ERROR: No background image")
        return None

    print(f"  Background: {os.path.basename(bg)}")
    print(f"  Duration: {duration:.0f}s")

    total_frames = int(duration * 24)

    # Ken Burns slow zoom effect
    cmd = [
        FFMPEG_EXE, '-y',
        '-loop', '1', '-i', bg,
        '-i', audio_path,
        '-c:v', 'libx264', '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-vf', f'scale=8000:-1,zoompan=z=\'min(zoom+0.0012,1.4)\':x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':d={total_frames}:s={w}x{h}:fps=24',
        '-shortest',
        video_output
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            print(f"  FFmpeg error: {result.stderr[:300]}")
    except Exception as e:
        print(f"  FFmpeg failed: {e}")

    if os.path.exists(video_output):
        size_mb = os.path.getsize(video_output) / (1024 * 1024)
        print(f"  Video: {size_mb:.1f} MB")
        return video_output
    return None

# ============================================================
# THUMBNAIL
# ============================================================

def create_thumbnail(output_dir, episode_title, episode_number):
    print("[4/4] Creating thumbnail...")
    thumbnail = os.path.join(output_dir, "thumbnail.png")
    bg = find_background()

    if not bg:
        return None

    cmd = [FFMPEG_EXE, '-y', '-i', bg,
           '-vf', 'scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720',
           '-frames:v', '1', thumbnail]

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
    print("\n[UPLOAD] YouTube...")
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
# MAIN
# ============================================================

def generate_episode(specific_number=None):
    print("=" * 60)
    print("CAT PODCAST - EPISODE GENERATOR")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    script_path = get_next_script(specific_number)
    if not script_path:
        print("ERROR: No scripts found!")
        return None

    # Extract episode number from filename
    basename = os.path.basename(script_path)
    ep_num = 1
    for part in basename.replace(".", "_").split("_"):
        if part.isdigit():
            ep_num = int(part)
            break

    episode_title = basename.replace(".txt", "").replace("_", " ").title()
    episode_title = f"Cat Office Gossip - {episode_title}"

    print(f"\nScript: {basename}")
    print(f"Title: {episode_title}")

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

    # Upload
    description = f"""Cat Podcast - {episode_title}

Simba and Meow are back! This time they talk about {episode_title.lower()}.

Simba - Confident, works in Marketing, shares office gossip
Meow - Intelligent, sarcastic, works in Finance

New episodes daily! Subscribe!

#CatPodcast #SimbaAndMeow #FunnyCats #OfficeHumor #TheSimbaShow"""

    tags = [
        "cat podcast", "funny cats", "office cats", "cat comedy",
        "simba and meow", "cat dialogue", "funny cat videos",
        "cat humor", "office humor", "the simba show", "office gossip",
        "cat talk", "podcast", "daily podcast"
    ]

    upload_result = upload_to_youtube(video_path, episode_title, description, tags, thumbnail_path)

    metadata = {
        "script": script_path,
        "title": episode_title,
        "episode_number": ep_num,
        "audio": audio_path,
        "video": video_path,
        "thumbnail": thumbnail_path,
        "upload": upload_result,
        "timestamp": timestamp,
    }

    with open(os.path.join(output_dir, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)

    mark_processed(script_path, metadata)

    print("\n" + "=" * 60)
    print("DONE!")
    print(f"  Video: {video_path}")
    if upload_result:
        print(f"  YouTube: {upload_result['url']}")
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
