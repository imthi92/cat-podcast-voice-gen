"""
Cat Podcast — Colab Webhook Bridge
Runs on Deepnote, connects to Colab for GPU tasks.
Falls back to CPU methods if Colab is unavailable.
"""

import os
import sys
import json
import subprocess
import base64
from pathlib import Path

# Config
COLAB_WEBHOOK_URL = os.environ.get("COLAB_WEBHOOK_URL", "")
FALLBACK_DIR = Path("/tmp/cat-podcast-fallback")
FALLBACK_DIR.mkdir(exist_ok=True)

def generate_audio_edge_tts(text, output_path):
    """Method 2: Edge TTS (CPU, no GPU needed)"""
    try:
        cmd = f'edge-tts --voice en-US-GuyNeural --text "{text}" --write-media {output_path}'
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        if os.path.exists(output_path):
            print(f"  [Edge TTS] Audio generated: {output_path}")
            return True
    except Exception as e:
        print(f"  [Edge TTS] Failed: {e}")
    return False

def generate_audio_gtts(text, output_path):
    """Method 3: gTTS (CPU, basic quality)"""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang='en')
        tts.save(output_path)
        print(f"  [gTTS] Audio generated: {output_path}")
        return True
    except Exception as e:
        print(f"  [gTTS] Failed: {e}")
    return False

def generate_video_ffmpeg(audio_path, image_path, output_path):
    """Method 3: FFmpeg Ken Burns (CPU, no GPU needed)"""
    try:
        cmd = (
            f'ffmpeg -loop 1 -i {image_path} -i {audio_path} '
            f'-vf "scale=8000:-1,zoompan=z=\'min(zoom+0.001,1.5)\':d=25*60:s=1920x1080" '
            f'-c:v libx264 -tune stillimage -c:a aac -shortest '
            f'-pix_fmt yuv420p {output_path} -y'
        )
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        if os.path.exists(output_path):
            print(f"  [FFmpeg] Video generated: {output_path}")
            return True
    except Exception as e:
        print(f"  [FFmpeg] Failed: {e}")
    return False

def generate_subtitles_faster_whisper(audio_path, output_path):
    """Method 2: faster-whisper (CPU, fast)"""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("medium", device="cpu")
        segments, info = model.transcribe(audio_path)
        
        with open(output_path, 'w') as f:
            for i, segment in enumerate(segments):
                start = segment.start
                end = segment.end
                text = segment.text.strip()
                f.write(f"{i+1}\n")
                f.write(f"{format_time(start)} --> {format_time(end)}\n")
                f.write(f"{text}\n\n")
        
        print(f"  [faster-whisper] Subtitles generated: {output_path}")
        return True
    except Exception as e:
        print(f"  [faster-whisper] Failed: {e}")
    return False

def format_time(seconds):
    """Format seconds to SRT timestamp"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def try_colab(text, filename):
    """Method 1: Try Colab webhook first"""
    if not COLAB_WEBHOOK_URL:
        print("  [Colab] No webhook URL set, skipping")
        return None
    
    try:
        import requests
        resp = requests.post(
            f"{COLAB_WEBHOOK_URL}/generate",
            json={"script": text, "filename": filename},
            timeout=120
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                audio_b64 = data["audio_base64"]
                audio_bytes = base64.b64decode(audio_b64)
                output_path = str(FALLBACK_DIR / f"{filename}.wav")
                with open(output_path, 'wb') as f:
                    f.write(audio_bytes)
                print(f"  [Colab] Audio generated: {output_path}")
                return output_path
    except Exception as e:
        print(f"  [Colab] Failed: {e}")
    return None

def generate_audio(text, filename="episode"):
    """Generate audio with fallback chain: Colab -> Edge TTS -> gTTS"""
    print("[Audio] Starting generation...")
    
    # Method 1: Colab
    result = try_colab(text, filename)
    if result:
        return result
    
    # Method 2: Edge TTS
    output_path = str(FALLBACK_DIR / f"{filename}.mp3")
    if generate_audio_edge_tts(text, output_path):
        return output_path
    
    # Method 3: gTTS
    output_path = str(FALLBACK_DIR / f"{filename}.mp3")
    if generate_audio_gtts(text, output_path):
        return output_path
    
    print("  [FAIL] All audio methods failed")
    return None

def generate_video(audio_path, image_path, filename="episode"):
    """Generate video with fallback chain: Colab SadTalker -> FFmpeg Ken Burns"""
    print("[Video] Starting generation...")
    
    # Method 1: Try Colab for SadTalker
    if COLAB_WEBHOOK_URL:
        try:
            import requests
            resp = requests.post(
                f"{COLAB_WEBHOOK_URL}/generate-video",
                json={"audio": audio_path, "image": image_path},
                timeout=300
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    output_path = str(FALLBACK_DIR / f"{filename}.mp4")
                    # Download video from Colab
                    video_url = data.get("video_url")
                    if video_url:
                        video_resp = requests.get(video_url, timeout=60)
                        with open(output_path, 'wb') as f:
                            f.write(video_resp.content)
                        print(f"  [Colab SadTalker] Video generated: {output_path}")
                        return output_path
        except Exception as e:
            print(f"  [Colab SadTalker] Failed: {e}")
    
    # Method 2: FFmpeg Ken Burns
    output_path = str(FALLBACK_DIR / f"{filename}.mp4")
    if generate_video_ffmpeg(audio_path, image_path, output_path):
        return output_path
    
    print("  [FAIL] All video methods failed")
    return None

def generate_subtitles(audio_path, filename="episode"):
    """Generate subtitles with fallback chain: Whisper -> faster-whisper"""
    print("[Subtitles] Starting generation...")
    
    # Method 1: Whisper (if GPU available)
    try:
        import whisper
        model = whisper.load_model("medium")
        result = model.transcribe(audio_path)
        output_path = str(FALLBACK_DIR / f"{filename}.srt")
        
        with open(output_path, 'w') as f:
            for i, segment in enumerate(result["segments"]):
                start = segment["start"]
                end = segment["end"]
                text = segment["text"].strip()
                f.write(f"{i+1}\n")
                f.write(f"{format_time(start)} --> {format_time(end)}\n")
                f.write(f"{text}\n\n")
        
        print(f"  [Whisper] Subtitles generated: {output_path}")
        return output_path
    except Exception as e:
        print(f"  [Whisper] Failed: {e}")
    
    # Method 2: faster-whisper
    output_path = str(FALLBACK_DIR / f"{filename}.srt")
    if generate_subtitles_faster_whisper(audio_path, output_path):
        return output_path
    
    print("  [FAIL] All subtitle methods failed")
    return None

# Main entry point
if __name__ == "__main__":
    print("Cat Podcast — Fallback Audio/Video Generator")
    print("Methods: Colab -> Edge TTS -> gTTS | SadTalker -> FFmpeg")
    print("")
    
    if len(sys.argv) > 1:
        text = sys.argv[1]
        audio = generate_audio(text)
        if audio:
            print(f"\nFinal audio: {audio}")
    else:
        print("Usage: python fallback_generator.py 'text to generate'")
