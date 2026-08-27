#!/bin/bash
# Cat Podcast — Deepnote Setup Script
# Run this on a fresh Deepnote server to restore everything
# Usage: bash setup.sh

echo "============================================"
echo "  CAT PODCAST — FULL PIPELINE SETUP"
echo "============================================"
echo ""

# 1. System dependencies
echo "[1/6] Installing system dependencies..."
apt update && apt install -y ffmpeg git python3-pip python3-venv curl > /dev/null 2>&1

# 2. Python dependencies
echo "[2/6] Installing Python packages..."
cd /root/cat-podcast-voice-gen
pip install -r automation/requirements.txt > /dev/null 2>&1

# 3. Verify FFmpeg
echo "[3/6] Verifying FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    echo "  [OK] FFmpeg installed: $(ffmpeg -version 2>&1 | head -1)"
else
    echo "  [FAIL] FFmpeg not found"
fi

# 4. Verify Edge TTS
echo "[4/6] Verifying Edge TTS..."
if python3 -c "import edge_tts" 2>/dev/null; then
    echo "  [OK] Edge TTS ready"
else
    echo "  [FAIL] Edge TTS not installed"
fi

# 5. Verify faster-whisper
echo "[5/6] Verifying faster-whisper..."
if python3 -c "import faster_whisper" 2>/dev/null; then
    echo "  [OK] faster-whisper ready"
else
    echo "  [FAIL] faster-whisper not installed"
fi

# 6. Test audio generation
echo "[6/6] Testing audio generation..."
edge-tts --voice en-US-GuyNeural --text "Test audio" --write-media /tmp/test_audio.mp3 2>/dev/null
if [ -f /tmp/test_audio.mp3 ]; then
    echo "  [OK] Audio generation works"
    rm /tmp/test_audio.mp3
else
    echo "  [FAIL] Audio generation failed"
fi

# 7. Verify Groq
echo "[7/7] Verifying Groq..."
if python3 -c "import groq" 2>/dev/null; then
    echo "  [OK] Groq ready (set GROQ_API_KEY env var)"
else
    echo "  [FAIL] Groq not installed"
fi

echo ""
echo "============================================"
echo "  SETUP COMPLETE"
echo "============================================"
echo ""
echo "Pipeline location: /root/cat-podcast-voice-gen"
echo ""
echo "Commands:"
echo "  Generate episode:  python automation/generate_episode.py"
echo "  Generate + upload: python automation/generate_episode.py --publish"
echo "  Batch 5 episodes:  python automation/generate_episode.py --batch 5"
echo ""
echo "Fallback chain:"
echo "  Script: Groq (Llama 3.3) -> HuggingFace -> Template"
echo "  Audio: Colab XTTS -> Edge TTS -> gTTS"
echo "  Video: SadTalker -> DAWN -> FFmpeg Ken Burns"
echo "  Subs:  Whisper -> faster-whisper -> whisper.cpp"
echo "============================================"
