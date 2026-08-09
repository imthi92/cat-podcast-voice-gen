# Cat Podcast Project - Status & Reference

## Project Overview
- **Channel:** @thesimbashows (YouTube)
- **Characters:** Simba (Speaker 1, Frank voice) & Meow (Speaker 2, Maya voice)
- **Theme:** Office gossip podcast - two cats secretly recording in the office
- **GitHub:** https://github.com/imthi92/cat-podcast-voice-gen

## Current Status: Aug 9, 2026

### What Works ✅
1. **AI Script Generation** - OpenAI generates funny cat podcast scripts
2. **Video Pipeline** - FFmpeg creates video with colored background + audio + subtitles
3. **YouTube Upload** - OAuth2 authenticated, uploads work
4. **Thumbnail Generation** - FFmpeg creates thumbnails
5. **Colab Server** - Flask + ngrok webhook is running

### What's Broken ❌
1. **Colab Audio Generation** - Returns 500 error: `No such file or directory: './outputs/episode_script_generated.wav'`
   - The `os.makedirs('./outputs', exist_ok=True)` fix was added but user may not have re-run Cell 2
   - OR the inference command is failing silently

### Blockers
- The Colab notebook needs to be re-run with fresh session to pick up code changes
- The user is frustrated and wants to continue later

## Files & Locations

### Local PC (C:\Users\Imtiyaz\Documents\New OpenCode Project\)
```
automation/
├── master_automation.py      # Main entry point - run this
├── video_pipeline.py         # Audio + video + thumbnail generation
├── youtube_upload.py         # YouTube OAuth2 upload
├── scheduler.py              # For scheduled runs
├── run_daily.bat             # Windows batch for Task Scheduler
├── episodes/                 # Generated scripts
├── output/                   # Generated videos
└── youtube_token.pickle      # YouTube auth (in .gitignore)

cat_podcast_vibevoice_colab.ipynb  # Colab notebook (push to GitHub)
colab_webhook.py                    # Standalone webhook code
scripts/                            # Episode scripts
docs/                               # Documentation
```

### GitHub Repository
- https://github.com/imthi92/cat-podcast-voice-gen
- All code pushed there

## API Keys & Credentials

### OpenAI
- **Key:** Set via environment variable `OPENAI_API_KEY`
- **Model:** gpt-3.5-turbo

### ngrok
- **Authtoken:** Set in Colab notebook
- **Dashboard:** https://dashboard.ngrok.com

### YouTube
- **OAuth2:** `automation/client_secret.json` and `automation/youtube_token.pickle`
- **Channel:** @thesimbashowss

## How to Run (When Ready)

### Step 1: Start Colab Server
1. Open: https://colab.research.google.com/github/imthi92/cat-podcast-voice-gen/blob/master/cat_podcast_vibevoice_colab.ipynb
2. Click **Runtime → Restart session** (important!)
3. Run Cell 1 (install - takes 2-3 min)
4. Run Cell 2 (server) - wait for: `YOUR WEBHOOK URL: https://xxxx.ngrok-free.dev/generate`
5. Copy the URL

### Step 2: Run Automation on PC
```powershell
cd "C:\Users\Imtiyaz\Documents\New OpenCode Project\automation"
$env:COLAB_WEBHOOK_URL="https://YOUR-URL/generate"
$env:OPENAI_API_KEY="YOUR-OPENAI-KEY"
python master_automation.py
```

## Next Steps
1. **Fix Colab audio issue** - Re-run Colab session and test generate endpoint
2. **Verify audio generation works end-to-end**
3. **Create batch of first 5 episodes** for channel launch
4. **Set up scheduled automation** for daily uploads

## Episode Scripts Written
- episode_02_the_manager_listened.txt
- episode_03_simbas_crush.txt
- episode_04_about_our_owners.txt
- episode_05_hometown_friends.txt
- episode_06_hiking_trip.txt
- episode_07_fan_following.txt
- episode_08_department_rivalry.txt
- episode_09_office_crush_update.txt

## Colab Notebook Code (Current)
```python
# Cell 1: Install
!apt-get update -qq > /dev/null
!apt-get install -y ffmpeg -qq > /dev/null
!pip install flask pyngrok -qq
import os
if not os.path.exists('VibeVoice'):
    !git clone https://github.com/vibevoice-community/VibeVoice.git > /dev/null 2>&1
%cd VibeVoice
!pip install -e . -qq
print('Setup done')

# Cell 2: Server
import subprocess as sp
sp.run('pkill -f ngrok', shell=True, capture_output=True)
sp.run('rm -rf /tmp/ngrok*', shell=True, capture_output=True)

from flask import Flask, request, jsonify
from pyngrok import ngrok
import subprocess
import base64
import traceback

ngrok.set_auth_token('YOUR-NGROK-AUTHTOKEN')

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        script = data.get('script', '')
        filename = data.get('filename', 'episode.txt')
        with open(filename, 'w') as f:
            f.write(script)
        os.makedirs('./outputs', exist_ok=True)
        cmd = 'python demo/inference_from_file.py --model_path microsoft/VibeVoice-1.5B --txt_path ' + filename + ' --speaker_names Frank Maya --output_dir ./outputs --cfg_scale 1.3 --device cuda'
        subprocess.run(cmd, shell=True, check=True)
        with open('./outputs/episode_script_generated.wav', 'rb') as f:
            audio = base64.b64encode(f.read()).decode('utf-8')
        return jsonify({'status': 'success', 'audio_base64': audio, 'sample_rate': 24000})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()}), 500

url = ngrok.connect(5000)
print('\nYOUR WEBHOOK URL: ' + str(url) + '/generate\n')
app.run(port=5000)
```

## Test Videos Uploaded (All Private)
- https://www.youtube.com/watch?v=_apIjYLNIfY
- https://www.youtube.com/watch?v=EMm1cOoD7_A
- https://www.youtube.com/watch?v=20mro45oqx0
- https://www.youtube.com/watch?v=I7auQCywzTA
- https://www.youtube.com/watch?v=ULX3GCtRUzo
- https://www.youtube.com/watch?v=4VPoOVBNXn8
