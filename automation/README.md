# Cat Podcast Automation

Fully automated pipeline: Script -> Audio -> Video -> YouTube

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run single episode
python master_automation.py

# 3. Run with specific topic
python master_automation.py --topic "The printer jam conspiracy"

# 4. Run batch of 5 episodes
python master_automation.py --batch 5

# 5. Run and publish to YouTube
python master_automation.py --publish
```

## Environment Variables

```bash
# Required for AI script generation
export OPENAI_API_KEY="your-key-here"

# Required for YouTube upload
# Download client_secret.json from Google Cloud Console
export YOUTUBE_CLIENT_SECRET="path/to/client_secret.json"

# Optional: Colab webhook URL (for remote audio generation)
export COLAB_WEBHOOK_URL="your-colab-webhook-url"
```

## Files

| File | Purpose |
|------|---------|
| `master_automation.py` | Main entry point - runs everything |
| `video_pipeline.py` | Audio + subtitles + video generation |
| `youtube_upload.py` | YouTube API upload |
| `n8n_workflow.json` | Importable n8n workflow |
| `requirements.txt` | Python dependencies |

## Pipeline Flow

```
1. Pick topic (random or specified)
      |
2. Generate script (AI or template)
      |
3. Generate audio (VibeVoice on Colab)
      |
4. Generate subtitles (Whisper)
      |
5. Create video (FFmpeg + moviepy)
      |
6. Create thumbnail
      |
7. Upload to YouTube
      |
8. Mark as processed
```

## n8n Integration

Import `n8n_workflow.json` into your n8n instance:

1. Open n8n (http://localhost:5678)
2. Click menu -> Import from File
3. Select `n8n_workflow.json`
4. Configure credentials:
   - OpenAI API key
   - YouTube OAuth2
5. Activate workflow

## First Time Setup

### YouTube API Setup

1. Go to https://console.cloud.google.com
2. Create project
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials
5. Download client_secret.json
6. Place in automation folder

### OpenAI Setup

1. Go to https://platform.openai.com
2. Get API key
3. Set environment variable

### Colab Webhook (Optional)

For remote audio generation, run this in Colab:

```python
from flask import Flask, request
from pyngrok import ngrok

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate():
    # ... your VibeVoice code ...
    return {"status": "success", "audio_path": "output.wav"}

public_url = ngrok.connect(5000)
print(f"Webhook: {public_url}")
app.run(port=5000)
```

## Troubleshooting

### Audio generation fails
- Check Colab GPU is enabled
- Verify VibeVoice is installed

### YouTube upload fails
- Check client_secret.json exists
- Verify OAuth2 credentials
- Check API quotas

### Video creation fails
- Verify FFmpeg is installed: `ffmpeg -version`
- Check moviepy is installed: `pip show moviepy`