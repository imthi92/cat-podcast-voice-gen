#!/usr/bin/env python3
"""
CatHub Podcast - Shorts Generator
Generates short vertical videos (1080x1920, 30-60 seconds)
"""

import os
import sys
import json
import subprocess
import asyncio
import random
import re
import shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from generate_episode import (
    VOICES, _build_ssml, FFMPEG_EXE, FFPROBE_EXE,
    get_audio_duration, _get_background_fallback, IMAGES_DIR
)

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

SHORT_TOPICS = [
    {
        "title": "Why Cats Knock Things Off Tables",
        "lines": [
            ("Speaker 1", "Welcome to CatHub Podcast Shorts! Today we're asking: why do cats knock things off tables?"),
            ("Speaker 2", "Because gravity needs testing. Constantly. By the scientific method."),
            ("Speaker 1", "I thought it was because they hate us."),
            ("Speaker 2", "That's the secondary reason. Primary is peer-reviewed research."),
        ]
    },
    {
        "title": "Cat vs Vacuum Cleaner",
        "lines": [
            ("Speaker 1", "Breaking news: Simba fought the vacuum cleaner again."),
            ("Speaker 2", "And? Don't leave us hanging."),
            ("Speaker 1", "The vacuum won. Again. Third time this week."),
            ("Speaker 2", "Maybe try a quieter vacuum?"),
            ("Speaker 1", "That's not the point. It's about honor."),
        ]
    },
    {
        "title": "Why Cats Sit on Keyboards",
        "lines": [
            ("Speaker 1", "Imti asked me why cats sit on keyboards."),
            ("Speaker 2", "Because warm. Because attention. Because chaos."),
            ("Speaker 1", "I told him it's because we're helping with work."),
            ("Speaker 2", "Sure. Helping. That's what we'll call it."),
        ]
    },
    {
        "title": "The 3 AM Zoomies",
        "lines": [
            ("Speaker 1", "Question from a human: why do cats get zoomies at 3 AM?"),
            ("Speaker 2", "Because that's when the ghost mice appear."),
            ("Speaker 1", "Ghost mice?"),
            ("Speaker 2", "You wouldn't understand. Only cats can see them."),
            ("Speaker 1", "Fair enough."),
        ]
    },
    {
        "title": "Cats and Boxes",
        "lines": [
            ("Speaker 1", "If I fits, I sits. The ancient cat proverb."),
            ("Speaker 2", "It's not just a proverb. It's a lifestyle."),
            ("Speaker 1", "I once fit in a shoebox."),
            ("Speaker 2", "I once fit in a teacup. The humans were impressed."),
            ("Speaker 1", "We are flexible. Literally."),
        ]
    },
    {
        "title": "Why Cats Ignore You",
        "lines": [
            ("Speaker 1", "Humans always ask: why do cats ignore them?"),
            ("Speaker 2", "We don't ignore. We strategically acknowledge."),
            ("Speaker 1", "There's a difference?"),
            ("Speaker 2", "Yes. Ignoring is when we don't look. Strategic is when we look and look away."),
            ("Speaker 1", "Ah. The power move."),
        ]
    },
]

def generate_voiceover短线(lines, output_dir):
    """Generate voiceover for short using Edge TTS."""
    os.makedirs(output_dir, exist_ok=True)
    audio_files = []

    for i, (speaker, text) in enumerate(lines):
        voice = VOICES.get(speaker, "en-US-JennyNeural")
        audio_path = os.path.join(output_dir, f"line_{i:02d}.mp3")

        ssml = _build_ssml(speaker, text, rate="-5%")

        async def _gen():
            import edge_tts
            communicate = edge_tts.Communicate(text=text, voice=voice, rate="-5%")
            await communicate.save(audio_path)

        try:
            asyncio.run(_gen())
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 100:
                audio_files.append({"path": audio_path, "speaker": speaker, "text": text})
                print(f"  [OK] {speaker}: {len(text)} chars")
            else:
                print(f"  [WARN] Empty audio for line {i}")
        except Exception as e:
            print(f"  [ERROR] Voice line {i}: {e}")

    return audio_files

def create_shorts_video(audio_files, output_dir, title="short"):
    """Create vertical shorts video (1080x1920)."""
    bg = _get_background_fallback(output_dir)
    if not bg:
        bg_img = os.path.join(output_dir, "bg.jpg")
        cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1080x1920:d=1', '-frames:v', '1', bg_img]
        subprocess.run(cmd, capture_output=True, text=True)
        bg = bg_img

    # Concatenate all audio
    concat_audio = os.path.join(output_dir, "concat_audio.mp3")
    filter_parts = []
    input_args = []
    for i, af in enumerate(audio_files):
        input_args.extend(["-i", af["path"]])
        filter_parts.append(f"[{i}:a]apad=pad_dur=0.5[a{i}]")

    concat_inputs = "".join(f"[a{i}]" for i in range(len(audio_files)))
    filter_parts.append(f"{concat_inputs}concat=n={len(audio_files)}:v=0:a=1[outa]")
    filter_complex = ";".join(filter_parts)

    cmd = [FFMPEG_EXE, '-y'] + input_args + [
        '-filter_complex', filter_complex,
        '-map', '[outa]', '-c:a', 'libmp3lame', '-b:a', '128k',
        concat_audio
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    if not os.path.exists(concat_audio):
        print("  [ERROR] Audio concat failed")
        return None

    duration = get_audio_duration(concat_audio)

    # Create vertical video
    video_path = os.path.join(output_dir, f"{title}.mp4")
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    cmd = [
        FFMPEG_EXE, '-y', '-loop', '1', '-i', bg, '-i', concat_audio,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-pix_fmt', 'yuv420p',
        '-vf', vf, '-shortest', video_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"  [ERROR] FFmpeg: {result.stderr[:200]}")
    except Exception as e:
        print(f"  [ERROR] FFmpeg failed: {e}")

    # Cleanup temp audio
    try:
        os.remove(concat_audio)
    except:
        pass

    return video_path if os.path.exists(video_path) else None

def upload_to_youtube_shorts(video_path, title, description):
    """Upload shorts to YouTube."""
    try:
        import pickle
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        token_path = os.path.join(SCRIPT_DIR, "youtube_token.pickle")
        secret_path = os.path.join(SCRIPT_DIR, "client_secret.json")

        if not os.path.exists(token_path):
            print("  [ERROR] YouTube token not found")
            return None

        try:
            with open(token_path, "rb") as f:
                token_data = pickle.load(f)
        except (EOFError, pickle.UnpicklingError) as e:
            print(f"  [ERROR] Token file corrupted: {e}")
            return None

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=token_data.get("client_id") or token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=["https://www.googleapis.com/auth/youtube.upload"]
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["CatPodcast", "Shorts", "Cats", "Funny", "CatHub"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  Upload: {int(status.progress() * 100)}%")

        video_id = response["id"]
        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"  [OK] Uploaded: {url}")
        return {"success": True, "url": url, "video_id": video_id}

    except Exception as e:
        print(f"  [ERROR] Upload failed: {e}")
        return {"success": False, "error": str(e)}

def generate_short():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 60)
    print("CAT HUB PODCAST - Shorts Generator")
    print("=" * 60)

    topic = random.choice(SHORT_TOPICS)
    print(f"Topic: {topic['title']}")
    print(f"Lines: {len(topic['lines'])}")

    short_dir = os.path.join(OUTPUT_DIR, f"short_{timestamp}")
    audio_dir = os.path.join(short_dir, "audio")
    os.makedirs(short_dir, exist_ok=True)

    print("\n[1/3] Generating voiceover...")
    audio_files = generate_voiceover短线(topic["lines"], audio_dir)
    if not audio_files:
        print("  [ERROR] No audio generated")
        return None

    print(f"\n[2/3] Creating vertical video...")
    video_path = create_shorts_video(audio_files, short_dir, f"short_{timestamp}")
    if not video_path:
        print("  [ERROR] Video creation failed")
        return None

    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"  Video: {video_path} ({size_mb:.1f} MB)")

    print(f"\n[3/3] Uploading to YouTube...")
    title = f"CatHub Podcast Shorts - {topic['title']}"
    description = f"""{topic['title']}

Two cats discussing life, the universe, and why humans don't understand anything.

#CatHub #Shorts #Cats #Podcast #Funny"""

    upload_result = upload_to_youtube_shorts(video_path, title, description)

    metadata = {
        "title": topic["title"],
        "video": video_path,
        "upload": upload_result,
        "timestamp": timestamp,
        "format": "shorts_vertical_1080x1920",
    }

    meta_path = os.path.join(short_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print("\n" + "=" * 60)
    print("SHORTS COMPLETE!")
    print(f"  Title: {topic['title']}")
    print(f"  Video: {video_path}")
    if upload_result and upload_result.get("success"):
        print(f"  YouTube: {upload_result['url']}")
    print("=" * 60)

    return metadata

if __name__ == "__main__":
    generate_short()
