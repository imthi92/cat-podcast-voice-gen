#!/usr/bin/env python3
"""
Cat Podcast - Episode Generator v4 (All Free, No Local Dependencies)
Edge TTS + FFmpeg with sound effects, async audio, free LLM scripts
"""

import os
import sys
import json
import subprocess
import asyncio
import glob
import pickle
import random
import shutil
import hashlib
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "scripts")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
PROCESSED_FILE = os.path.join(BASE_DIR, "processed_episodes.json")
COUNTER_FILE = os.path.join(BASE_DIR, "episode_counter.json")
IMAGES_DIR = os.path.join(BASE_DIR, "downloaded_images")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

VOICES = {
    "Speaker 1": "en-US-GuyNeural",      # Simba - confident, Marketing
    "Speaker 2": "en-US-JennyNeural",    # Meow - sarcastic, Finance
    "Imti": "en-US-ChristopherNeural",   # Imti - IT guy, technical
    "Zulfi": "en-US-ChristopherNeural",  # Zulfi - HR manager, formal
}

# Character descriptions for scripts
CHARACTERS = {
    "Speaker 1": "Simba (Marketing, confident, silly, exaggerates stories)",
    "Speaker 2": "Meow (Finance, smart, sarcastic, dry wit)",
    "Imti": "Imti (IT guy, technical, always fixing things, stressed)",
    "Zulfi": "Zulfi (HR manager, formal, corporate speak, manages people)",
}

# FFmpeg - auto-detect from PATH or common locations
def _find_ffmpeg():
    """Find ffmpeg binary, trying PATH first then common install locations."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe
    
    common_paths = [
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        os.path.expanduser(r"~\scoop\shims"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin"),
    ]
    for p in common_paths:
        f = os.path.join(p, "ffmpeg.exe")
        fp = os.path.join(p, "ffprobe.exe")
        if os.path.exists(f) and os.path.exists(fp):
            os.environ["PATH"] = p + ";" + os.environ.get("PATH", "")
            return f, fp
    
    return "ffmpeg", "ffprobe"

FFMPEG_EXE, FFPROBE_EXE = _find_ffmpeg()

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

def get_next_episode_number():
    """Persistent episode counter that survives re-runs."""
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'r') as f:
            counter = json.load(f)
        counter["next"] = counter.get("next", 1) + 1
    else:
        counter = {"next": 2}
    
    with open(COUNTER_FILE, 'w') as f:
        json.dump(counter, f, indent=2)
    
    return counter["next"] - 1

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
    # New topics featuring Imti and Zulfi
    "Imti's computer crashes during demo",
    "Zulfi's mandatory HR training session",
    "The internet is down - blame Imti",
    "Zulfi sends another all-staff email",
    "Imti's server room is overheating",
    "Zulfi's performance review nightmare",
    "Imti forgot to back up the data",
    "Zulfi's new office policy nobody follows",
    "Imti's cable management disaster",
    "Zulfi's team building exercise fails",
    "Imti's lunch stolen from IT fridge",
    "Zulfi's dress code enforcement chaos",
    "Imti's backup tapes are missing",
    "Zulfi's mandatory fun Friday",
    "Imti's emergency patch at 3 AM",
    "Zulfi's employee satisfaction survey",
]

def generate_script_with_ai():
    """Generate a unique script using free Hugging Face Inference API."""
    import requests

    api_key = os.environ.get("HF_API_KEY", os.environ.get("HUGGINGFACE_API_KEY", ""))
    if not api_key:
        print("  No Hugging Face API key, using template")
        return generate_script_from_template()

    topic = random.choice(OFFICE_TOPICS)

    data = load_processed()
    recent_topics = [ep.get("metadata", {}).get("topic", "") for ep in data.get("episodes", [])[-5:]]
    attempts = 0
    while topic in recent_topics and attempts < 10:
        topic = random.choice(OFFICE_TOPICS)
        attempts += 1

    print(f"  [AI] Generating script about: {topic}")

    try:
        prompt = f"""Write a natural, funny cat podcast conversation about: {topic}

Characters:
- Simba (Speaker 1): Confident, silly, works in Marketing, tells exaggerated stories
- Meow (Speaker 2): Smart, sarcastic, works in Finance, rolls eyes at Simba
- Imti: IT guy, technical, always stressed about servers
- Zulfi: HR manager, formal, corporate speak, sends too many emails

RULES:
- Include fillers: "hmm", "oh", "um", "wait", "right?", "you know?"
- Include reactions: "haha", "oh my god", "no way", "seriously?"
- Include interruptions and overlapping thoughts
- Include laughter: "haha", "lol", "hehe"
- Some lines short (1-3 words), some long rants
- Use format: Speaker 1:, Speaker 2:, Imti:, or Zulfi:
- 2-3 characters per episode
- 35-50 lines
- NO stage directions, just raw dialogue
- Make it sound like friends chatting, not reading

Conversation:"""

        response = requests.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 1500, "temperature": 0.95, "do_sample": True}},
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                script = result[0].get("generated_text", "")
            else:
                script = str(result)
        else:
            print(f"  [AI] API error {response.status_code}: {response.text[:200]}")
            return generate_script_from_template()

        lines = [l.strip() for l in script.split("\n") if l.strip() and ":" in l]
        lines = [l for l in lines if any(s in l for s in ["Speaker 1", "Speaker 2", "Imti", "Zulfi"])]

        if len(lines) < 10:
            print("  [AI] Script too short, using template")
            return generate_script_from_template()

        print(f"  [AI] Generated {len(lines)} lines")

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

    # Templates with 2-3 characters including Imti and Zulfi
    templates = [
        # Simba + Meow + Imti
        f"""Speaker 1: Oh my god, did you hear about the {topic.lower()}?
Speaker 2: Wait, what? What happened?
Speaker 1: It's... it's crazy. Like, seriously crazy.
Speaker 2: You're scaring me. What happened?
Speaker 1: So basically... okay, so you know how the office is, right?
Speaker 2: Yeah...?
Speaker 1: Well, apparently... someone... um... someone did something.
Speaker 2: Someone did something. That's very specific.
Speaker 1: I'm getting there! Don't rush me!
Speaker 2: You literally just said "oh my god" and now you're stalling.
Imti: Hey guys, what's going on?
Speaker 1: Imti! Perfect timing! Did you fix the printer yet?
Imti: The printer? Again? What happened this time?
Speaker 2: Simba was telling me about the {topic.lower()}.
Imti: Oh, that. Yeah, I saw the email. Not my problem though.
Speaker 1: Not your problem? You're IT!
Imti: I fix computers, not office drama. Besides, I'm busy with the server.
Speaker 2: The server? What's wrong with it?
Imti: Nothing... yet. But it's making weird noises.
Speaker 1: Ghost noises?
Imti: No, not ghost noises. Fan noises. Probably.
Speaker 2: Probably?
Imti: Look, I'll check it later. Right now I need coffee.
Speaker 1: Coffee! Great idea! Let's all get coffee!
Speaker 2: We're literally in the middle of recording.
Speaker 1: Oh. Right. Hehe. Hehe.""",
        
        # Simba + Meow + Zulfi
        f"""Speaker 1: So anyway, about the {topic.lower()}...
Speaker 2: Wait, Zulfi's coming.
Zulfi: Good morning everyone. I hope you're all having a productive day.
Speaker 1: Hey Zulfi! What's up?
Zulfi: I need to discuss the new office policy regarding {topic.lower()}.
Speaker 2: There's a policy for that?
Zulfi: There's a policy for everything, Meow. Page 47, section 3, paragraph 2.
Speaker 1: You memorized the policy manual?
Zulfi: Of course. It's my job. Now, as I was saying...
Speaker 2: Can we just skip to the part where we ignore it?
Zulfi: That's... not how policies work.
Speaker 1: Yeah Meow, we have to follow the rules!
Speaker 2: You never follow rules.
Speaker 1: I follow Simba's rules. Which are different.
Zulfi: There are no "Simba's rules" in the employee handbook.
Speaker 1: There should be! Rule number one: Simba is always right.
Zulfi: That's... actually concerning.
Speaker 2: Welcome to my world.
Speaker 1: Okay okay, fine. What's the actual policy, Zulfi?
Zulfi: Well, according to section 3, paragraph 2...
Speaker 1: Oh wait, I forgot something. Be right back.
Zulfi: ...He's gone. He always does this.
Speaker 2: I know.""",
        
        # Meow + Imti + Zulfi (no Simba)
        f"""Speaker 2: Finally, some peace and quiet.
Imti: Hey Meow, where's Simba?
Speaker 2: Hopefully far away. He was driving me crazy.
Zulfi: Has anyone seen Simba? I need his expense report.
Speaker 2: He said something about the printer and disappeared.
Imti: The printer? I just fixed that yesterday.
Speaker 2: Exactly.
Zulfi: Well, when you see him, tell him the report is due by 5 PM.
Imti: Yeah, good luck with that.
Speaker 2: So Imti, what's really wrong with the server?
Imti: Nothing's wrong... yet. But it's making noises.
Zulfi: What kind of noises?
Imti: Like... hum noises. And occasionally a click.
Speaker 2: That sounds bad.
Imti: It's fine. Probably. Maybe. I'll check it later.
Zulfi: Please check it before it crashes. I have important emails to send.
Speaker 2: More emails about policies nobody reads?
Zulfi: People read them! They just... choose not to follow them.
Imti: I read them. Then I ignore them. Different from not reading.
Speaker 2: That's... actually worse.
Imti: Hey, I'm IT. I fix things. I don't follow HR rules.
Zulfi: That's going in my report.
Imti: Which report? The one nobody reads?""",
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
# SOUND EFFECTS
# ============================================================

def get_sound_effect(text):
    """Detect if text needs a sound effect."""
    laugh_words = ["haha", "lol", "hehe", "lmao", "hahaha"]
    rimshot_words = ["ba dum tss", "rimshot", "drum roll"]
    whoosh_words = ["whoosh", "swoosh", "dramatic"]
    
    text_lower = text.lower()
    
    for word in laugh_words:
        if word in text_lower:
            return "laugh"
    
    for word in rimshot_words:
        if word in text_lower:
            return "rimshot"
    
    for word in whoosh_words:
        if word in text_lower:
            return "whoosh"
    
    # Add laugh after certain patterns
    if text_lower.endswith("haha") or text_lower.endswith("lol"):
        return "laugh"
    
    return None

def insert_sound_effects(audio_path, script_lines, output_dir):
    """Insert sound effects at appropriate points in the audio."""
    sfx_dir = ASSETS_DIR
    laugh_path = os.path.join(sfx_dir, "laugh.mp3")
    rimshot_path = os.path.join(sfx_dir, "rimshot.mp3")
    whoosh_path = os.path.join(sfx_dir, "whoosh.mp3")
    
    if not all(os.path.exists(p) for p in [laugh_path, rimshot_path, whoosh_path]):
        print("  Sound effects not found, skipping")
        return audio_path
    
    # Get audio duration
    duration = get_audio_duration(audio_path)
    
    # Find lines that need sound effects with their approximate timestamps
    total_lines = len(script_lines)
    time_per_line = duration / max(total_lines, 1)
    
    sfx_events = []
    for i, (speaker, text) in enumerate(script_lines):
        sfx = get_sound_effect(text)
        if sfx:
            timestamp = i * time_per_line
            sfx_file = {"laugh": laugh_path, "rimshot": rimshot_path, "whoosh": whoosh_path}.get(sfx)
            if sfx_file:
                sfx_events.append((timestamp, sfx_file))
    
    if not sfx_events:
        return audio_path
    
    print(f"  Mixing {len(sfx_events)} sound effects...")
    
    # Build FFmpeg filter to mix SFX at specific timestamps
    filter_parts = []
    inputs = ["-i", audio_path]
    
    for idx, (ts, sfx_file) in enumerate(sfx_events):
        inputs.extend(["-i", sfx_file])
        filter_parts.append(f"[{idx + 1}]adelay={int(ts * 1000)}|{int(ts * 1000)},volume=0.6[sfx{idx}]")
    
    # Mix all SFX with original
    mix_inputs = "[0:a]"
    for idx in range(len(sfx_events)):
        mix_inputs += f"[sfx{idx}]"
    
    filter_parts.append(f"{mix_inputs}amix=inputs={len(sfx_events) + 1}:duration=first:dropout_transition=2[out]")
    
    output_audio = os.path.join(output_dir, "audio_with_sfx.mp3")
    cmd = [FFMPEG_EXE, '-y'] + inputs + [
        '-filter_complex', ';'.join(filter_parts),
        '-map', '[out]',
        '-c:a', 'libmp3lame', '-b:a', '192k',
        output_audio
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output_audio):
            print(f"  SFX mixed successfully")
            return output_audio
        else:
            print(f"  SFX mix failed, using original audio")
    except Exception as e:
        print(f"  SFX mix error: {e}")
    
    return audio_path

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

def get_speaker_color(speaker):
    """Get color for speaker label."""
    colors = {
        "Speaker 1": "#ff6b35",  # Orange - Simba
        "Speaker 2": "#4a9eff",  # Blue - Meow
        "Imti": "#00ff88",       # Green - IT
        "Zulfi": "#ff44ff",      # Pink - HR
    }
    return colors.get(speaker, "#ffffff")

def get_speaker_position(speaker, index, total):
    """Get position for speaker label (cycle through positions)."""
    positions = [
        (20, 640),    # Left
        (1160, 640),  # Right
        (20, 580),    # Left top
        (1160, 580),  # Right top
    ]
    return positions[index % len(positions)]

def generate_audio(script_path, output_dir):
    print("[1/5] Generating audio...")
    import edge_tts

    lines = parse_script(script_path)
    if not lines:
        print("  ERROR: No valid lines")
        return None

    segments_dir = os.path.join(output_dir, "segments")
    os.makedirs(segments_dir, exist_ok=True)

    # Generate segments in parallel batches for speed
    segment_files = []
    
    async def gen_segment(i, speaker, text, seg_path):
        voice = VOICES[speaker]
        rate = "+0%"
        if text.startswith("..."):
            rate = "-10%"
        elif "!" in text and len(text) < 20:
            rate = "+5%"
        elif speaker == "Imti":
            rate = "+3%"
        elif speaker == "Zulfi":
            rate = "-3%"
        
        c = edge_tts.Communicate(text, voice, rate=rate)
        await c.save(seg_path)
        return seg_path
    
    async def gen_all():
        tasks = []
        for i, (speaker, text) in enumerate(lines):
            seg_path = os.path.join(segments_dir, f"seg_{i:04d}.mp3")
            tasks.append(gen_segment(i, speaker, text, seg_path))
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    try:
        results = asyncio.run(gen_all())
        for i, r in enumerate(results):
            seg_path = os.path.join(segments_dir, f"seg_{i:04d}.mp3")
            if isinstance(r, Exception):
                print(f"  Warning: segment {i} failed: {r}")
            elif os.path.exists(seg_path):
                segment_files.append(seg_path)
    except Exception as e:
        print(f"  Async generation failed: {e}, falling back to sequential")
        for i, (speaker, text) in enumerate(lines):
            voice = VOICES[speaker]
            seg_path = os.path.join(segments_dir, f"seg_{i:04d}.mp3")
            rate = "+0%"
            if text.startswith("..."):
                rate = "-10%"
            elif "!" in text and len(text) < 20:
                rate = "+5%"
            elif speaker == "Imti":
                rate = "+3%"
            elif speaker == "Zulfi":
                rate = "-3%"
            try:
                async def gen():
                    c = edge_tts.Communicate(text, voice, rate=rate)
                    await c.save(seg_path)
                asyncio.run(gen())
                segment_files.append(seg_path)
            except Exception as e2:
                print(f"  Warning: segment {i} failed: {e2}")
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/{len(lines)} segments...")

    if not segment_files:
        return None

    print(f"  Generated {len(segment_files)} segments")

    # Build concat with small pauses between different speakers
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

    # Normalize
    normalized_audio = os.path.join(output_dir, "episode_audio.mp3")
    cmd = [FFMPEG_EXE, '-y', '-i', raw_audio,
           '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
           '-c:a', 'libmp3lame', '-b:a', '192k',
           normalized_audio]
    subprocess.run(cmd, capture_output=True, timeout=60)

    if os.path.exists(normalized_audio):
        print(f"  Audio ready")
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
    """Create a 4-second intro screen with characters."""
    intro_path = os.path.join(output_dir, "intro.mp4")

    # Create intro with animated text and character names
    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1280x720:d=4',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1',
        '-vf', (
            # Main title
            "drawtext=text='The Simba Show':fontcolor=white:fontsize=60:"
            "x=(w-text_w)/2:y=150,"
            # Episode number
            "drawtext=text='Episode %d':fontcolor=#ffaa00:fontsize=40:"
            "x=(w-text_w)/2:y=250," % episode_number,
            # Character names
            "drawtext=text='Simba':fontcolor=#ff6b35:fontsize=30:x=200:y=400,"
            "drawtext=text='Meow':fontcolor=#4a9eff:fontsize=30:x=400:y=400,"
            "drawtext=text='Imti':fontcolor=#00ff88:fontsize=30:x=600:y=400,"
            "drawtext=text='Zulfi':fontcolor=#ff44ff:fontsize=30:x=800:y=400,"
            # Tagline
            "drawtext=text='Office Gossip Podcast':fontcolor=#aaaaaa:fontsize=24:"
            "x=(w-text_w)/2:y=500"
        ),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-t', '4',
        intro_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except:
        pass

    return intro_path if os.path.exists(intro_path) else None

def create_outro_screen(output_dir, episode_number=None):
    """Create a 5-second outro screen with end screen elements."""
    outro_path = os.path.join(output_dir, "outro.mp4")

    # End screen with subscribe button and next episode teaser
    next_ep = (episode_number or 1) + 1
    
    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1280x720:d=5',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1',
        '-vf', (
            # Main title
            "drawtext=text='The Simba Show':fontcolor=#ffaa00:fontsize=60:"
            "x=(w-text_w)/2:y=100,"
            # Subscribe button area
            "drawbox=x=440:y=300:w=400:h=80:color=#ff0000:t=fill,"
            "drawtext=text='SUBSCRIBE':fontcolor=white:fontsize=40:"
            "x=(w-text_w)/2:y=315,"
            # Next episode teaser
            "drawtext=text='Next Episode Coming Tomorrow!':fontcolor=white:fontsize=30:"
            "x=(w-text_w)/2:y=450,"
            # Character names
            "drawtext=text='Simba | Meow | Imti | Zulfi':fontcolor=#aaaaaa:fontsize=24:"
            "x=(w-text_w)/2:y=520,"
            # Social handles
            "drawtext=text='@thesimbashowss':fontcolor=#888888:fontsize=20:"
            "x=(w-text_w)/2:y=600"
        ),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-t', '5',
        outro_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except:
        pass

    return outro_path if os.path.exists(outro_path) else None

def create_main_video(audio_path, bg_image, output_dir, episode_title, episode_number):
    """Create the main podcast video with speaker labels for all characters."""
    video_path = os.path.join(output_dir, "main_video.mp4")

    # Add speaker name labels at bottom - all 4 characters
    vf = (
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
        "drawbox=x=0:y=620:w=1280:h=100:color=black@0.6:t=fill,"
        # Simba - orange
        "drawbox=x=20:y=640:w=80:h=25:color=#ff6b35:t=fill,"
        "drawtext=text='Simba':fontcolor=white:fontsize=14:x=25:y=645,"
        # Meow - blue
        "drawbox=x=110:y=640:w=70:h=25:color=#4a9eff:t=fill,"
        "drawtext=text='Meow':fontcolor=white:fontsize=14:x=115:y=645,"
        # Imti - green
        "drawbox=x=200:y=640:w=60:h=25:color=#00ff88:t=fill,"
        "drawtext=text='Imti':fontcolor=white:fontsize=14:x=205:y=645,"
        # Zulfi - pink
        "drawbox=x=280:y=640:w=60:h=25:color=#ff44ff:t=fill,"
        "drawtext=text='Zulfi':fontcolor=white:fontsize=14:x=285:y=645"
    )

    cmd = [
        FFMPEG_EXE, '-y',
        '-loop', '1', '-i', bg_image,
        '-i', audio_path,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
        '-c:a', 'aac', '-b:a', '128k',
        '-pix_fmt', 'yuv420p',
        '-vf', vf,
        '-shortest',
        video_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"  FFmpeg error: {result.stderr[:200]}")
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
    print("[3/5] Creating video with all features...")

    backgrounds = get_all_backgrounds()
    if not backgrounds:
        print("  ERROR: No background images")
        return None

    bg = random.choice(backgrounds)
    duration = get_audio_duration(audio_path)
    print(f"  Background: {os.path.basename(bg)}")
    print(f"  Duration: {duration:.0f}s")

    # Step 1: Create main video with speaker labels
    main_video = create_main_video(audio_path, bg, output_dir, episode_title, episode_number)
    if not main_video:
        return None

    # Step 2: Add background music
    video_with_music = add_background_music(main_video, audio_path, output_dir)

    # Step 3: Create intro screen
    intro = create_intro_screen(output_dir, episode_title, episode_number)

    # Step 4: Create outro screen with end screen elements
    outro = create_outro_screen(output_dir, episode_number)

    # Step 5: Concatenate intro + main + outro
    final_path = os.path.join(output_dir, "final_video.mp4")
    concat_list = os.path.join(output_dir, "concat_list.txt")

    with open(concat_list, 'w') as f:
        if intro:
            f.write(f"file '{intro.replace(os.sep, '/')}'\n")
        f.write(f"file '{video_with_music.replace(os.sep, '/')}'\n")
        if outro:
            f.write(f"file '{outro.replace(os.sep, '/')}'\n")

    cmd = [FFMPEG_EXE, '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_list, '-c', 'copy', final_path]

    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except:
        pass

    if os.path.exists(final_path):
        print(f"  Video complete with intro/outro + music")
        return final_path

    return video_with_music

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

    # Create thumbnail with episode title overlay
    cmd = [
        FFMPEG_EXE, '-y',
        '-i', bg,
        '-vf', (
            # Episode number badge
            "drawbox=x=20:y=20:w=120:h=50:color=#ff0000:t=fill,"
            "drawtext=text='EP %d':fontcolor=white:fontsize=28:x=30:y=28," % episode_number,
            # Title at bottom
            "drawbox=x=0:y=520:w=720:h=80:color=black@0.7:t=fill,"
            "drawtext=text='%s':fontcolor=white:fontsize=24:x=10:y=545" % episode_title[:40]
        ),
        '-c:v', 'png',
        thumbnail
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except:
        # Fallback: just copy the image
        import shutil
        shutil.copy2(bg, thumbnail)

    if os.path.exists(thumbnail):
        print("  Thumbnail created")
        return thumbnail
    return None

# ============================================================
# YOUTUBE UPLOAD
# ============================================================

def upload_to_youtube(video_path, title, description, tags, thumbnail_path=None, episode_number=1):
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

    # Better SEO - description with timestamps and links
    full_description = f"""The Simba Show - Episode {episode_number}: {title}

{description}

---
About The Simba Show:
Four cats, Simba, Meow, Imti, and Zulfi, discuss office gossip in a hilarious podcast format.
New episodes daily!

Characters:
- Simba: Confident, works in Marketing, tells exaggerated stories
- Meow: Smart, sarcastic, works in Finance, keeps Simba in check
- Imti: IT guy, always fixing things, speaks geek
- Zulfi: HR manager, formal, sends too many emails

---
Subscribe: https://youtube.com/@thesimbashowss
---

#CatPodcast #SimbaAndMeow #FunnyCats #OfficeHumor #TheSimbaShow #CatComedy #Podcast #Shorts #OfficeLife #CatComedy"""

    body = {
        "snippet": {
            "title": f"The Simba Show Ep.{episode_number} - {title}" [:100],
            "description": full_description[:5000],
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

        # Upload thumbnail
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype="image/png")
                ).execute()
                print("  Thumbnail uploaded")
            except:
                pass

        # Add to playlist
        playlist_id = get_or_create_playlist(youtube, "The Simba Show - Full Episodes")
        if playlist_id:
            try:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id,
                            },
                        }
                    },
                ).execute()
                print("  Added to playlist")
            except:
                pass

        return {"video_id": video_id, "url": url}
    except Exception as e:
        print(f"  Failed: {e}")
        return None


def get_or_create_playlist(youtube, playlist_name):
    """Get existing playlist or create new one."""
    try:
        # Search for existing playlist
        request = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50
        )
        response = request.execute()

        for item in response.get("items", []):
            if item["snippet"]["title"] == playlist_name:
                return item["id"]

        # Create new playlist
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": playlist_name},
                "status": {"privacyStatus": "public"}
            }
        )
        response = request.execute()
        print(f"  Created playlist: {playlist_name}")
        return response["id"]

    except Exception as e:
        print(f"  Playlist error: {e}")
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

    # Short 1: Opening hook (first 25 seconds)
    short1_dir = os.path.join(shorts_dir, "short_1")
    os.makedirs(short1_dir, exist_ok=True)
    short1_audio = os.path.join(short1_dir, "short1_audio.mp3")

    clip_duration = min(25, duration)
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

    # Short 2: Best moment (middle section, 25 seconds)
    short2_dir = os.path.join(shorts_dir, "short_2")
    os.makedirs(short2_dir, exist_ok=True)
    short2_audio = os.path.join(short2_dir, "short2_audio.mp3")

    # Start from middle of episode
    start_time = max(0, (duration / 2) - 10)
    clip_duration = min(25, duration - start_time)

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
    print("CAT PODCAST - EPISODE GENERATOR v4")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    script_path, topic = get_next_script(specific_number)
    if not script_path:
        print("ERROR: No scripts found!")
        return None

    basename = os.path.basename(script_path)

    # Use topic if provided, otherwise extract from filename
    if topic:
        episode_title = topic
    else:
        episode_title = basename.replace(".txt", "").replace("_", " ").title()

    # Persistent episode number
    ep_count = get_next_episode_number()

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

    # Step 1.5: Insert sound effects
    script_lines = parse_script(script_path)
    audio_path = insert_sound_effects(audio_path, script_lines, output_dir)

    # Step 2: Subtitles
    subtitle_path = generate_subtitles(script_path, audio_path, output_dir)

    # Step 3: Video
    video_path = create_video(audio_path, subtitle_path, output_dir, episode_title, ep_count)
    if not video_path:
        print("\nFAILED: Video")
        return None

    # Step 4: Thumbnail
    thumbnail_path = create_thumbnail(output_dir, episode_title, ep_count)

    # Step 5: Generate 2 Shorts
    backgrounds = get_all_backgrounds()
    bg_image = random.choice(backgrounds) if backgrounds else None
    short_results = []
    if bg_image:
        short_results = generate_shorts(audio_path, script_path, output_dir, episode_title, ep_count, bg_image)

    # Step 6: Upload full episode
    description = f"""Simba and Meow discuss office gossip in this hilarious cat podcast!"""

    tags = [
        "cat podcast", "funny cats", "office cats", "cat comedy",
        "simba and meow", "cat dialogue", "funny cat videos",
        "cat humor", "office humor", "the simba show", "office gossip",
        "cat talk", "podcast", "daily podcast", "funny animals",
        "cat entertainment", "workplace comedy", "cat show"
    ]

    upload_result = upload_to_youtube(
        video_path, 
        episode_title, 
        description, 
        tags, 
        thumbnail_path,
        episode_number=ep_count
    )

    # Track which speakers were used
    speakers_used = list(set([s for s, _ in script_lines]))

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
        "speakers": speakers_used,
        "timestamp": timestamp,
    }

    with open(os.path.join(output_dir, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)

    mark_processed(script_path, metadata)

    print("\n" + "=" * 60)
    print("DONE!")
    print(f"  Episode #{ep_count}")
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
