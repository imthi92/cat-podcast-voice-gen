# Cell 1: Setup
!apt-get update -qq > /dev/null
!apt-get install -y ffmpeg -qq > /dev/null
import os
if not os.path.exists('VibeVoice'):
    !git clone https://github.com/vibevoice-community/VibeVoice.git > /dev/null 2>&1
%cd VibeVoice
!pip install -e . -qq
print("Setup done")

# Cell 2: Webhook server
!pip install flask pyngrok -qq
from flask import Flask, request, jsonify
from pyngrok import ngrok
import subprocess
import base64

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        script = data.get('script', '')
        filename = data.get('filename', 'episode.txt')
        
        # Save script
        with open(filename, 'w') as f:
            f.write(script)
        
        # Generate audio
        cmd = "python demo/inference_from_file.py --model_path microsoft/VibeVoice-1.5B --txt_path " + filename + " --speaker_names Frank Maya --output_dir ./outputs --cfg_scale 1.3 --device cuda"
        subprocess.run(cmd, shell=True, check=True)
        
        # Read and return audio as base64
        audio_path = "./outputs/episode_script_generated.wav"
        with open(audio_path, 'rb') as f:
            audio_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        return jsonify({
            "status": "success", 
            "audio_base64": audio_base64,
            "sample_rate": 24000
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

from pyngrok import ngrok
ngrok.set_auth_token("3Hg6t6KMD50TMDe7WJBy6kxICHC_34gzH8g6o9N4V7We6VDgm")
public_url = ngrok.connect(5000)
print("\nYOUR WEBHOOK URL: " + str(public_url) + "/generate\n")
app.run(port=5000)
