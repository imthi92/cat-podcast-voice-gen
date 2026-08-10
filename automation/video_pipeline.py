#!/usr/bin/env python3
"""
Automated Video Pipeline - Cat Podcast
Generates video from script: Audio + Subtitles + Visuals + Music + Thumbnail
Supports: Local Whisper, Colab webhook for VibeVoice, placeholder audio
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
import requests
import base64
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

# FFmpeg path (Windows - installed via winget)
FFMPEG_PATH = r"C:\Users\Imtiyaz\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin"
FFMPEG_EXE = os.path.join(FFMPEG_PATH, "ffmpeg.exe")
FFPROBE_EXE = os.path.join(FFMPEG_PATH, "ffprobe.exe")

# Add FFmpeg to PATH for this session
os.environ["PATH"] = FFMPEG_PATH + ";" + os.environ.get("PATH", "")

CONFIG = {
    "model_path": "microsoft/VibeVoice-1.5B",
    "speaker_mapping": {
        "Speaker 1": "Frank",  # Simba
        "Speaker 2": "Maya",   # Meow
    },
    "sample_rate": 24000,
    "video_resolution": (1280, 720),
    "subtitle_font": "Arial",
    "subtitle_fontsize": 24,
    "subtitle_color": "white",
    "subtitle_bg_color": "black@0.6",
    "music_volume": 0.12,
    "output_dir": "./output",
    "assets_dir": "./assets",
    # Colab webhook URL (set via environment variable or here)
    "colab_webhook_url": os.environ.get("COLAB_WEBHOOK_URL", ""),
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def run_command(cmd, check=True):
    """Run shell command and return output."""
    print(f"  Running: {cmd[:80]}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: {result.stderr[:200]}")
        return None
    return result.stdout


def ensure_dir(path):
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)
    return path


# ============================================================
# STEP 1: GENERATE AUDIO
# ============================================================

def generate_audio_via_colab(script_path, output_dir):
    """Generate audio using Colab webhook."""
    webhook_url = CONFIG.get("colab_webhook_url", "")
    if not webhook_url:
        print("  No Colab webhook URL configured")
        return None

    print(f"  Sending to Colab: {webhook_url[:50]}...")

    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()

        response = requests.post(
            webhook_url,
            json={
                "script": script_content,
                "filename": os.path.basename(script_path)
            },
            timeout=600
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                audio_base64 = result.get("audio_base64")
                if audio_base64:
                    # Decode base64 and save
                    audio_output = os.path.join(output_dir, "audio_from_colab.wav")
                    with open(audio_output, 'wb') as f:
                        f.write(base64.b64decode(audio_base64))
                    print(f"  Audio received from Colab")
                    return audio_output
                else:
                    print(f"  No audio in response")
        else:
            print(f"  Colab error: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"  Colab request failed: {e}")

    return None


def generate_audio_placeholder(script_path, output_dir):
    """Generate a placeholder audio file for testing."""
    print("  Generating placeholder audio for testing...")

    output_file = os.path.join(output_dir, "placeholder_audio.wav")

    # Create 30 seconds of silence
    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi',
        '-i', 'sine=frequency=0:duration=30',
        '-ar', '24000',
        '-ac', '1',
        output_file
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"  FFmpeg error: {result.stderr[:200]}")
    except Exception as e:
        print(f"  FFmpeg failed: {e}")

    if os.path.exists(output_file):
        print(f"  Placeholder audio created: {output_file}")
        return output_file

    return None


def generate_audio(script_path, output_dir):
    """Generate audio - try Colab first, fallback to placeholder."""
    print("\n[1/5] Generating audio...")

    # Try Colab webhook
    audio_path = generate_audio_via_colab(script_path, output_dir)
    if audio_path:
        return audio_path

    # Try local VibeVoice (if running in VibeVoice directory)
    if os.path.exists("demo/inference_from_file.py"):
        print("  Found local VibeVoice, trying local generation...")
        cmd = f"""python demo/inference_from_file.py \
            --model_path {CONFIG['model_path']} \
            --txt_path {script_path} \
            --speaker_names Frank Maya \
            --output_dir {output_dir} \
            --cfg_scale 1.3 \
            --device cuda"""

        run_command(cmd, check=False)

        # Find generated audio
        for f in os.listdir(output_dir):
            if f.endswith(".wav"):
                return os.path.join(output_dir, f)

    # Fallback: placeholder audio
    print("  No audio source available, using placeholder for testing...")
    return generate_audio_placeholder(script_path, output_dir)


# ============================================================
# STEP 2: GENERATE SUBTITLES (Whisper)
# ============================================================

def generate_subtitles_from_script(script_path, output_dir):
    """Generate SRT subtitles directly from script text (no audio needed)."""
    print("  Generating subtitles from script text...")

    srt_path = os.path.join(output_dir, "subtitles.srt")

    with open(script_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    srt_content = ""
    counter = 1
    time_offset = 0

    for line in lines:
        line = line.strip()
        if not line or ":" not in line:
            continue

        # Extract speaker and text
        parts = line.split(":", 1)
        if len(parts) < 2:
            continue

        speaker = parts[0].strip()
        text = parts[1].strip()

        if not text:
            continue

        # Calculate timestamps (approximate 3 seconds per line)
        start_time = time_offset
        end_time = time_offset + 3
        time_offset += 3.5

        # Format SRT timestamps
        start_str = f"00:{int(start_time)//60:02d}:{int(start_time)%60:02d},000"
        end_str = f"00:{int(end_time)//60:02d}:{int(end_time)%60:02d},000"

        srt_content += f"{counter}\n{start_str} --> {end_str}\n{text}\n\n"
        counter += 1

    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

    print(f"  Subtitles generated from script: {srt_path}")
    return srt_path


def generate_subtitles(audio_path, script_path, output_dir):
    """Generate SRT subtitles - try Whisper first, fallback to script."""
    print("\n[2/5] Generating subtitles...")

    # Try Whisper if audio is real (not placeholder)
    if audio_path and "placeholder" not in audio_path:
        srt_path = os.path.join(output_dir, "subtitles.srt")

        cmd = f"""whisper {audio_path} \
            --model base \
            --output_format srt \
            --output_dir {output_dir} \
            --language en"""

        run_command(cmd, check=False)

        audio_basename = os.path.splitext(os.path.basename(audio_path))[0]
        generated_srt = os.path.join(output_dir, f"{audio_basename}.srt")

        if os.path.exists(generated_srt):
            if generated_srt != srt_path:
                shutil.move(generated_srt, srt_path)
            print(f"  Subtitles generated via Whisper: {srt_path}")
            return srt_path

    # Fallback: generate from script
    return generate_subtitles_from_script(script_path, output_dir)


# ============================================================
# STEP 3: CREATE VIDEO (FFmpeg)
# ============================================================

def get_audio_duration(audio_path):
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        FFPROBE_EXE, '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except:
        return 30  # Default 30 seconds


def create_video(audio_path, subtitle_path, output_dir):
    """Create video with background image, audio, and subtitles."""
    print("\n[3/5] Creating video with FFmpeg...")

    video_output = os.path.join(output_dir, "final_video.mp4")
    duration = get_audio_duration(audio_path)
    w, h = CONFIG['video_resolution']

    # Use background image if available
    bg_image = os.path.join(CONFIG['assets_dir'], "background.jpg")
    if not os.path.exists(bg_image):
        # Try downloaded images
        downloaded = os.path.join(CONFIG['output_dir'].replace('output', ''), "downloaded_images")
        if os.path.exists(downloaded):
            for f in os.listdir(downloaded):
                if 'Wide' in f or 'studio' in f.lower():
                    bg_image = os.path.join(downloaded, f)
                    break
            if not os.path.exists(bg_image):
                for f in os.listdir(downloaded):
                    if f.endswith('.jpg'):
                        bg_image = os.path.join(downloaded, f)
                        break

    if os.path.exists(bg_image):
        print(f"  Using background: {os.path.basename(bg_image)}")
        cmd = [
            FFMPEG_EXE, '-y',
            '-loop', '1',
            '-i', bg_image,
            '-i', audio_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-vf', f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2',
            '-shortest',
            video_output
        ]
    else:
        print("  Using colored background (no image found)")
        cmd = [
            FFMPEG_EXE, '-y',
            '-f', 'lavfi',
            '-i', f'color=c=#1a1a2e:s={w}x{h}:d={duration}',
            '-i', audio_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-shortest',
            video_output
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"  FFmpeg stderr: {result.stderr[:500]}")
    except Exception as e:
        print(f"  FFmpeg failed: {e}")

    if os.path.exists(video_output):
        print(f"  Video created: {video_output}")
        return video_output

    print("  ERROR: Video creation failed")
    return None


def create_placeholder_background(output_path):
    """Create a simple podcast studio background."""
    ensure_dir(os.path.dirname(output_path))

    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi',
        '-i', 'color=c=#1a1a2e:s=1280x720:d=1',
        '-vf', "drawtext=text='The Simba Show':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=50,drawtext=text='Podcast Studio':fontcolor=#888888:fontsize=30:x=(w-text_w)/2:y=120,drawtext=text='Simba & Meow':fontcolor=#ffaa00:fontsize=40:x=(w-text_w)/2:y=h-100",
        '-frames:v', '1',
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"  Background creation failed: {e}")


# ============================================================
# STEP 4: ADD BACKGROUND MUSIC
# ============================================================

def add_music(video_path, output_dir):
    """Add background music to video."""
    print("\n[4/5] Adding background music...")

    music_file = os.path.join(CONFIG['assets_dir'], "background_music.mp3")
    final_output = os.path.join(output_dir, "final_with_music.mp4")

    if not os.path.exists(music_file):
        print("  No music file found, skipping...")
        return video_path

    cmd = [
        FFMPEG_EXE, '-y',
        '-i', video_path,
        '-i', music_file,
        '-filter_complex', f'[1:a]volume={CONFIG["music_volume"]}[m];[0:a][m]amix=inputs=2:duration=first',
        '-c:v', 'copy',
        final_output
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as e:
        print(f"  Music addition failed: {e}")

    if os.path.exists(final_output):
        print(f"  Music added: {final_output}")
        return final_output

    print("  Music addition failed, returning original")
    return video_path


# ============================================================
# STEP 5: CREATE THUMBNAIL
# ============================================================

def create_thumbnail(episode_title, output_dir):
    """Create YouTube thumbnail."""
    print("\n[5/5] Creating thumbnail...")

    thumbnail_path = os.path.join(output_dir, "thumbnail.png")

    # Simple thumbnail without special characters
    safe_title = episode_title[:50].replace("'", "").replace('"', '')

    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi',
        '-i', 'color=c=#ff6b35:s=1280x720:d=1',
        '-frames:v', '1',
        thumbnail_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"  Thumbnail creation failed: {e}")

    if os.path.exists(thumbnail_path):
        print(f"  Thumbnail created: {thumbnail_path}")
        return thumbnail_path

    print("  WARNING: Thumbnail creation failed, using video frame instead")
    return None


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(script_path, episode_title=None):
    """Run the complete video generation pipeline."""
    print("=" * 60)
    print("CAT PODCAST - AUTOMATED VIDEO PIPELINE")
    print("=" * 60)

    # Setup directories
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(CONFIG['output_dir'], f"episode_{timestamp}")
    ensure_dir(output_dir)
    ensure_dir(CONFIG['assets_dir'])

    # Use episode title or extract from filename
    if not episode_title:
        episode_title = os.path.splitext(os.path.basename(script_path))[0]
        episode_title = episode_title.replace("_", " ").title()

    print(f"\nScript: {script_path}")
    print(f"Episode: {episode_title}")
    print(f"Output: {output_dir}")

    # Run pipeline steps
    results = {
        "script": script_path,
        "episode_title": episode_title,
        "output_dir": output_dir,
        "timestamp": timestamp,
    }

    # Step 1: Audio
    audio_path = generate_audio(script_path, output_dir)
    if not audio_path:
        print("\nPIPELINE FAILED at audio generation")
        return None
    results["audio"] = audio_path

    # Step 2: Subtitles
    subtitle_path = generate_subtitles(audio_path, script_path, output_dir)
    if not subtitle_path:
        print("\nPIPELINE FAILED at subtitle generation")
        return None
    results["subtitles"] = subtitle_path

    # Step 3: Video
    video_path = create_video(audio_path, subtitle_path, output_dir)
    if not video_path:
        print("\nPIPELINE FAILED at video creation")
        return None
    results["video"] = video_path

    # Step 4: Music
    final_video = add_music(video_path, output_dir)
    results["final_video"] = final_video

    # Step 5: Thumbnail
    thumbnail_path = create_thumbnail(episode_title, output_dir)
    results["thumbnail"] = thumbnail_path

    # Save metadata
    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE!")
    print("=" * 60)
    print(f"\nFinal video: {final_video}")
    print(f"Thumbnail: {thumbnail_path}")
    print(f"Metadata: {metadata_path}")

    return results


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python video_pipeline.py <script.txt> [episode title]")
        print("Example: python video_pipeline.py scripts/episode_01.txt 'Why Humans Work So Much'")
        sys.exit(1)

    script_path = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else None

    run_pipeline(script_path, title)