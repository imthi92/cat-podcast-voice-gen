#!/usr/bin/env python3
"""
Automated Video Pipeline - Cat Podcast
Generates video from script: Audio + Subtitles + Visuals + Music + Thumbnail
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

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
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def run_command(cmd, check=True):
    """Run shell command and return output."""
    print(f"  Running: {cmd[:80]}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        return None
    return result.stdout


def ensure_dir(path):
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)
    return path


# ============================================================
# STEP 1: GENERATE AUDIO (VibeVoice)
# ============================================================

def generate_audio(script_path, output_dir):
    """Generate audio from script using VibeVoice."""
    print("\n[1/5] Generating audio with VibeVoice...")

    cmd = f"""python demo/inference_from_file.py \
        --model_path {CONFIG['model_path']} \
        --txt_path {script_path} \
        --speaker_names Frank Maya \
        --output_dir {output_dir} \
        --cfg_scale 1.3 \
        --device cuda"""

    result = run_command(cmd)

    # Find the generated audio file
    audio_file = os.path.join(output_dir, "episode_script_generated.wav")
    if os.path.exists(audio_file):
        print(f"  Audio generated: {audio_file}")
        return audio_file

    # Try to find any wav file in output
    for f in os.listdir(output_dir):
        if f.endswith(".wav"):
            audio_path = os.path.join(output_dir, f)
            print(f"  Audio generated: {audio_path}")
            return audio_path

    print("  ERROR: Audio generation failed")
    return None


# ============================================================
# STEP 2: GENERATE SUBTITLES (Whisper)
# ============================================================

def generate_subtitles(audio_path, output_dir):
    """Generate SRT subtitles from audio using Whisper."""
    print("\n[2/5] Generating subtitles with Whisper...")

    srt_path = os.path.join(output_dir, "subtitles.srt")

    cmd = f"""whisper {audio_path} \
        --model base \
        --output_format srt \
        --output_dir {output_dir} \
        --language en"""

    result = run_command(cmd)

    # Whisper saves as audio_name.srt
    audio_basename = os.path.splitext(os.path.basename(audio_path))[0]
    generated_srt = os.path.join(output_dir, f"{audio_basename}.srt")

    if os.path.exists(generated_srt):
        if generated_srt != srt_path:
            shutil.move(generated_srt, srt_path)
        print(f"  Subtitles generated: {srt_path}")
        return srt_path

    if os.path.exists(srt_path):
        print(f"  Subtitles generated: {srt_path}")
        return srt_path

    print("  ERROR: Subtitle generation failed")
    return None


# ============================================================
# STEP 3: CREATE VIDEO (FFmpeg)
# ============================================================

def get_audio_duration(audio_path):
    """Get audio duration in seconds using ffprobe."""
    cmd = f"""ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 {audio_path}"""
    result = run_command(cmd)
    try:
        return float(result.strip())
    except:
        return 180  # Default 3 minutes


def create_video(audio_path, subtitle_path, output_dir):
    """Create video with background image, audio, and subtitles."""
    print("\n[3/5] Creating video with FFmpeg...")

    video_output = os.path.join(output_dir, "final_video.mp4")
    background = os.path.join(CONFIG['assets_dir'], "studio_background.png")

    # Check if background exists, create placeholder if not
    if not os.path.exists(background):
        print("  Creating placeholder background...")
        create_placeholder_background(background)

    duration = get_audio_duration(audio_path)
    w, h = CONFIG['video_resolution']

    # Method: Use moviepy via Python (more reliable for subtitles)
    cmd = f"""python3 -c "
from moviepy.editor import *
from moviepy.video.tools.subtitles import SubtitlesClip

# Load components
audio = AudioFileClip('{audio_path}')
background = ImageClip('{background}').set_duration(audio.duration).resize(({w}, {h}))

# Load subtitles
subtitles = SubtitlesClip('{subtitle_path}', lambda txt: TextClip(txt, font='{CONFIG['subtitle_font']}', fontsize={CONFIG['subtitle_fontsize']}, color='{CONFIG['subtitle_color']}'))

# Composite video
video = CompositeVideoClip([background, subtitles.set_position(('center', 'bottom'))])
video = video.set_audio(audio)

# Write output
video.write_videofile('{video_output}', fps=24, codec='libx264', audio_codec='aac', threads=4)
" """

    result = run_command(cmd, check=False)

    # Fallback: FFmpeg without styled subtitles
    if not os.path.exists(video_output):
        print("  Trying FFmpeg fallback...")
        cmd_ffmpeg = f"""ffmpeg -y \
            -loop 1 -i {background} \
            -i {audio_path} \
            -vf "scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2" \
            -c:v libx264 -tune stillimage -c:a aac -b:a 192k \
            -pix_fmt yuv420p -shortest \
            -t {duration} \
            {video_output}"""
        run_command(cmd_ffmpeg)

    if os.path.exists(video_output):
        print(f"  Video created: {video_output}")
        return video_output

    print("  ERROR: Video creation failed")
    return None


def create_placeholder_background(output_path):
    """Create a simple podcast studio background."""
    ensure_dir(os.path.dirname(output_path))

    cmd = f"""ffmpeg -y -f lavfi -i "color=c=#1a1a2e:s=1280x720:d=1" \
        -vf "drawtext=text='The Simba Show':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=50,\
drawtext=text='Podcast Studio':fontcolor=#888888:fontsize=30:x=(w-text_w)/2:y=120,\
drawtext=text='Simba & Meow':fontcolor=#ffaa00:fontsize=40:x=(w-text_w)/2:y=h-100" \
        -frames:v 1 {output_path}"""
    run_command(cmd)


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

    cmd = f"""ffmpeg -y \
        -i {video_path} \
        -i {music_file} \
        -filter_complex "[1:a]volume={CONFIG['music_volume']}[m];[0:a][m]amix=inputs=2:duration=first" \
        -c:v copy \
        {final_output}"""

    result = run_command(cmd, check=False)

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

    # Check for custom thumbnail template
    template = os.path.join(CONFIG['assets_dir'], "thumbnail_template.png")

    if os.path.exists(template):
        # Use template and add text
        cmd = f"""ffmpeg -y -i {template} \
            -vf "drawtext=text='{episode_title}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h-150:borderw=3:bordercolor=black" \
            {thumbnail_path}"""
        run_command(cmd)
    else:
        # Create simple thumbnail
        cmd = f"""ffmpeg -y -f lavfi -i "color=c=#ff6b35:s=1280x720:d=1" \
            -vf "drawtext=text='The Simba Show':fontcolor=white:fontsize=72:x=(w-text_w)/2:y=50,\
drawtext=text='{episode_title}':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=(h-text_h)/2:borderw=2:bordercolor=black,\
drawtext=text='Simba & Meow Podcast':fontcolor=#000000:fontsize=28:x=(w-text_w)/2:y=h-80" \
            -frames:v 1 {thumbnail_path}"""
        run_command(cmd)

    if os.path.exists(thumbnail_path):
        print(f"  Thumbnail created: {thumbnail_path}")
        return thumbnail_path

    print("  ERROR: Thumbnail creation failed")
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
    subtitle_path = generate_subtitles(audio_path, output_dir)
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