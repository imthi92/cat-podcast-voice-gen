#!/usr/bin/env python3
"""
Cat Podcast - Episode Generator v5 (Multi-Tier Fallback System)
Every component has fallback chains ranked by quality.
If method 1 fails -> method 2 -> method 3 -> etc.
"""

import os
import sys
import json
import re
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

# Windows-safe stdout/stderr encoding (prevents UnicodeEncodeError on prints)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

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

# NATURAL_MODE: when enabled, TTS injects real pauses (from "..." / "--") and
# per-speaker prosody via SSML so the podcast sounds like a real conversation
# instead of someone reading a script. Disable with:  NATURAL_MODE=0 python ...
NATURAL_MODE = os.environ.get("NATURAL_MODE", "1") != "0"

# Per-speaker pitch tweak (SSML) to give each cat a distinct, lively voice.
_NATURAL_PITCH = {
    "Speaker 1": "+5%",   # Simba - upbeat, energetic
    "Speaker 2": "-2%",   # Meow  - dry, calm
    "Imti":      "+1%",   # Imti - slightly strained
    "Zulfi":     "-1%",   # Zulfi - formal, flat
}

def _build_ssml(speaker, text, rate):
    """Wrap spoken text in SSML with real pauses and per-speaker prosody."""
    voice = VOICES.get(speaker, "en-US-JennyNeural")
    pitch = _NATURAL_PITCH.get(speaker, "0%")
    t = text
    # Escape XML special characters to prevent SSML parse errors
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    # Convert written pauses into actual audible breaks
    t = t.replace("...", '<break time="600ms"/>')
    t = t.replace("--", '<break time="300ms"/>')
    # Small breath/pause after sentence-ending punctuation
    t = re.sub(r'([.!?])\s', r'\1<break time="200ms"/>', t)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="en-US"><voice name="{voice}">'
        f'<prosody rate="{rate}" pitch="{pitch}">{t}</prosody></voice></speak>'
    )

CHARACTERS = {
    "Speaker 1": "Simba (Hospital IT cat, confident, silly, exaggerates stories, orange tabby)",
    "Speaker 2": "Meow (Hospital accounts/finance cat, smart, sarcastic, dry wit)",
    "Imti": "Imti (Hospital IT cat, technical, always fixing the medical devices, stressed)",
    "Zulfi": "Zulfi (Hospital HR cat, formal, compliance speak, manages people)",
}

# Natural speech: fillers, slang, and catchphrases per character
FILLERS = ["hmm", "oh", "um", "uh", "wait", "right?", "you know?", "like", "okay so", "honestly", "i mean"]
INTERJECTIONS = ["oh my god", "no way", "seriously?", "what?!", "exactly!", "big yikes", "oof", "yikes", "bro"]
SLANG = ["lowkey", "no cap", "fr", "dead", "that's wild", "bet", "sus", "vibes", "lit", "snack", "stan", "rent free"]

CATCHPHRASES = {
    "Speaker 1": ["Trust me, I know this hospital's systems.", "Watch this.", "Listen, I'm an IT genius."],
    "Speaker 2": ["Anyway.", "Moving on.", "That's concerning.", "Noted.", "Cool story, bro."],
    "Imti": ["Did you try restarting the EMR system?", "That's a server issue.", "It's always DNS."],
    "Zulfi": ["Per the hospital compliance handbook...", "Let's circle back.", "This needs a policy.", "That's a HIPAA issue."],
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
    """Copy the font into output_dir and return relative filename."""
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
    return ":fontfile=arial.ttf" if FONTFILE else ""

# ============================================================
# RETRY HELPER
# ============================================================

def retry(func, max_attempts=3, delay=2, backoff=2, description="operation"):
    for attempt in range(max_attempts):
        try:
            return func()
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
    target = os.path.basename(script_path)
    data = load_processed()
    for ep in data.get("episodes", []):
        if os.path.basename(ep.get("script_path", "")) == target:
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
# ============================================================

OFFICE_TOPICS = [
    "The hospital billing system charged a patient for a gold-plated checkup",
    "The accounts department keeps rejecting the cat food expense report",
    "The patient in room 3 asked if the hospital has a cat menu",
    "The finance department's monthly budget meeting went completely off the rails",
    "The hospital generator failed during a power outage in the ER",
    "The reception desk keeps sending patients to the wrong department",
    "The vending machine in the hospital lobby ate the nurses' change",
    "The hospital cafeteria ran out of tuna sandwiches at lunch",
    "The new intern nurse lost the patient records cart",
    "The accounts department posted the salaries on the bulletin board by mistake",
    "The doctor's handwriting on the prescription is impossible to read",
    "The hospital IT cat Imti had to restart the whole EMR system again",
    "The pharmacy ran out of the good painkillers right before the night shift",
    "The hospital security cat caught someone sneaking out with a wheelchair",
    "The finance cat Meow found a mystery expense that nobody will own up to",
    "The HR cat Zulfi scheduled mandatory wellness training during the busiest shift",
    "The hospital's new patient paging system beeps at 3 AM for no reason",
    "The accounts team argued about who broke the calculator",
    "The hospital has a new mascot and it's a literal meerkat",
    "The blood test lab mixed up the results of two very different patients",
    "The hospital's MRI machine is haunted by a ghost, says the radiologist",
    "The finance department audit made everyone panic about their expense claims",
    "The hospital parking lot charges more than the actual treatment",
    "The patient complained that the hospital food tastes like the office food",
    "The nurse station's coffee machine is out of order again",
    "The hospital HR cat sent a policy about not napping in the supply closet",
    "The accounts department found an invoice for a mystery shipment of 500 kiwis",
    "The hospital's new digital check-in kiosk is driving everyone insane",
    "The billing department double-charged a patient for a band-aid",
    "The hospital administrator planned a team-building day at the zoo",
    "The finance cat tried to expense a luxury cat bed as office furniture",
    "The hospital's emergency alarm drill happened during the lunch rush",
    "The accounts department is doing a surprise inventory of every paperclip",
    "The new doctor keeps prescribing naps as treatment and patients love it",
    "The hospital gift shop is selling branded cat bandanas",
    "The finance team discovered the hospital has been paying for a ghost subscription",
    "The hospital's water cooler became a turf war between departments",
    "The HR cat organized a bring-your-own-lunch day and nobody brought lunch",
    "The hospital printer jammed right before the board meeting presentation",
    "The accounts department lost the receipts for an entire month",
    "The hospital's intercom keeps playing elevator music during code blues",
    "The finance cat audited the snack cart and the results were scandalous",
    "The hospital reception cat gave a patient directions to the wrong floor",
    "The accounts team is fighting over who gets the good stapler",
    "The hospital's new uniforms are unflattering and everyone is complaining",
    "The IT cat Imti's emergency patch at 3 AM shut down the lab equipment",
    "The HR cat scheduled a surprise fire drill during the accounts close",
    "The hospital's cafeteria merged with the gift shop by accident",
    "The finance department found a mystery charge for 'mystery meat'",
    "The hospital administrator tried to make the cats the official mascots",
    "The accounts team's calculator addiction is out of control",
    "The hospital's air conditioning war between the wards and the admin wing",
    "The billing department sent a patient an invoice written in meme format",
    "The hospital's parking garage elevator is possessed",
    "The finance cat discovered the hospital pays for 500 unused desks",
    "The new hospital policy forbids cats from using the elevators",
    "The accounts department celebrated its smallest budget cut with a parade",
    "The hospital's vending machine gives free snacks after midnight",
    "The IT cat Imti's cable management disaster in the server room",
    "The hospital's mystery sticky note campaign is blaming the accounts team",
    "The finance cat's expense report for 'patient research' was just cat toys",
    "The hospital's lunch table politics between the wards and admin",
    "The accounts department's mandatory fun Friday was a spreadsheet party",
    "The hospital's new kiosk keeps asking patients for their cat's name",
    "The finance team audited the vending machine and found a crime ring",
    "The hospital administrator's motivational speech put everyone to sleep",
    "The accounts cat counted the same box of band-aids five times",
    "The hospital's elevator is haunted by the ghost of a fax machine",
    "The billing department's hold music is the sound of a dying printer",
    "The hospital's fire drill during the finance close was chaos",
    "The finance cat's audit spreadsheet is so complex nobody dares open it",
    "The hospital's new policy says no catnip in the break room",
    "The accounts team's Monday morning mood is medically dangerous",
    "The hospital's secret files are just a folder labeled 'do not open'",
    "The finance department's coffee stain detective is on the case again",
    "The hospital's vending machine monopoly by the snack cart gang",
    "The accounts cat got a paper cut and made it a whole medical incident",
    "The hospital's new HR policy nobody follows: no napping in meetings",
    "The finance team's performance review panic about the annual budget",
    "The hospital's gift shop started selling 'mystery expired snacks'",
    "The accounts department's window seat battle turned into a turf war",
    "The hospital's medical records cat keeps losing the good pen",
    "The finance cat found a recurring charge for 'emotional support tuna'",
    "The hospital administrator's employee satisfaction survey backfired",
    "The accounts team's headphone conspiracy in the open-plan ward",
    "The hospital's new badge system locks everyone out at lunch",
    "The finance department's 'team building' was a budget-cutting contest",
    "The hospital's emergency snack stash got raided by the night shift",
    "The accounts cat balanced the hospital books to the penny and is now smug",
    "The hospital's mystery USB drive found in the break room",
    "The finance team's office supply hoarding problem is now a hazard",
    "The hospital's thermostat war between the wards and the morgue",
    "The accounts department's 'quiet hour' is a myth",
    "The hospital's new robot janitor is stealing everyone's snacks",
    "The finance cat's backup of the budget file is just a screenshot",
    "The hospital's dress code confusion after casual Friday was banned",
    "The accounts team found a charge for 10,000 mugs nobody ordered",
    "The hospital's meeting room booking system double-books everything",
    "The finance cat's emergency budget patch saved the day but made enemies",
    "The hospital's new intern's first day disaster in the accounts department",
    "The accounts team's secret files are just a folder of budget memes",
    "The hospital's lunch theft ring is finally being investigated",
    "The finance department's wellness initiative lasted exactly one day",
    "The accounts cat's spreadsheet has 47 hidden tabs and a password",
    "The hospital's new policy on 'cat-friendly meetings' confused everyone",
    "The finance team's emergency audit at 3 AM caught someone napping",
    "The hospital's mysterious email from the CEO was just an apology",
    "The accounts department's group chat is 90 percent memes and 10 percent panic",
    "The hospital's coffee machine conspiracy: who keeps taking the last cup",
    "The finance cat's annual 'budget day' is treated like a disaster drill",
    "The hospital's new printer only works when the accounts cat is near it",
    "The accounts team's holiday party planning committee is in chaos",
    "The hospital's mystery invoice for 'emergency kitten supplies'",
    "The finance department's revenue report is 3 pages of cat doodles",
]

def load_character_memory():
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
    memory = load_character_memory()
    memory["episodes_done"] = memory.get("episodes_done", 0) + 1
    memory.setdefault("past_topics", []).append(topic)
    memory["past_topics"] = memory["past_topics"][-10:]

    if memory.get("episodes_done", 0) % 3 == 0 and len(memory.get("running_jokes", [])) < 5:
        joke = f"The cats still bring up: '{topic}' from a few episodes ago"
        memory.setdefault("running_jokes", []).append(joke)

    save_character_memory(memory)

def _get_memory_context():
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
    memory_context = _get_memory_context()
    return f"""Write a natural, funny cat podcast conversation about: {topic}

SETTING: The cats work at a busy HOSPITAL. The hospital has many departments:
accounts/finance (where Meow works), HR (where Zulfi works), IT (where Imti
works), billing, pharmacy, reception, ER, lab, nursing. Keep ALL discussion about
hospital work, hospital life, hospital gossip, hospital departments, patients,
medical billing, hospital admin nonsense, and workplace drama in the hospital.

STYLE - This is a GOOD example of how the dialogue should sound (mimic this energy):
Speaker 1: Okay okay, so you're never gonna believe what happened.
Speaker 2: I always don't believe what you're about to say. That's my whole thing.
Speaker 1: No, this time it's real. Like, actually real. Hehe.
Speaker 2: You said that about the mouse that was just a leaf.
Speaker 1: ...it looked like a mouse from behind, okay?! Big yikes, moving on.
Imti: Are we talking about the hospital's broken billing machine again?
Speaker 1: Imti!! Perfect timing, bro. You're IT, you gotta hear this.
Imti: I literally just fixed that billing terminal yesterday. It's always DNS.
Speaker 2: It's never DNS.
Imti: ...it's DNS.

Characters (all hospital workers):
- Simba (Speaker 1): Confident, silly orange Tabby, works in the hospital IT department, exaggerates stories, says "trust me bro"
- Meow (Speaker 2): Smart, sarcastic, dry wit, works in hospital accounts/finance, says "anyway" and "that's concerning", keeps Simba honest
- Imti: Hospital IT cat (Simba's IT colleague), stressed about the EMR system and medical devices, says "have you tried restarting the EMR"
- Zulfi: Hospital HR cat, formal, says "per the hospital compliance handbook", sends too many policy emails

USE THESE NATURAL SPEECH TOOLS (mix them in, don't overdo):
- Fillers: "hmm", "oh", "um", "uh", "wait", "right?", "you know?", "like"
- Reactions: "haha", "oh my god", "no way", "seriously?", "big yikes", "oof"
- Slang (light sprinkle): "lowkey", "no cap", "fr", "sus", "vibes", "bro"
- Interruptions: someone cuts off another mid-sentence
- Short punchy lines: "No.", "Yes.", "What?!", "Exactly!", "Nope."
- Laughter: "haha", "lol", "hehe", "pfft"
- Pauses: "..." or "--"

STRUCTURE (emotional arc):
1. OPENING HOOK (2-4 lines): someone reveals juicy hospital gossip about the topic
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
- Sound like real friends chatting at the hospital, not a script

{memory_context}

Conversation:"""


def _parse_ai_script(raw_text):
    valid_speakers = ["Speaker 1", "Speaker 2", "Imti", "Zulfi"]
    lines = []
    for l in raw_text.split("\n"):
        l = l.strip()
        if not l or ":" not in l:
            continue
        speaker = l.split(":", 1)[0].strip()
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

def _generate_hf():
    import requests
    api_key = os.environ.get("HF_API_KEY", os.environ.get("HUGGINGFACE_API_KEY", ""))
    if not api_key:
        raise Exception("No HF_API_KEY set")

    topic = _pick_unique_topic()
    print(f"  [HF] Generating script about: {topic}")
    prompt = _get_script_prompt(topic)

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

def _generate_groq():
    import requests
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise Exception("No GROQ_API_KEY set")

    topic = _pick_unique_topic()
    print(f"  [Groq] Generating script about: {topic}")
    prompt = _get_script_prompt(topic) + "\n\nWrite ONLY the dialogue, no extra text."

    url = "https://api.groq.com/openai/v1/chat/completions"
    response = requests.post(url, 
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.95,
            "max_tokens": 1500
        }, 
        timeout=30  # 30 second timeout, not 120 minutes
    )

    if response.status_code != 200:
        raise Exception(f"Groq API error {response.status_code}: {response.text[:200]}")

    data = response.json()
    script = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    lines = _parse_ai_script(script)
    if len(lines) < 10:
        raise Exception(f"Script too short ({len(lines)} lines)")

    print(f"  [Groq] Generated {len(lines)} lines")
    return _save_script(lines, topic)

def _generate_template():
    topic = _pick_unique_topic()
    templates = [
        f"""Speaker 1: Oh my god, did you hear about the {topic.lower()}?
Speaker 2: Wait, what? What happened?
Speaker 1: It's... it's crazy. Like, seriously crazy.
Speaker 2: You're scaring me. What happened?
Speaker 1: So basically... okay, so you know how the hospital is, right?
Speaker 2: Yeah...?
Speaker 1: Well, apparently... someone... um... someone did something.
Speaker 2: Someone did something. That's very specific.
Speaker 1: I'm getting there! Don't rush me!
Speaker 2: You literally just said "oh my god" and now you're stalling.
Imti: Hey guys, what's going on?
Speaker 1: Imti! Perfect timing! Did you fix the billing terminal yet?
Imti: The billing machine? Again? What happened this time?
Speaker 2: Simba was telling me about the {topic.lower()}.
Imti: Oh, that. Yeah, I saw the email. Not my problem though.
Speaker 1: Not your problem? You're IT!
Imti: I fix the EMR system, not hospital drama. Besides, I'm busy with the server.
Speaker 2: The server? What's wrong with it?
Imti: Nothing... yet. But it's making weird noises.
Speaker 1: Ghost noises?
Imti: No, not ghost noises. Hum noises. Probably.
Speaker 2: Probably?
Imti: Look, I'll check it later. Right now I need coffee from the cafeteria.
Speaker 1: Coffee! Great idea! Let's all get coffee!
Speaker 2: We're literally in the middle of recording.
Speaker 1: Oh. Right. Hehe. Hehe.""",
        f"""Speaker 1: So anyway, about the {topic.lower()}...
Speaker 2: Wait, Zulfi's coming.
Zulfi: Good morning everyone. I hope you're all having a productive shift.
Speaker 1: Hey Zulfi! What's up?
Zulfi: I need to discuss the new hospital policy regarding {topic.lower()}.
Speaker 2: There's a policy for that?
Zulfi: There's a policy for everything, Meow. Page 47, section 3, paragraph 2 of the hospital compliance handbook.
Speaker 1: You memorized the policy manual?
Zulfi: Of course. It's my job. Now, as I was saying...
Speaker 2: Can we just skip to the part where we ignore it?
Zulfi: That's... not how policies work.
Speaker 1: Yeah Meow, we have to follow the rules!
Speaker 2: You never follow rules.
Speaker 1: I follow Simba's rules. Which are different.
Zulfi: There are no "Simba's rules" in the hospital handbook.
Speaker 1: There should be! Rule number one: Simba is always right.
Zulfi: That's... actually concerning.
Speaker 2: Welcome to my world.
Speaker 1: Okay okay, fine. What's the actual policy, Zulfi?
Zulfi: Well, according to section 3, paragraph 2...
Speaker 1: Oh wait, I have to check on a patient's chart. Be right back.
Zulfi: ...He's gone. He always does this.
Speaker 2: I know.""",
        f"""Speaker 2: Finally, some peace and quiet.
Imti: Hey Meow, where's Simba?
Speaker 2: Hopefully far away. He was driving me crazy.
Zulfi: Has anyone seen Simba? I need his expense report for the department.
Speaker 2: He said something about the printer in the billing office and disappeared.
Imti: The printer? I just fixed that yesterday.
Speaker 2: Exactly.
Zulfi: Well, when you see him, tell him the report is due by 5 PM.
Imti: Yeah, good luck with that.
Speaker 2: So Imti, what's really wrong with the hospital server?
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
Imti: Hey, I'm IT. I fix the medical devices. I don't follow HR rules.
Zulfi: That's going in my report.
Imti: Which report? The one the hospital board never reads?""",
    ]
    script = random.choice(templates)
    print(f"  [Template] Generated about: {topic}")
    return _save_script(script.split("\n"), topic)

def generate_script_with_ai():
    print("[0/5] Generating script...")
    try:
        result = _generate_hf()
        if result: return result
    except Exception as e:
        print(f"  [SKIP] HF failed: {e}")

    try:
        result = _generate_groq()
        if result: return result
    except Exception as e:
        print(f"  [SKIP] Groq failed: {e}")

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
    basename = os.path.basename(script_path)
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            first = f.readline().strip()
        if first and ":" in first:
            text = first.split(":", 1)[1].strip().strip('?!.," ')
            text = text.replace(",", "")
            for prefix in ["oh my god did you hear about", "did you hear about",
                           "so anyway about the", "so basically", "okay so",
                           "oh my god did you hear"]:
                if text.lower().startswith(prefix):
                    text = text[len(prefix):].strip('?!.," ')
                    break
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
    if not text: return None
    t = text.lower()
    if any(w in t for w in ["hahahaha", "hahahaa", "hahaha", "hahaa", "haha", "lol", "lmao", "rofl", "kekeke"]): return "laugh"
    if any(w in t for w in ["hehehe", "hehe", "hee hee", "hihihi", "giggle"]): return "giggle"
    if any(w in t for w in ["pfft", "snort", "snicker", "pshh"]): return "snort"
    if any(w in t for w in ["gasp", "*gasp*", "oh my god", "oh my gosh", "no way", "what?!", "whaat", "whoa", "woah", "ooh", "ohh!", "ahh!", "ahhh", "wowww", "wooow", "woooow", "omg", "hold on", "huh?"]): return "gasp"
    if any(w in t for w in ["sigh", "ugh", "ughh", "uggg", "meh", "*sigh*", "pff", "ehhh", "hmmph"]): return "sigh"
    if any(w in t for w in ["whoosh", "swoosh", "wooosh", "woooosh", "woooosh!", "dramatic", "swish"]): return "whoosh"
    if any(w in t for w in ["ba dum tss", "badumtss", "rimshot", "drum roll", "drumroll"]): return "rimshot"
    if any(w in t for w in ["applause", "clap", "*claps*", "round of applause", "bravo"]): return "applause"
    return None

def _synthesize_sfx(name, output_path):
    try:
        if name == "laugh" or name == "giggle":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'sine=frequency=700:duration=0.5', '-af', 'aecho=0.8:0.7:60|120:0.4|0.3,volume=0.8', '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "snort":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'anoisesrc=d=0.3:c=pink:r=44100:a=0.5', '-af', 'lowpass=f=800,volume=0.7', '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "gasp":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'anoisesrc=d=0.15:c=white:r=44100:a=0.4', '-af', 'highpass=f=1500,lowpass=f=4000,volume=1.5', '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "sigh":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'sine=frequency=400:duration=0.8', '-af', 'afade=t=out:st=0.5:d=0.3,volume=0.4', '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "applause":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'anoisesrc=d=1.5:c=pink:r=44100:a=0.3', '-af', 'lowpass=f=3000,volume=1.2', '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        elif name == "drumroll":
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'anoisesrc=d=1.2:c=white:r=44100:a=0.3', '-af', 'lowpass=f=2000,volume=0.8', '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        else:
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'anoisesrc=d=0.5:c=white:r=44100:a=0.5', '-af', 'bandpass=f=2000:w=1000,volume=0.9', '-c:a', 'libmp3lame', '-b:a', '128k', output_path]
        subprocess.run(cmd, capture_output=True, timeout=15)
        return os.path.exists(output_path)
    except Exception:
        return False

def ensure_sound_effects():
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
        return audio_path

    duration = get_audio_duration(audio_path)
    total_lines = len(script_lines)
    seg_times = get_segment_times(output_dir, total_lines, duration)
    sfx_events = []

    for i, (speaker, text) in enumerate(script_lines):
        sfx = get_sound_effect(text)
        if sfx and sfx in sfx_paths:
            timestamp = seg_times[i][0]
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
# ============================================================

def parse_script(script_path):
    lines = []
    with open(script_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line: continue
            parts = line.split(":", 1)
            if len(parts) < 2: continue
            speaker = parts[0].strip()
            text = parts[1].strip()
            if text and speaker in VOICES:
                lines.append((speaker, text))
    return lines

def get_speaker_color(speaker):
    colors = {"Speaker 1": "#ff6b35", "Speaker 2": "#4a9eff", "Imti": "#00ff88", "Zulfi": "#ff44ff"}
    return colors.get(speaker, "#ffffff")

NATURAL_PREFILLERS = ["Hmm,", "Ohh,", "Wait,", "Okay so,", "So,", "Well,"]
NATURAL_LONG_EXCL = ["Woooow!", "Whoa!", "No way!", "Oof.", "Hahaha!", "Hehe.", "Ugh...", "Ooh!"]
NATURAL_SHORT_EXCL = ["Hmm.", "Eh.", "Oof.", "Hahaha!", "Hehe.", "Pfft.", "Mmm.", "Ooh!"]
_last_filler = None

def _pick_filler():
    global _last_filler
    options = [f for f in NATURAL_PREFILLERS if f != _last_filler]
    if not options: options = NATURAL_PREFILLERS
    chosen = random.choice(options)
    _last_filler = chosen
    return chosen

def naturalize_text(text, line_index, total_lines):
    t = text.strip()
    if not t or "[" in t or "]" in t: return t
    low = t.lower()
    already_expressive = any(w in low for w in ["hmm", "ohh", "oh my", "wow", "whoa", "haha", "hehe", "ugh", "oof", "mmm", "pfft", "ooh", "wait", "like,"])
    if already_expressive: return t
    has_question = t.rstrip().endswith("?")
    has_exclaim = "!" in t
    is_last = line_index >= total_lines - 2
    is_first = line_index <= 0
    is_short = len(t) < 25

    if is_last:
        opener = random.choice(["Okay so,", "So,", "Well,", ""])
        tail = random.choice([" ...hahaha!", " ...oof.", " ...goodnight everyone.", ""])
    elif is_first:
        opener = random.choice(["Okay okay, ", "So, ", "Alright, "])
        tail = random.choice([" ...hehe.", " ...right?", ""])
    elif is_short:
        if has_question:
            opener = ""
            tail = random.choice([" ...?", " ...hmm?", " ...right?", ""])
            if random.random() < 0.3: opener = random.choice(["Wait, ", "Hmm, "])
        else:
            opener = random.choice(["Ohh, ", "Wait, ", "No way, ", "Hahaha! ", "Pfft. ", ""])
            tail = random.choice([" ", " haha.", " oof.", "!"])
    else:
        opener = ""
        if random.random() < 0.30: opener = _pick_filler() + " "
        tail = ""
        if has_exclaim and random.random() < 0.35:
            tail = random.choice(["!", " ...wow!", " ...hahaha!", ""])
        elif random.random() < 0.12:
            tail = random.choice([" ...hehe.", " ...oof.", " ...right?", ""])
    return opener + t + tail

def _tts_edge(segments_dir, lines):
    import edge_tts
    segment_files = []
    async def gen_segment(i, speaker, text, seg_path):
        voice = VOICES[speaker]
        spoken = naturalize_text(text, i, len(lines))
        rate = "+8%"
        if text.startswith("..."): rate = "-2%"
        elif "!" in text and len(text) < 20: rate = "+15%"
        elif speaker == "Simba" or speaker == "Speaker 1": rate = "+10%"
        elif speaker == "Meow" or speaker == "Speaker 2": rate = "+8%"
        elif speaker == "Imti": rate = "+12%"
        elif speaker == "Zulfi": rate = "+4%"
        if NATURAL_MODE:
            # SSML already embeds voice + rate + pitch + pauses
            ssml = _build_ssml(speaker, spoken, rate)
            c = edge_tts.Communicate(ssml)
        else:
            c = edge_tts.Communicate(spoken, voice, rate=rate)
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

def _tts_gtts(segments_dir, lines):
    from gtts import gTTS
    segment_files = []
    gtts_voices = {"Speaker 1": "en", "Speaker 2": "en", "Imti": "en", "Zulfi": "en"}
    for i, (speaker, text) in enumerate(lines):
        seg_path = os.path.join(segments_dir, f"seg_{i:04d}.mp3")
        try:
            lang = gtts_voices.get(speaker, "en")
            spoken = naturalize_text(text, i, len(lines))
            tts = gTTS(text=spoken, lang=lang)
            tts.save(seg_path)
            if os.path.exists(seg_path): segment_files.append(seg_path)
        except Exception as e:
            print(f"  [gTTS] segment {i} failed: {e}")
    return segment_files

def _tts_pyttsx3(segments_dir, lines):
    import pyttsx3
    engine = pyttsx3.init()
    segment_files = []
    for i, (speaker, text) in enumerate(lines):
        seg_path = os.path.join(segments_dir, f"seg_{i:04d}.wav")
        try:
            engine.save_to_file(text, seg_path)
            engine.runAndWait()
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
    if not lines: return None

    segments_dir = os.path.join(output_dir, "segments")
    os.makedirs(segments_dir, exist_ok=True)
    segment_files = []

    try:
        print("  [Edge TTS] Generating segments...")
        segment_files = _tts_edge(segments_dir, lines)
        if segment_files: print(f"  [OK] Edge TTS: {len(segment_files)} segments")
        else: raise Exception("No segments generated")
    except Exception as e:
        print(f"  [SKIP] Edge TTS failed: {e}")

    if not segment_files:
        try:
            print("  [gTTS] Generating segments...")
            segment_files = _tts_gtts(segments_dir, lines)
            if segment_files: print(f"  [OK] gTTS: {len(segment_files)} segments")
            else: raise Exception("No segments generated")
        except Exception as e:
            print(f"  [SKIP] gTTS failed: {e}")

    if not segment_files:
        try:
            print("  [pyttsx3] Generating segments (offline)...")
            segment_files = _tts_pyttsx3(segments_dir, lines)
            if segment_files: print(f"  [OK] pyttsx3: {len(segment_files)} segments")
            else: raise Exception("No segments generated")
        except Exception as e:
            print(f"  [FATAL] All TTS methods failed: {e}")
            return None

    concat_file = os.path.join(segments_dir, "concat.txt")
    with open(concat_file, 'w') as f:
        for seg in segment_files:
            f.write(f"file '{os.path.abspath(seg).replace(os.sep, '/')}'\n")

    raw_audio = os.path.join(output_dir, "raw_audio.mp3")
    cmd = [FFMPEG_EXE, '-y', '-f', 'concat', '-safe', '0', '-i', concat_file, '-c', 'copy', raw_audio]
    subprocess.run(cmd, capture_output=True, timeout=60)

    if not os.path.exists(raw_audio): return None

    normalized_audio = os.path.join(output_dir, "episode_audio.mp3")
    cmd = [FFMPEG_EXE, '-y', '-i', raw_audio, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:a', 'libmp3lame', '-b:a', '192k', normalized_audio]
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
    cmd = [FFPROBE_EXE, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
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
        if not line or ":" not in line: continue
        parts = line.split(":", 1)
        if len(parts) >= 2 and parts[1].strip():
            dialogue.append(parts[1].strip())

    if not dialogue: return None

    times = get_segment_times(output_dir, len(dialogue), total_duration)
    srt_content = ""
    for i, text in enumerate(dialogue):
        start, end = times[i]
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
    cmd = [FFPROBE_EXE, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
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

def _get_background_fallback(output_dir):
    existing = get_all_backgrounds()
    if existing: return random.choice(existing)

    try:
        import requests
        os.makedirs(IMAGES_DIR, exist_ok=True)
        # NOTE: AI image models often bake fake gibberish text/URLs into
        # "studio" scenes. Explicitly forbid text, words, letters, signage and
        # logos so the background doesn't show URL-like artifacts in the video.
        prompt = "two cartoon cats sitting on cozy chairs in a warm podcast studio with plant pots, wooden desk, microphones, soft warm lighting, bookshelves, cozy interior, no text, no words, no letters, no signage, no logos, no URLs"
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1280&height=720&nologo=true&model=flux"
        resp = requests.get(url, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            img_path = os.path.join(IMAGES_DIR, f"gen_{hashlib.md5(resp.content).hexdigest()[:8]}.jpg")
            with open(img_path, 'wb') as f: f.write(resp.content)
            if os.path.getsize(img_path) > 1000:
                print(f"  Generated background via Pollinations")
                return img_path
    except Exception as e:
        print(f"  [SKIP] Pollinations failed: {e}")

    try:
        import requests
        url = "https://picsum.photos/1280/720"
        resp = requests.get(url, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            img_path = os.path.join(IMAGES_DIR, f"picsum_{hashlib.md5(resp.content).hexdigest()[:8]}.jpg")
            with open(img_path, 'wb') as f: f.write(resp.content)
            if os.path.getsize(img_path) > 1000:
                print(f"  Downloaded background from Picsum")
                return img_path
    except Exception as e:
        print(f"  [SKIP] Picsum failed: {e}")

    try:
        img_path = os.path.join(output_dir, "generated_bg.jpg")
        cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1280x720:d=1', '-frames:v', '1', img_path]
        subprocess.run(cmd, capture_output=True, timeout=10)
        if os.path.exists(img_path):
            print(f"  Generated solid color background")
            return img_path
    except:
        pass
    return None

def create_intro_screen(output_dir, episode_title, episode_number):
    intro_path = os.path.abspath(os.path.join(output_dir, "intro.mp4"))
    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1280x720:d=4',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '44100', '-t', '4', intro_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, cwd=output_dir)
    except:
        pass
    return intro_path if os.path.exists(intro_path) else None

def create_outro_screen(output_dir, episode_number=None):
    outro_path = os.path.abspath(os.path.join(output_dir, "outro.mp4"))
    cmd = [
        FFMPEG_EXE, '-y',
        '-f', 'lavfi', '-i', 'color=c=#1a1a2e:s=1280x720:d=5',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '44100', '-t', '5', outro_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, cwd=output_dir)
    except:
        pass
    return outro_path if os.path.exists(outro_path) else None

def get_speaker_image(speaker):
    keywords = {
        "Speaker 1": ["orange"],
        "Speaker 2": ["black"],
        "Imti": ["wide", "studio", "two"],
        "Zulfi": ["wide", "studio", "two"],
    }
    kws = keywords.get(speaker, [])
    if os.path.exists(IMAGES_DIR):
        for f in os.listdir(IMAGES_DIR):
            low = f.lower()
            if not f.endswith((".jpg", ".jpeg", ".png")) or f.startswith("episode"): continue
            if any(k in low for k in kws):
                return os.path.join(IMAGES_DIR, f)
    return None

def _speaker_display_name(speaker):
    return {"Speaker 1": "Simba", "Speaker 2": "Meow", "Imti": "Imti", "Zulfi": "Zulfi"}.get(speaker, speaker)

def get_segment_times(output_dir, num_lines, total_duration):
    seg_dir = os.path.join(output_dir, "segments")
    segs = sorted(glob.glob(os.path.join(seg_dir, "seg_*.mp3")))
    if len(segs) >= num_lines:
        starts = []
        cursor = 0.0
        for i in range(num_lines):
            d = get_audio_duration(segs[i])
            starts.append((cursor, cursor + d))
            cursor += d
        if cursor > 0 and abs(cursor - total_duration) > 0.3:
            scale = total_duration / cursor
            starts = [(s * scale, e * scale) for s, e in starts]
        return starts
    step = total_duration / max(num_lines, 1)
    return [(i * step, (i + 1) * step) for i in range(num_lines)]

def create_speaker_video(audio_path, output_dir, script_lines, episode_title, episode_number):
    print("  Building per-speaker video segments...")
    if not script_lines: return None
    total_duration = get_audio_duration(audio_path)
    times = get_segment_times(output_dir, len(script_lines), total_duration)

    clips = []
    seg_out = os.path.join(output_dir, "speaker_clips")
    os.makedirs(seg_out, exist_ok=True)
    for i, (speaker, text) in enumerate(script_lines):
        start, end = times[i]
        clip_dur = max(0.5, end - start)
        img = get_speaker_image(speaker)
        if not img: img = _get_background_fallback(output_dir)
        if not img: return None
        img = os.path.abspath(img)
        clip_path = os.path.join(seg_out, f"clip_{i:04d}.mp4")
        # Blur the image and overlay a sharp centered copy so any AI-generated
        # fake text/URLs baked into the background become unreadable, while the
        # subject (cat) stays crisp.
        vf = (
            "split=2[a][b];"
            "[a]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=12[bg];"
            "[b]scale=900:-1[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        cmd = [
            FFMPEG_EXE, '-y', '-loop', '1', '-i', img,
            '-ss', str(start), '-t', str(clip_dur), '-i', audio_path,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-pix_fmt', 'yuv420p',
            '-vf', vf, '-shortest', clip_path
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=output_dir)
            if r.returncode != 0:
                print(f"  [speaker clip {i}] error: {r.stderr[-150:]}")
        except Exception as e:
            print(f"  [speaker clip {i}] failed: {e}")
        if os.path.exists(clip_path):
            clips.append(clip_path)

    if len(clips) < len(script_lines):
        print(f"  [WARN] Only {len(clips)}/{len(script_lines)} speaker clips built")
    if not clips: return None

    concat_list = os.path.join(output_dir, "speaker_concat.txt")
    with open(concat_list, 'w') as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c).replace(os.sep, '/')}'\n")
    video_path = os.path.join(output_dir, "main_speaker.mp4")
    cmd = [FFMPEG_EXE, '-y', '-f', 'concat', '-safe', '0', '-i', concat_list, '-c', 'copy', video_path]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120, cwd=output_dir)
    except Exception as e:
        print(f"  speaker concat failed: {e}")
    return video_path if os.path.exists(video_path) else None

def create_main_video(audio_path, bg_image, output_dir, episode_title, episode_number):
    audio_path = os.path.abspath(audio_path)
    bg_image = os.path.abspath(bg_image)
    video_path = os.path.join(output_dir, "main_video.mp4")
    vf = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720"
    cmd = [
        FFMPEG_EXE, '-y', '-loop', '1', '-i', bg_image, '-i', audio_path,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-pix_fmt', 'yuv420p',
        '-vf', vf, '-shortest', video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=output_dir)
        if result.returncode != 0:
            print(f"  FFmpeg error: {result.stderr[:300]}")
    except Exception as e:
        print(f"  FFmpeg failed: {e}")

    if not os.path.exists(video_path):
        print("  Retrying without text overlays...")
        vf_no_text = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720"
        cmd2 = [
            FFMPEG_EXE, '-y', '-loop', '1', '-i', bg_image, '-i', audio_path,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-pix_fmt', 'yuv420p',
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
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', final_path
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

def create_video(audio_path, subtitle_path, output_dir, episode_title, episode_number, script_lines=None):
    print("[3/5] Creating video with all features...")
    bg = _get_background_fallback(output_dir)
    if not bg:
        print("  ERROR: No background images available")
        return None

    duration = get_audio_duration(audio_path)
    print(f"  Duration: {duration:.0f}s")

    main_video = None
    if script_lines:
        main_video = create_speaker_video(audio_path, output_dir, script_lines, episode_title, episode_number)
    if not main_video:
        print(f"  Background: {os.path.basename(bg)}")
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

    cmd = [FFMPEG_EXE, '-y', '-f', 'concat', '-safe', '0', '-i', concat_list, '-c', 'copy', concat_path]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except:
        pass

    if os.path.exists(concat_path):
        return concat_path
    return video_with_music

# ============================================================
# THUMBNAIL
# ============================================================

def create_thumbnail(output_dir, episode_title, episode_number):
    print("[4/5] Creating thumbnail...")
    thumbnail = os.path.abspath(os.path.join(output_dir, "thumbnail.png"))

    backgrounds = get_all_backgrounds()
    if not backgrounds:
        cmd = [
            FFMPEG_EXE, '-y', '-f', 'lavfi',
            '-i', 'color=c=#1a1a2e:s=720x540:d=1',
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
    if os.path.exists(bg):
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

    try:
        with open(TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)
    except (ModuleNotFoundError, AttributeError) as e:
        print(f"  [WARN] Token incompatible: {e}")
        print("  [WARN] Re-authenticate on this machine: python authenticate_youtube.py")
        return None

    # FIX: Check token scopes to prevent silent 403 failures on playlists
    token_scopes = getattr(creds, 'scopes', []) or []
    if "https://www.googleapis.com/auth/youtube" not in token_scopes:
        print("  WARNING: Token does not have 'youtube' scope. Playlist creation will fail!")
        print("  Please delete youtube_token.pickle and regenerate it using the fixed youtube_upload.py")

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
Four cats, Simba, Meow, Imti, and Zulfi, work at a busy hospital and discuss hospital gossip in a hilarious podcast format.
New episodes daily!

Characters:
- Simba: Confident orange tabby, works in Hospital IT, tells exaggerated stories
- Meow: Smart, sarcastic, works in Hospital Accounts/Finance, keeps Simba in check
- Imti: Hospital IT cat, always fixing the EMR system, speaks geek
- Zulfi: Hospital HR cat, formal, sends too many policy emails

---
Subscribe: https://youtube.com/@thesimbashowss
---

#CatPodcast #SimbaAndMeow #FunnyCats #HospitalHumor #TheSimbaShow #CatComedy #Podcast #Shorts #HospitalLife #CatComedy"""

    # FIX: Properly format and slice the title string
    yt_title = f"The Simba Show Ep.{episode_number} - {title}"[:100]

    body = {
        "snippet": {
            "title": yt_title,
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
        # Non-fatal: video is already public. Usually a 403 because the token
        # lacks the full 'youtube' scope (re-run authenticate_youtube.py to fix).
        print(f"  Playlist skipped (scope/permission): {e}")
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

def upload_short(video_path, title, description, tags, thumbnail_path=None):
    return None

# ============================================================
# MAIN
# ============================================================

def generate_episode(specific_number=None):
    print("=" * 60)
    print("CAT PODCAST - EPISODE GENERATOR v5")
    print("Fallback chains: HF->Groq->Template | Edge->gTTS->pyttsx3")
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

    video_path = create_video(audio_path, subtitle_path, output_dir, episode_title, ep_count, script_lines)
    if not video_path:
        print("\nFAILED: Video")
        return None

    thumbnail_path = create_thumbnail(output_dir, episode_title, ep_count)

    description = f"""Simba and Meow discuss hospital gossip in this hilarious cat podcast!"""
    tags = [
        "cat podcast", "funny cats", "hospital cats", "cat comedy",
        "simba and meow", "cat dialogue", "funny cat videos",
        "cat humor", "hospital humor", "the simba show", "hospital gossip",
        "cat talk", "podcast", "daily podcast", "funny animals",
        "cat entertainment", "hospital comedy", "cat show"
    ]

    upload_result = upload_to_youtube(video_path, episode_title, description, tags, thumbnail_path, episode_number=ep_count)

    speakers_used = list(set([s for s, _ in script_lines]))
    metadata = {
        "script": script_path, "title": episode_title, "topic": topic,
        "episode_number": ep_count, "audio": audio_path, "video": video_path,
        "thumbnail": thumbnail_path, "upload": upload_result,
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
