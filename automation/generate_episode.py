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

def _generate_gemini():
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
        result = _generate_gemini()
        if result: return result
    except Exception as e:
        print(f"  [SKIP] Gemini failed: {e}")

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
            cmd = [FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'sine=frequency=700:duration=0.5', '-af', 'aecho=0.8:0.7:60|120:0.4|0.
