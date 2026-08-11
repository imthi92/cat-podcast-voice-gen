#!/usr/bin/env python3
"""
Cat Podcast - Episode Generator v5 (Multi-Tier Fallback System)
Every component has fallback chains ranked by quality.
If method 1 fails -> method 2 -> method 3 -> etc.
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
import time
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
MEMORY_FILE = os.path.join(BASE_DIR, "character_memory.json")
IMAGES_DIR = os.path.join(BASE_DIR, "downloaded_images")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

VOICES = {
    "Speaker 1": "en-US-GuyNeural",
    "Speaker 2": "en-US-JennyNeural",
    "Imti": "en-US-ChristopherNeural",
    "Zulfi": "en-US-ChristopherNeural",
}

CHARACTERS = {
    "Speaker 1": "Simba (Marketing, confident, silly, exaggerates stories)",
    "Speaker 2": "Meow (Finance, smart, sarcastic, dry wit)",
    "Imti": "Imti (IT guy, technical, always fixing things, stressed)",
    "Zulfi": "Zulfi (HR manager, formal, corporate speak, manages people)",
}

# Natural speech: fillers, slang, and catchphrases per character
FILLERS = ["hmm", "oh", "um", "uh", "wait", "right?", "you know?", "like", "okay so", "honestly", "i mean"]
INTERJECTIONS = ["oh my god", "no way", "seriously?", "what?!", "exactly!", "big yikes", "oof", "yikes", "bro"]
SLANG = ["lowkey", "no cap", "fr", "dead", "that's wild", "bet", "sus", "vibes", "lit", "snack", "stan", "rent free"]

CATCHPHRASES = {
    "Speaker 1": ["Trust me, I've seen this before.", "Watch this.", "Listen, I'm a genius."],
    "Speaker 2": ["Anyway.", "Moving on.", "That's concerning.", "Noted.", "Cool story, bro."],
    "Imti": ["Have you tried turning it off and on again?", "That's a server issue.", "It's always DNS."],
    "Zulfi": ["Per the employee handbook...", "Let's circle back.", "This needs a policy.", "That's a compliance issue."],
}

# Sound effects available (auto-synthesized if missing)
SFX_TYPES = {
    "laugh": "laugh.mp3",
    "giggle": "giggle.mp3",
    "snort": "snort.mp3",
    "gasp": "gasp.mp3",
    "sigh": "sigh.mp3",
    "whoosh": "whoosh.mp3",
    "rimshot": "rimshot.mp3",
    "applause": "applause.mp3",
    "drumroll": "drumroll.mp3",
}

# FFmpeg auto-detect
def _find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe
    common_paths = [
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        os.path.expanduser(r"~\scoop\shims"),
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

def _find_fontfile():
    """Locate a usable font file for drawtext (Windows + Linux)."""
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

FONTFILE = _find_fontfile()

def _ensure_font_in(output_dir):
    """Copy the font into output_dir and return relative filename.
    ffmpeg can't handle Windows drive-letter colons in fontfile paths,
    so we copy the font next to the output and reference it relatively."""
    if not FONTFILE:
        return None
    try:
        os.makedirs(output_dir, exist_ok=True)
        dest = os.path.join(output_dir, "arial.ttf")
        if not os.path.exists(dest):
            shutil.copy2(FONTFILE, dest)
        return "arial.ttf"
    except Exception:
        return None

def _font_arg():
    """Return the fontfile arg for drawtext. Must be used with cwd=output_dir."""
    return ":fontfile=arial.ttf" if FONTFILE else ""

# ============================================================
# RETRY HELPER
# ============================================================

def retry(func, max_attempts=3, delay=2, backoff=2, description="operation"):
    """Retry with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            result = func()
            return result
        except Exception as e:
            wait = delay * (backoff ** attempt)
            if attempt < max_attempts - 1:
                print(f"  [{description}] Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [{description}] All {max_attempts} attempts failed: {e}")
                return None

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
# AI SCRIPT GENERATION - FALLBACK CHAIN
# Rank 1: Hugging Face (Mistral-7B) - Best free quality
# Rank 2: Google Gemini (free tier) - Good quality
# Rank 3: Template scripts - Always works
# ============================================================

OFFICE_TOPICS = [
    "The printer jam conspiracy theory", "Who stole my lunch from the fridge",
    "The meeting that should have been an email", "The WiFi password changed again",
    "The air conditioning war between departments", "The mysterious sticky notes on the desk",
    "The new intern's first day disaster", "The coffee machine is broken again",
    "The elevator is haunted", "The manager's motivational speech gone wrong",
    "The office birthday party disaster", "The IT department's secret files",
    "The parking lot drama", "The vending machine ate my money",
    "The fire drill during lunch hour", "The mysterious email from the CEO",
    "The office plant is dying", "The broken chair in the conference room",
    "The Monday morning mood", "The Friday afternoon rush",
    "The lunch break debate", "The remote work vs office war",
    "The team building exercise disaster", "The performance review panic",
    "The office snack monopoly", "The window seat battle",
    "The headphone cord conspiracy", "The printer ink cartridge mystery",
    "The thermostat wars", "The office gossip network",
    "The calendar invite chaos", "The dress code confusion",
    "The parking spot theft", "The lunch table politics",
    "The meeting room booking system", "The office supply shortage",
    "The mysterious USB drive", "The broken elevator saga",
    "The coffee stain detective", "The office music debate",
    "Imti's computer crashes during demo", "Zulfi's mandatory HR training session",
    "The internet is down - blame Imti", "Zulfi sends another all-staff email",
    "Imti's server room is overheating", "Zulfi's performance review nightmare",
    "Imti forgot to back up the data", "Zulfi's new office policy nobody follows",
    "Imti's cable management disaster", "Zulfi's team building exercise fails",
    "Imti's lunch stolen from IT fridge", "Zulfi's dress code enforcement chaos",
    "Imti's backup tapes are missing", "Zulfi's mandatory fun Friday",
    "Imti's emergency patch at 3 AM", "Zulfi's employee satisfaction survey",
]

def load_character_memory():
    """Load persistent character memory (traits, jokes, relationships)."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "episodes_done": 0,
        "running_jokes": [],
        "past_topics": [],
        "relationships": {
            "Simba_Meow": "Friendly rivals, Meow always corrects Simba's stories",
            "Simba_Imti": "Simba keeps breaking things, Imti keeps fixing them",
            "Imti_Zulfi": "Imti ignores Zulfi's policies, Zulfi sends complaints",
            "Meow_Zulfi": "Meow finds Zulfi exhausting but polite",
        },
    }

def save_character_memory(memory):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memory, f, indent=2)

def update_character_memory(topic, speakers):
    """Record episode info for continuity across episodes."""
    memory = load_character_memory()
    memory["episodes_done"] = memory.get("episodes_done", 0) + 1
    memory.setdefault("past_topics", []).append(topic)
    memory["past_topics"] = memory["past_topics"][-10:]  # keep last 10

    # Occasionally build a running joke from the topic
    if memory.get("episodes_done", 0) % 3 == 0 and len(memory.get("running_jokes", [])) < 5:
        joke = f"The cats still bring up: '{topic}' from a few episodes ago"
        memory.setdefault("running_jokes", []).append(joke)

    save_character_memory(memory)

def _get_memory_context():
    """Build a text block of character history for the AI prompt."""
    memory = load_character_memory()
    parts = []
    if memory.get("running_jokes"):
        parts.append("Running jokes from past episodes (reference ONE casually if natural):")
        for joke in memory["running_jokes"][-3:]:
            parts.append(f"- {joke}")
    if memory.get("relationships"):
        parts.append("Character relationships:")
        for key, rel in memory["relationships"].items():
            parts.append(f"- {key.replace('_', ' & ')}: {rel}")
    return "\n".join(parts)

def _get_script_prompt(topic):
    """Enhanced prompt with few-shot examples, slang, and character memory."""
    memory_context = _get_memory_context()
    return f"""Write a natural, funny cat podcast conversation about: {topic}

STYLE - This is a GOOD example of how the dialogue should sound (mimic this energy):
Speaker 1: Okay okay, so you're never gonna believe what happened.
Speaker 2: I always don't believe what you're about to say. That's my whole thing.
Speaker 1: No, this time it's real. Like, actually real. Hehe.
Speaker 2: You said that about the mouse that was just a leaf.
Speaker 1: ...it looked like a mouse from behind, okay?! Big yikes, moving on.
Imti: Are we talking about the thing with the printer again?
Speaker 1: Imti!! Perfect timing, bro. You're IT, you gotta hear this.
Imti: I literally just fixed that printer yesterday. It's always DNS.
Speaker 2: It's never DNS.
Imti: ...it's DNS.

Characters:
- Simba (Speaker 1): Confident, silly, works in Marketing, exaggerates stories, says "trust me bro"
- Meow (Speaker 2): Smart, sarcastic, dry wit, says "anyway" and "that's concerning", keeps Simba honest
- Imti: IT guy, stressed about servers, says "have you tried turning it off and on again"
- Zulfi: HR manager, formal, says "per the employee handbook", sends too many emails

USE THESE NATURAL SPEECH TOOLS (mix them in, don't overdo):
- Fillers: "hmm", "oh", "um", "uh", "wait", "right?", "you know?", "like"
- Reactions: "haha", "oh my god", "no way", "seriously?", "big yikes", "oof"
- Slang (light sprinkle): "lowkey", "no cap", "fr", "sus", "vibes", "bro"
- Interruptions: someone cuts off another mid-sentence
- Short punchy lines: "No.", "Yes.", "What?!", "Exactly!", "Nope."
- Laughter: "haha", "lol", "hehe", "pfft"
- Pauses: "..." or "--"

STRUCTURE (emotional arc):
1. OPENING HOOK (2-4 lines): someone reveals juicy gossip about the topic
2. BUILD (10-15 lines): they argue about details, someone exaggerates, someone corrects
3. CLIMAX (5-10 lines): the big reveal or dumbest decision made
4. WRAP (3-5 lines): a laugh together, a zinger, and a quick "next time on the show"

RULES:
- 2-3 characters per episode (rotate who appears)
- 35-50 lines total
- Use format EXACTLY: "Speaker 1:", "Speaker 2:", "Imti:", or "Zulfi:"
- NO stage directions in brackets
- NO "narrator" lines
- End on a funny beat, not a summary
- Sound like real friends chatting in an office, not a script

{memory_context}

Conversation:"""


def _parse_ai_script(raw_text):
    """Extract valid dialogue lines from raw AI output."""
    valid_speakers = ["Speaker 1", "Speaker 2", "Imti", "Zulfi"]
    lines = []
    for l in raw_text.split("\n"):
        l = l.strip()
        if not l or ":" not in l:
            continue
        speaker = l.split(":", 1)[0].strip()
        # Strip markdown/emphasis characters for matching ("**Imti**" -> "Imti")
        bare = speaker.strip().strip('*_`').strip()
        if bare not in valid_speakers:
            continue
        text = l.split(":", 1)[1].strip()
        if not text:
            continue
        lines.append(f"{bare}: {text}")
    return lines

def _pick_unique_topic():
    topic = random.choice(OFFICE_TOPICS)
    data = load_processed()
    recent_topics = [ep.get("metadata", {}).get("topic", "") for ep in data.get("episodes", [])[-5:]]
    for _ in range(10):
        if topic not in recent_topics:
            break
        topic = random.choice(OFFICE_TOPICS)
    return topic

def _save_script(lines, topic):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = os.path.join(SCRIPTS_DIR, f"episode_ai_{timestamp}.txt")
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    return script_path, topic

# --- RANK 1: Hugging Face Inference API ---
def _generate_hf():
    """Rank 1: Hugging Face free inference API."""
    import requests
    api_key = os.environ.get("HF_API_KEY", os.environ.get("HUGGINGFACE_API_KEY", ""))
    if not api_key:
        raise Exception("No HF_API_KEY set")

    topic = _pick_unique_topic()
    print(f"  [HF] Generating script about: {topic}")
    prompt = _get_script_prompt(topic)

    # Try several free models in order; keep the first that returns a usable script
    models = [
        "mistralai/Mistral-7B-Instruct-v0.3",
        "HuggingFaceH4/zephyr-7b-beta",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "google/gemma-2-2b-it",
        "microsoft/phi-3-mini-4k-instruct",
    ]
    last_err = None
    for model in models:
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"inputs": prompt, "parameters": {"max_new_tokens": 1500, "temperature": 0.95, "do_sample": True}},
                timeout=120
            )
            if response.status_code != 200:
                last_err = f"HF API error {response.status_code}: {response.text[:200]}"
                print(f"  [HF] {model}: {last_err}")
                continue

            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                script = result[0].get("generated_text", "")
            else:
                script = str(result)

            lines = _parse_ai_script(script)
            if len(lines) < 10:
                last_err = f"Script too short ({len(lines)} lines)"
                print(f"  [HF] {model}: {last_err}")
                continue

            print(f"  [HF] {model}: {len(lines)} lines")
            return _save_script(lines, topic)
        except Exception as e:
            last_err = str(e)
            print(f"  [HF] {model}: {last_err}")

    raise Exception(last_err or "All HF models failed")

# --- RANK 2: Google Gemini API (free tier) ---
def _generate_gemini():
    """Rank 2: Google Gemini free API."""
    import requests
    api_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
    if not api_key:
        raise Exception("No GEMINI_API_KEY set")

    topic = _pick_unique_topic()
    print(f"  [Gemini] Generating script about: {topic}")
    prompt = _get_script_prompt(topic) + "\n\nWrite ONLY the dialogue, no extra text."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    response = requests.post(url, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.95, "maxOutputTokens": 1500}
    }, timeout=60)

    if response.status_code != 200:
        raise Exception(f"Gemini API error {response.status_code}: {response.text[:200]}")

    data = response.json()
    script = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

    lines = _parse_ai_script(script)
    if len(lines) < 10:
        raise Exception(f"Script too short ({len(lines)} lines)")

    print(f"  [Gemini] Generated {len(lines)} lines")
    return _save_script(lines, topic)

# --- RANK 3: Template fallback (always works) ---
def _generate_template():
    """Rank 3: Template scripts - never fails."""
    topic = _pick_unique_topic()
    templates = [
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
        f"""Speaker 2: Okay, real talk. Who here has actually seen the {topic.lower()}?
Speaker 1: Oh! Oh! I have a story. I have SUCH a story.
Speaker 2: It's been 4 seconds and you're already exhausting me.
Speaker 1: No cap, this is the wildest thing that's happened all month.
Imti: If this is about the mouse again—
Speaker 1: IT WAS A LEAF, AND WE MOVED ON.
Speaker 2: Anyway. Please continue, Simba.
Speaker 1: So I'm walking to the kitchen, right? Lowkey vibes, just getting a snack.
Speaker 2: And?
Speaker 1: And I hear the weirdest noise. Like... buh-dup. Buh-dup.
Imti: That's the printer. It does that when it's dying. It's fine. Probably.
Speaker 1: It's not fine, Imti! The paper came out and it had like... a face on it?!
Speaker 2: A face? Like an actual face?
Speaker 1: Like, a potato face. Blobby. Deeply cursed.
Speaker 2: So you're telling me the printer is haunted.
Speaker 1: I'm telling you it's haunted, bro. Big yikes energy.
Imti: I can literally hear the ghost. It's the toner drum. It needs replacing.
Speaker 1: OR. And hear me out. We name it. Gary.
Speaker 2: We're not naming the haunted printer Gary.
Speaker 1: Too late. I already put a sticky note on it that says Gary.
Imti: Oh my god. You know what, sure. Gary's fine. He can keep making the noise.
Speaker 2: This is how we end up on a company-wide email.
Speaker 1: Zulfi's gonna send a policy about haunted printer etiquette.
Speaker 2: He already has one. Page 63. It says "per the employee handbook, paranormal activity should be reported to HR."
Speaker 1: Wait, seriously?!
Speaker 2: No. But I'm gonna add it now. That's content.""",
    ]
    script = random.choice(templates)
    print(f"  [Template] Generated about: {topic}")
    return _save_script(script.split("\n"), topic)


def generate_script_with_ai():
    """Generate script using fallback chain: HF -> Gemini -> Template."""
    print("[0/5] Generating script...")

    # Rank 1: Hugging Face
    try:
        result = _generate_hf()
        if result:
            print("  [OK] Script from Hugging Face")
            return result
    except Exception as e:
        print(f"  [SKIP] HF failed: {e}")

    # Rank 2: Gemini
    try:
        result = _generate_gemini()
        if result:
            print("  [OK] Script from Gemini")
            return result
    except Exception as e:
        print(f"  [SKIP] Gemini failed: {e}")

    # Rank 3: Template (always works)
    print("  [OK] Using template (all APIs unavailable)")
    return _generate_template()


# ============================================================
# SCRIPT SELECTION
# ============================================================

def get_next_script(specific_number=None):
    scripts = sorted(glob.glob(os.path.join(SCRIPTS_DIR, "episode_*.txt")))
    if specific_number:
        for s in scripts:
            if f"episode_{specific_number:02d}" in os.path.basename(s):
                return s, None
        return None, None
    for script in scripts:
        if not is_processed(script):
            topic = _derive_topic_from_script(script)
            return script, topic
    print("  All existing scripts used, generating new content...")
    return generate_script_with_ai()


def _derive_topic_from_script(script_path):
    """Derive a readable topic/title from a script file.
    AI scripts are named episode_ai_<timestamp>.txt with no topic in the name,
    so we try to extract the subject from the first dialogue line."""
    basename = os.path.basename(script_path)
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            first = f.readline().strip()
        if first and ":" in first:
            text = first.split(":", 1)[1].strip().strip('?!.," ')
            text = text.replace(",", "")
            # Clean up common leading phrases to make a decent title
            for prefix in ["oh my god did you hear about", "did you hear about",
                           "so anyway about the", "so basically", "okay so",
                           "oh my god did you hear"]:
                if text.lower().startswith(prefix):
                    text = text[len(prefix):].strip('?!.," ')
                    break
            # drop leading articles for readability
            for art in ["the ", "a ", "an "]:
                if text.lower().startswith(art) and len(text) > 6:
                    text = text[len(art):]
                    break
            if text:
                return text[:60].capitalize()
    except Exception:
        pass
    return basename.replace(".txt", "").replace("_", " ").title()

# ============================================================
# SOUND EFFECTS
# ============================================================

def get_sound_effect(text):
    """Detect natural sounds in dialogue."""
    if not text:
        return None
    t = text.lower()
    
    # Laughter variations
    if any(w in t for w in ["hahaha", "haha", "lol", "lmao", "rofl"]):
        return "laugh"
    if any(w in t for w in ["hehe", "hee hee", "giggle"]):
        return "giggle"
    if any(w in t for w in ["pfft", "snort", "snicker"]):
        return "snort"
    
    # Gasps / surprise
    if any(w in t for w in ["gasp", "*gasp*", "oh my god", "oh my gosh", "no way!", "what?!", "whoa"]):
        return "gasp"
    
    # Sighs / frustration
    if any(w in t for w in ["sigh", "ugh", "ughh", "*sigh*", "pff"]):
        return "sigh"
    
    # Whoosh / dramatic
    if any(w in t for w in ["whoosh", "swoosh", "dramatic"]):
        return "whoosh"
    
    # Rimshot / jokes
    if any(w in t for w in ["ba dum tss", "rimshot", "drum roll", "drumroll"]):
        return "rimshot"
    
    # Applause
    if any(w in t for w in ["applause", "clap", "*claps*", "round of applause"]):
        return "applause"
    
    return None

def _synthesize_sfx(name, output_path):
    """Synthesize a sound effect with FFmpeg if the file doesn't exist."""
    try:
        if name == "laugh" or name == "giggle":
            # Laugh-like: rapid rising tone blips
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi',
                   '-i', 'sine=frequency=700:duration=0.5',
                   '-af', 'aecho=0.8:0.7:60|120:0.4|0.3,volume=0.8',
                   '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "snort":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi',
                   '-i', 'anoisesrc=d=0.3:c=pink:r=44100:a=0.5',
                   '-af', 'lowpass=f=800,volume=0.7',
                   '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "gasp":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi',
                   '-i', 'anoisesrc=d=0.15:c=white:r=44100:a=0.4',
                   '-af', 'highpass=f=1500,lowpass=f=4000,volume=1.5',
                   '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "sigh":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi',
                   '-i', 'sine=frequency=400:duration=0.8',
                   '-af', 'afade=t=out:st=0.5:d=0.3,volume=0.4',
                   '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "applause":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi',
                   '-i', 'anoisesrc=d=1.5:c=pink:r=44100:a=0.3',
                   '-af', 'lowpass=f=3000,volume=1.2',
                   '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "drumroll":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi',
                   '-i', 'anoisesrc=d=1.2:c=white:r=44100:a=0.3',
                   '-af', 'lowpass=f=2000,volume=0.8',
                   '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        else:
            # Default whoosh/rimshot - noise sweep
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi',
                   '-i', 'anoisesrc=d=0.5:c=white:r=44100:a=0.5',
                   '-af', 'bandpass=f=2000:w=1000,volume=0.9',
                   '-c:a', 'libmp3lame', '-b:a', '128k', output_path]

        subprocess.run(cmd, capture_output=True, timeout=15)
        return os.path.exists(output_path)
    except Exception:
        return False

def ensure_sound_effects():
    """Make sure all SFX files exist (from repo or synthesized)."""
    os.makedirs(ASSETS_DIR, exist_ok=True)
    available = {}
    for name, filename in SFX_TYPES.items():
        path = os.path.join(ASSETS_DIR, filename)
        if not os.path.exists(path):
            if _synthesize_sfx(name, path):
                print(f"  [SFX] Synthesized: {filename}")
            else:
                print(f"  [SFX] Could not create: {filename}")
                continue
        available[name] = path
    return available

def insert_sound_effects(audio_path, script_lines, output_dir):
    sfx_paths = ensure_sound_effects()
    if not sfx_paths:
        print("  No sound effects available, skipping")
        return audio_path

    duration = get_audio_duration(audio_path)
    total_lines = len(script_lines)
    time_per_line = duration / max(total_lines, 1)
    sfx_events = []

    for i, (speaker, text) in enumerate(script_lines):
        sfx = get_sound_effect(text)
        if sfx and sfx in sfx_paths:
            timestamp = i * time_per_line
            sfx_events.append((timestamp, sfx_paths[sfx]))

    if not sfx_events:
        return audio_path

    print(f"  Mixing {len(sfx_events)} sound effects...")
    filter_parts = []
    inputs = ["-i", audio_path]
    for idx, (ts, sfx_file) in enumerate(sfx_events):
        inputs.extend(["-i", sfx_file])
        filter_parts.append(f"[{idx + 1}]adelay={int(ts * 1000)}|{int(ts * 1000)},volume=0.6[sfx{idx}]")

    mix_inputs = "[0:a]"
    for idx in range(len(sfx_events)):
        mix_inputs += f"[sfx{idx}]"
    filter_parts.append(f"{mix_inputs}amix=inputs={len(sfx_events) + 1}:duration=first:dropout_transition=2[out]")

    output_audio = os.path.join(output_dir, "audio_with_sfx.mp3")
    cmd = [FFMPEG_EXE, '-y'] + inputs + [
        '-filter_complex', ';'.join(filter_parts),
        '-map', '[out]', '-c:a', 'libmp3lame', '-b:a', '192k', output_audio
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output_audio):
            print(f"  SFX mixed successfully")
            return output_audio
    except Exception as e:
        print(f"  SFX mix error: {e}")
    return audio_path

# ============================================================
# TTS AUDIO GENERATION - FALLBACK CHAIN
# Rank 1: Edge TTS (Microsoft) - Best free quality
# Rank 2: gTTS (Google) - Decent quality
# Rank 3: pyttsx3 (offline) - Works without internet
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
    colors = {
        "Speaker 1": "#ff6b35",
        "Speaker 2": "#4a9eff",
        "Imti": "#00ff88",
        "Zulfi": "#ff44ff",
    }
    return colors.get(speaker, "#ffffff")

# --- RANK 1: Edge TTS (best quality) ---
def _tts_edge(segments_dir, lines):
    """Rank 1: Microsoft Edge TTS - best free quality."""
    import edge_tts
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

    async def gen_all():
        tasks = []
        for i, (speaker, text) in enumerate(lines):
            seg_path = os.path.join(segments_dir, f"seg_{i:04d}.mp3")
            tasks.append(gen_segment(i, speaker, text, seg_path))
        return await asyncio.gather(*tasks, return_exceptions=True)

    results = asyncio.run(gen_all())
    for i, r in enumerate(results):
        seg_path = os.path.join(segments_dir, f"seg_{i:04d}.mp3")
        if isinstance(r, Exception):
            print(f"  [Edge] segment {i} failed: {r}")
        elif os.path.exists(seg_path):
            segment_files.append(seg_path)
    return segment_files

# --- RANK 2: gTTS (decent quality) ---
def _tts_gtts(segments_dir, lines):
    """Rank 2: Google TTS - decent quality, free."""
    from gtts import gTTS
    segment_files = []

    gtts_voices = {
        "Speaker 1": "en",
        "Speaker 2": "en",
        "Imti": "en",
        "Zulfi": "en",
    }

    for i, (speaker, text) in enumerate(lines):
        seg_path = os.path.join(segments_dir, f"seg_{i:04d}.mp3")
        try:
            lang = gtts_voices.get(speaker, "en")
            tts = gTTS(text=text, lang=lang)
            tts.save(seg_path)
            if os.path.exists(seg_path):
                segment_files.append(seg_path)
        except Exception as e:
            print(f"  [gTTS] segment {i} failed: {e}")
    return segment_files

# --- RANK 3: pyttsx3 (offline fallback) ---
def _tts_pyttsx3(segments_dir, lines):
    """Rank 3: pyttsx3 offline TTS - always works, no internet needed."""
    import pyttsx3
    engine = pyttsx3.init()
    segment_files = []

    for i, (speaker, text) in enumerate(lines):
        seg_path = os.path.join(segments_dir, f"seg_{i:04d}.wav")
        try:
            engine.save_to_file(text, seg_path)
            engine.runAndWait()
            # Convert wav to mp3
            mp3_path = os.path.join(segments_dir, f"seg_{i:04d}.mp3")
            cmd = [FFMPEG_EXE, '-y', '-i', seg_path, '-c:a', 'libmp3lame', '-b:a', '128k', mp3_path]
            subprocess.run(cmd, capture_output=True, timeout=30)
            if os.path.exists(mp3_path):
                segment_files.append(mp3_path)
                os.remove(seg_path)
        except Exception as e:
            print(f"  [pyttsx3] segment {i} failed: {e}")
    return segment_files


def generate_audio(script_path, output_dir):
    print("[1/5] Generating audio...")
    lines = parse_script(script_path)
    if not lines:
        print("  ERROR: No valid lines")
        return None

    segments_dir = os.path.join(output_dir, "segments")
    os.makedirs(segments_dir, exist_ok=True)

    # --- FALLBACK CHAIN: Edge TTS -> gTTS -> pyttsx3 ---
    segment_files = []

    # Rank 1: Edge TTS
    try:
        print("  [Edge TTS] Generating segments...")
        segment_files = _tts_edge(segments_dir, lines)
        if segment_files:
            print(f"  [OK] Edge TTS: {len(segment_files)} segments")
        else:
            raise Exception("No segments generated")
    except Exception as e:
        print(f"  [SKIP] Edge TTS failed: {e}")

    # Rank 2: gTTS
    if not segment_files:
        try:
            print("  [gTTS] Generating segments...")
            segment_files = _tts_gtts(segments_dir, lines)
            if segment_files:
                print(f"  [OK] gTTS: {len(segment_files)} segments")
            else:
                raise Exception("No segments generated")
        except Exception as e:
            print(f"  [SKIP] gTTS failed: {e}")

    # Rank 3: pyttsx3 (offline)
    if not segment_files:
        try:
            print("  [pyttsx3] Generating segments (offline)...")
            segment_files = _tts_pyttsx3(segments_dir, lines)
            if segment_files:
                print(f"  [OK] pyttsx3: {len(segment_files)} segments")
            else:
                raise Exception("No segments generated")
        except Exception as e:
            print(f"  [FATAL] All TTS methods failed: {e}")
            return None

    # Concatenate all segments
    concat_file = os.path.join(segments_dir, "concat.txt")
    with open(concat_file, 'w') as f:
        for seg in segment_files:
            f.write(f"file '{os.path.abspath(seg).replace(os.sep, '/')}'\n")

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
           '-c:a', 'libmp3lame', '-b:a', '192k', normalized_audio]
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
# VIDEO CREATION
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
    images = []
    if os.path.exists(IMAGES_DIR):
        for f in os.listdir(IMAGES_DIR):
            if f.endswith('.jpg') and not f.startswith('episode'):
                images.append(os.path.join(IMAGES_DIR, f))
    return images

# --- IMAGE FALLBACK CHAIN ---
# Rank 1: AI generate via Pollinations.ai (free, no API key)
# Rank 2: Download from Unsplash (free, no API key)
# Rank 3: Use existing downloaded images

def _get_background_fallback(output_dir):
    """Get background image with fallback chain."""
    # Rank 1: Existing images
    existing = get_all_backgrounds()
    if existing:
        return random.choice(existing)

    # Rank 2: Download from a free image source
    try:
        import requests
        os.makedirs(IMAGES_DIR, exist_ok=True)
        # Pollinations.ai free image generation (no API key)
        url = f"https://image.pollinations.ai/prompt/cartoon%20cat%20podcast%20studio%20with%20microphones?width=1280&height=720&nologo=true"
        resp = requests.get(url, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            img_path = os.path.join(IMAGES_DIR, f"gen_{hashlib.md5(resp.content).hexdigest()[:8]}.jpg")
            with open(img_path, 'wb') as f:
                f.write(resp.content)
            if os.path.getsize(img_path) > 1000:
                print(f"  Generated background via Pollinations")
                return img_path
    except Exception as e:
        print(f"  [SKIP] Pollinations failed: {e}")

    # Rank 3: Download from Picsum (free, no API key)
    try:
        import requests
        url = "https://picsum.photos/1280/720"
        resp = requests.get(url, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            img_path = os.path.join(IMAGES_DIR, f"picsum_{hashlib.md5(resp.content).hexdigest()[:8]}.jpg")
            with open(img_path, 'wb') as f:
                f.write(resp.content)
            if os.path.getsize(img_path) > 1000:
                print(f"  Downloaded background from Picsum")
                return img_path
    except Exception as e:
        print(f"  [SKIP] Picsum failed: {e}")

    # Rank 3: Generate solid color background via FFmpeg
    try:
        img_path = os.path.join(output_dir, "generated_bg.jpg")
        cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi',
               '-i', 'color=c=#1a1a2e:s=1280x720:d=1',
               '-frames:v', '1', img_path]
        subprocess.run(cmd, capture_output=True, timeout=10)
        if os.path.exists(img_path):
            print(f"  Generated solid color background")
            return img_path
    except:
        pass

    return None

def create_intro_screen(output_dir, episode_title, episode_number):
    intro_path = os.path.abspath(os.path.join(output_dir, "intro.mp4"))
    _ensure_font_in(output_dir)
    fa = _font_arg()
    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1280x720:d=4',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1',
        '-vf', (
            f"drawtext=text='The Simba Show':fontcolor=white:fontsize=60{fa}:"
            "x=(w-text_w)/2:y=150,"
            f"drawtext=text='Episode {episode_number}':fontcolor=#ffaa00:fontsize=40{fa}:"
            "x=(w-text_w)/2:y=250,"
            f"drawtext=text='Simba':fontcolor=#ff6b35:fontsize=30{fa}:x=200:y=400,"
            f"drawtext=text='Meow':fontcolor=#4a9eff:fontsize=30{fa}:x=400:y=400,"
            f"drawtext=text='Imti':fontcolor=#00ff88:fontsize=30{fa}:x=600:y=400,"
            f"drawtext=text='Zulfi':fontcolor=#ff44ff:fontsize=30{fa}:x=800:y=400,"
            f"drawtext=text='Office Gossip Podcast':fontcolor=#aaaaaa:fontsize=24{fa}:"
            "x=(w-text_w)/2:y=500"
        ),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-t', '4', intro_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, cwd=output_dir)
    except:
        pass
    return intro_path if os.path.exists(intro_path) else None

def create_outro_screen(output_dir, episode_number=None):
    outro_path = os.path.abspath(os.path.join(output_dir, "outro.mp4"))
    next_ep = (episode_number or 1) + 1
    _ensure_font_in(output_dir)
    fa = _font_arg()
    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1280x720:d=5',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1',
        '-vf', (
            f"drawtext=text='The Simba Show':fontcolor=#ffaa00:fontsize=60{fa}:"
            "x=(w-text_w)/2:y=100,"
            "drawbox=x=440:y=300:w=400:h=80:color=#ff0000:t=fill,"
            f"drawtext=text='SUBSCRIBE':fontcolor=white:fontsize=40{fa}:"
            "x=(w-text_w)/2:y=315,"
            f"drawtext=text='Next Episode Coming Tomorrow!':fontcolor=white:fontsize=30{fa}:"
            "x=(w-text_w)/2:y=450,"
            f"drawtext=text='Simba | Meow | Imti | Zulfi':fontcolor=#aaaaaa:fontsize=24{fa}:"
            "x=(w-text_w)/2:y=520,"
            f"drawtext=text='@thesimbashowss':fontcolor=#888888:fontsize=20{fa}:"
            "x=(w-text_w)/2:y=600"
        ),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-t', '5', outro_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, cwd=output_dir)
    except:
        pass
    return outro_path if os.path.exists(outro_path) else None

def create_main_video(audio_path, bg_image, output_dir, episode_title, episode_number):
    video_path = os.path.abspath(os.path.join(output_dir, "main_video.mp4"))
    audio_path = os.path.abspath(audio_path)
    bg_image = os.path.abspath(bg_image)
    _ensure_font_in(output_dir)
    fa = _font_arg()
    vf = (
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
        "drawbox=x=0:y=620:w=1280:h=100:color=black@0.6:t=fill,"
        "drawbox=x=20:y=640:w=80:h=25:color=#ff6b35:t=fill,"
        f"drawtext=text='Simba':fontcolor=white:fontsize=14{fa}:x=25:y=645,"
        "drawbox=x=110:y=640:w=70:h=25:color=#4a9eff:t=fill,"
        f"drawtext=text='Meow':fontcolor=white:fontsize=14{fa}:x=115:y=645,"
        "drawbox=x=200:y=640:w=60:h=25:color=#00ff88:t=fill,"
        f"drawtext=text='Imti':fontcolor=white:fontsize=14{fa}:x=205:y=645,"
        "drawbox=x=280:y=640:w=60:h=25:color=#ff44ff:t=fill,"
        f"drawtext=text='Zulfi':fontcolor=white:fontsize=14{fa}:x=285:y=645"
    )
    cmd = [
        FFMPEG_EXE, '-y', '-loop', '1', '-i', bg_image, '-i', audio_path,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
        '-c:a', 'aac', '-b:a', '128k', '-pix_fmt', 'yuv420p',
        '-vf', vf, '-shortest', video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=output_dir)
        if result.returncode != 0:
            print(f"  FFmpeg error: {result.stderr[:300]}")
    except Exception as e:
        print(f"  FFmpeg failed: {e}")

    # Fallback: retry without text overlays (fonts may be missing on some systems)
    if not os.path.exists(video_path):
        print("  Retrying without text overlays...")
        vf_no_text = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720"
        cmd2 = [
            FFMPEG_EXE, '-y', '-loop', '1', '-i', bg_image, '-i', audio_path,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
            '-c:a', 'aac', '-b:a', '128k', '-pix_fmt', 'yuv420p',
            '-vf', vf_no_text, '-shortest', video_path
        ]
        try:
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=300, cwd=output_dir)
            if result2.returncode != 0:
                print(f"  FFmpeg fallback error: {result2.stderr[:200]}")
        except Exception as e:
            print(f"  FFmpeg fallback failed: {e}")

    return video_path if os.path.exists(video_path) else None

def add_background_music(video_path, audio_path, output_dir):
    music_file = os.path.join(ASSETS_DIR, "ambient_bg.mp3")
    final_path = os.path.join(output_dir, "final_with_music.mp4")
    if not os.path.exists(music_file):
        return video_path
    duration = get_audio_duration(audio_path)
    cmd = [
        FFMPEG_EXE, '-y', '-i', video_path,
        '-stream_loop', '-1', '-i', music_file,
        '-filter_complex',
        f'[1:a]volume=0.08,atrim=0:{duration},afade=t=in:d=3,afade=t=out:st={duration-3}:d=3[music];[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[out]',
        '-map', '0:v', '-map', '[out]',
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', final_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"  Music mix error: {result.stderr[:200]}")
    except:
        pass
    return final_path if os.path.exists(final_path) else video_path

def add_subtitles(video_path, subtitle_path, output_dir):
    final_path = os.path.join(output_dir, "final_video.mp4")
    if not subtitle_path or not os.path.exists(subtitle_path):
        return video_path
    srt_copy = os.path.join(output_dir, "subtitles.srt")
    if subtitle_path != srt_copy:
        shutil.copy2(subtitle_path, srt_copy)
    cmd = [
        FFMPEG_EXE, '-y', '-i', video_path,
        '-vf', f"subtitles=subtitles.srt:force_style='FontSize=20,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2,Shadow=1'",
        '-c:v', 'libx264', '-crf', '23', '-c:a', 'copy', final_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=output_dir)
        if result.returncode != 0:
            return video_path
    except:
        return video_path
    return final_path if os.path.exists(final_path) else video_path

def create_video(audio_path, subtitle_path, output_dir, episode_title, episode_number):
    print("[3/5] Creating video with all features...")

    bg = _get_background_fallback(output_dir)
    if not bg:
        print("  ERROR: No background images available")
        return None

    duration = get_audio_duration(audio_path)
    print(f"  Background: {os.path.basename(bg)}")
    print(f"  Duration: {duration:.0f}s")

    main_video = create_main_video(audio_path, bg, output_dir, episode_title, episode_number)
    if not main_video:
        return None

    video_with_music = add_background_music(main_video, audio_path, output_dir)
    intro = create_intro_screen(output_dir, episode_title, episode_number)
    outro = create_outro_screen(output_dir, episode_number)

    concat_path = os.path.join(output_dir, "concat_video.mp4")
    concat_list = os.path.join(output_dir, "concat_list.txt")
    with open(concat_list, 'w') as f:
        if intro:
            f.write(f"file '{os.path.abspath(intro).replace(os.sep, '/')}'\n")
        f.write(f"file '{os.path.abspath(video_with_music).replace(os.sep, '/')}'\n")
        if outro:
            f.write(f"file '{os.path.abspath(outro).replace(os.sep, '/')}'\n")

    cmd = [FFMPEG_EXE, '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_list, '-c', 'copy', concat_path]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except:
        pass

    if os.path.exists(concat_path):
        return add_subtitles(concat_path, subtitle_path, output_dir)
    return video_with_music

# ============================================================
# THUMBNAIL
# ============================================================

def create_thumbnail(output_dir, episode_title, episode_number):
    print("[4/5] Creating thumbnail...")
    thumbnail = os.path.abspath(os.path.join(output_dir, "thumbnail.png"))
    _ensure_font_in(output_dir)
    fa = _font_arg()

    backgrounds = get_all_backgrounds()
    if not backgrounds:
        # Generate a thumbnail from solid color
        cmd = [
            FFMPEG_EXE, '-y', '-f', 'lavfi',
            '-i', 'color=c=#1a1a2e:s=720x540:d=1',
            '-vf', (
                "drawbox=x=20:y=20:w=120:h=50:color=#ff0000:t=fill,"
                f"drawtext=text='EP {episode_number}':fontcolor=white:fontsize=28{fa}:x=30:y=28,"
                f"drawtext=text='The Simba Show':fontcolor=#ffaa00:fontsize=40{fa}:"
                "x=(w-text_w)/2:y=200"
            ),
            '-frames:v', '1', thumbnail
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=15, cwd=output_dir)
        except:
            pass
        return thumbnail if os.path.exists(thumbnail) else None

    bg = random.choice(backgrounds)
    title_file = os.path.join(output_dir, "thumb_title.txt")
    try:
        with open(title_file, 'w', encoding='utf-8') as f:
            f.write(episode_title[:40])
    except:
        pass
    cmd = [
        FFMPEG_EXE, '-y', '-i', bg,
        '-vf', (
            "drawbox=x=20:y=20:w=120:h=50:color=#ff0000:t=fill,"
            f"drawtext=text='EP {episode_number}':fontcolor=white:fontsize=28{fa}:x=30:y=28,"
            "drawbox=x=0:y=520:w=720:h=80:color=black@0.7:t=fill,"
            f"drawtext=textfile=thumb_title.txt:fontcolor=white:fontsize=24{fa}:x=10:y=545"
        ),
        '-c:v', 'png', thumbnail
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30, cwd=output_dir)
        if result.returncode != 0 and os.path.exists(bg):
            shutil.copy2(bg, thumbnail)
    except:
        shutil.copy2(bg, thumbnail)

    return thumbnail if os.path.exists(thumbnail) else None

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

        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype="image/png")
                ).execute()
                print("  Thumbnail uploaded")
            except:
                pass

        playlist_id = get_or_create_playlist(youtube, "The Simba Show - Full Episodes")
        if playlist_id:
            try:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {"kind": "youtube#video", "videoId": video_id},
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
    try:
        request = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
        response = request.execute()
        for item in response.get("items", []):
            if item["snippet"]["title"] == playlist_name:
                return item["id"]
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": playlist_name},
                "status": {"privacyStatus": "public"}
            }
        )
        response = request.execute()
        return response["id"]
    except Exception as e:
        print(f"  Playlist error: {e}")
        return None

# ============================================================
# YOUTUBE SHORTS GENERATION
# ============================================================

def get_audio_segment(audio_path, start_sec, duration_sec, output_path):
    cmd = [FFMPEG_EXE, '-y', '-i', audio_path,
           '-ss', str(start_sec), '-t', str(duration_sec), '-c:a', 'libmp3lame', '-b:a', '192k', output_path]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except:
        pass
    return os.path.exists(output_path)

def create_short_video(audio_path, bg_image, output_dir, title, subtitle_text):
    duration = get_audio_duration(audio_path)
    w, h = 1080, 1920
    total_frames = int(duration * 24)
    video_path = os.path.join(output_dir, "short_video.mp4")
    cmd = [
        FFMPEG_EXE, '-y', '-loop', '1', '-i', bg_image, '-i', audio_path,
        '-c:v', 'libx264', '-c:a', 'aac', '-b:a', '192k', '-pix_fmt', 'yuv420p',
        '-vf', f'scale=8000:-1,zoompan=z=\'min(zoom+0.001,1.3)\':x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':d={total_frames}:s={w}x{h}:fps=24',
        '-shortest', video_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except:
        pass
    return video_path if os.path.exists(video_path) else None

def upload_short(video_path, title, description, tags, thumbnail_path=None):
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
    print("\n[SHORTS] Generating 2 Shorts...")
    duration = get_audio_duration(audio_path)
    shorts_dir = os.path.join(output_dir, "shorts")
    os.makedirs(shorts_dir, exist_ok=True)

    with open(script_path, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines() if l.strip() and ":" in l]

    short_results = []

    # Short 1: Opening hook
    short1_dir = os.path.join(shorts_dir, "short_1")
    os.makedirs(short1_dir, exist_ok=True)
    short1_audio = os.path.join(short1_dir, "short1_audio.mp3")
    clip_duration = min(25, duration)
    if get_audio_segment(audio_path, 0, clip_duration, short1_audio):
        first_line = lines[0].split(":", 1)[1].strip() if lines else "The Simba Show"
        short1_video = create_short_video(short1_audio, bg_image, short1_dir, f"EP {episode_number:02d} - Hook", first_line)
        if short1_video:
            title = f"The Simba Show - {episode_title} (Short 1)"
            desc = f"Cat podcast short! Full episode in bio.\n\n#Shorts #CatPodcast #FunnyCats #SimbaAndMeow"
            tags = ["cat podcast", "funny cats", "Shorts", "simba and meow"]
            upload1 = upload_short(short1_video, title, desc, tags)
            short_results.append({"short": 1, "upload": upload1, "video": short1_video})
            print(f"  Short 1 done")

    # Short 2: Best moment
    short2_dir = os.path.join(shorts_dir, "short_2")
    os.makedirs(short2_dir, exist_ok=True)
    short2_audio = os.path.join(short2_dir, "short2_audio.mp3")
    start_time = max(0, (duration / 2) - 10)
    clip_duration = min(25, duration - start_time)
    if get_audio_segment(audio_path, start_time, clip_duration, short2_audio):
        mid_idx = len(lines) // 2
        mid_line = lines[mid_idx].split(":", 1)[1].strip() if mid_idx < len(lines) else "Office gossip"
        short2_video = create_short_video(short2_audio, bg_image, short2_dir, f"EP {episode_number:02d} - Best Moment", mid_line)
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
    print("CAT PODCAST - EPISODE GENERATOR v5")
    print("Fallback chains: HF->Gemini->Template | Edge->gTTS->pyttsx3")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    script_path, topic = get_next_script(specific_number)
    if not script_path:
        print("ERROR: No scripts found!")
        return None

    basename = os.path.basename(script_path)
    if topic:
        episode_title = topic
    else:
        episode_title = basename.replace(".txt", "").replace("_", " ").title()

    ep_count = get_next_episode_number()
    print(f"\nScript: {basename}")
    print(f"Title: {episode_title}")
    print(f"Episode #{ep_count}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(OUTPUT_DIR, f"episode_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    audio_path = generate_audio(script_path, output_dir)
    if not audio_path:
        print("\nFAILED: Audio - all TTS methods failed")
        return None

    script_lines = parse_script(script_path)
    audio_path = insert_sound_effects(audio_path, script_lines, output_dir)
    subtitle_path = generate_subtitles(script_path, audio_path, output_dir)

    video_path = create_video(audio_path, subtitle_path, output_dir, episode_title, ep_count)
    if not video_path:
        print("\nFAILED: Video")
        return None

    thumbnail_path = create_thumbnail(output_dir, episode_title, ep_count)

    backgrounds = get_all_backgrounds()
    bg_image = random.choice(backgrounds) if backgrounds else None
    short_results = []
    if bg_image:
        short_results = generate_shorts(audio_path, script_path, output_dir, episode_title, ep_count, bg_image)

    description = f"""Simba and Meow discuss office gossip in this hilarious cat podcast!"""
    tags = [
        "cat podcast", "funny cats", "office cats", "cat comedy",
        "simba and meow", "cat dialogue", "funny cat videos",
        "cat humor", "office humor", "the simba show", "office gossip",
        "cat talk", "podcast", "daily podcast", "funny animals",
        "cat entertainment", "workplace comedy", "cat show"
    ]

    upload_result = upload_to_youtube(video_path, episode_title, description, tags, thumbnail_path, episode_number=ep_count)

    speakers_used = list(set([s for s, _ in script_lines]))
    metadata = {
        "script": script_path, "title": episode_title, "topic": topic,
        "episode_number": ep_count, "audio": audio_path, "video": video_path,
        "thumbnail": thumbnail_path, "upload": upload_result, "shorts": short_results,
        "speakers": speakers_used, "timestamp": timestamp,
    }

    with open(os.path.join(output_dir, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)

    mark_processed(script_path, metadata)
    update_character_memory(topic or episode_title, speakers_used)

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
