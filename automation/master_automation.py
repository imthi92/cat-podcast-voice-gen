#!/usr/bin/env python3
"""
Master Automation Script - Cat Podcast
Runs the complete pipeline: Script -> Audio -> Video -> YouTube
Fully automated, zero manual intervention.
"""

import os
import sys
import json
import random
import subprocess
from datetime import datetime
from pathlib import Path

# Import our modules
sys.path.insert(0, os.path.dirname(__file__))
from video_pipeline import run_pipeline, CONFIG as VIDEO_CONFIG
from youtube_upload import upload_episode

# ============================================================
# CONFIGURATION
# ============================================================

SCRIPTS_DIR = "./scripts"
OUTPUT_DIR = "./output"
EPISODES_DIR = "./episodes"
PROCESSED_FILE = "./processed_episodes.json"

# Office gossip topics for script generation
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
    "The HR department's new policy",
    "The accounting department's mysterious calculations",
    "The marketing team's brainstorming session",
    "The sales team's victory celebration",
    "The receptionist knows everything",
    "The parking lot drama",
    "The vending machine ate my money",
    "The fire drill during lunch hour",
]

# Script generation prompt
SCRIPT_PROMPT = """You are writing a funny cat podcast script for "The Simba Show".

Characters:
- Simba (Speaker 1): Confident, slightly stupid, thinks he knows everything, works in Marketing department, shares office gossip on the podcast without the manager knowing
- Meow (Speaker 2): Intelligent, sarcastic, works in Finance department (different department from Simba), frequently corrects Simba, delivers punchlines

Setting: Both work in the same office but different departments. Simba records the podcast secretly and shares office gossip. Sometimes the manager listens and confronts him the next day.

Topic: {topic}

Requirements:
1. Use format: Speaker 1: and Speaker 2:
2. Keep it 25-40 lines
3. Make it funny with office humor
4. Include Simba sharing gossip about the manager or office
5. Include Meow being sarcastic
6. End with a funny punchline
7. No profanity, keep it clean
8. Reference specific office situations (printers, meetings, lunch, etc.)

Write the script now:"""


# ============================================================
# PROCESSED EPISODES TRACKER
# ============================================================

def load_processed():
    """Load list of already processed episodes."""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            return json.load(f)
    return {"episodes": []}


def save_processed(data):
    """Save processed episodes list."""
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def mark_processed(episode_key, metadata):
    """Mark an episode as processed."""
    data = load_processed()
    data["episodes"].append({
        "key": episode_key,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata,
    })
    save_processed(data)


def is_processed(episode_key):
    """Check if episode was already processed."""
    data = load_processed()
    return any(ep["key"] == episode_key for ep in data["episodes"])


# ============================================================
# SCRIPT GENERATION (Using AI)
# ============================================================

def generate_script_with_ai(topic):
    """Generate a script using OpenAI API."""
    print(f"\n[AI] Generating script for: {topic}")

    try:
        import openai
        client = openai.OpenAI()  # Uses OPENAI_API_KEY env var

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You write funny cat podcast scripts."},
                {"role": "user", "content": SCRIPT_PROMPT.format(topic=topic)}
            ],
            temperature=0.8,
            max_tokens=1500,
        )

        script = response.choices[0].message.content.strip()
        print(f"  Script generated ({len(script.split(chr(10)))} lines)")
        return script

    except Exception as e:
        print(f"  AI generation failed: {e}")
        print("  Falling back to template script...")
        return generate_template_script(topic)


def generate_template_script(topic):
    """Generate a script from template (fallback)."""
    templates = [
        f"""Speaker 1: Did you hear about {topic.lower()}?
Speaker 2: What happened now, Simba?
Speaker 1: So apparently, the manager decided to implement a new policy. He sent an email at 3 AM. Who sends emails at 3 AM?
Speaker 2: Someone who doesn't sleep. Or someone who set a scheduled send and forgot.
Speaker 1: No no no. He was in the office. At 3 AM. Working on the policy. Alone. In the dark.
Speaker 2: That's actually kind of sad.
Speaker 1: It's kind of hilarious. He was so excited about this policy that he couldn't wait until morning. He had to send it immediately. At 3 AM. While eating leftover pizza from the fridge.
Speaker 2: How do you know he was eating pizza?
Speaker 1: I was there. I was sleeping on the filing cabinet. I saw everything. The pizza. The email. The maniacal typing. It was beautiful chaos.
Speaker 2: You were sleeping in the office again?
Speaker 1: I was conducting overnight surveillance. Quality control. Making sure the office was safe. From pizza thieves and 3 AM email senders.
Speaker 2: You're unbelievable.
Speaker 1: I'm dedicated. There's a difference. Now the policy says no food at desks. No food. At desks. How am I supposed to eat my tuna sandwiches?
Speaker 2: You're a cat. You don't have a desk.
Speaker 1: I have a spot on the printer. The printer is my desk. The warm printer. The humming printer. My favorite place.
Speaker 2: You sit on the printer and it jams every time.
Speaker 1: The printer jams because it's jealous. It knows I prefer the other printer. The newer one. The faster one. The one near the window.
Speaker 2: You're having an affair with a printer.
Speaker 1: I'm exploring my options. It's called career mobility. It's called networking. It's called having good taste in warm electronics.
Speaker 2: You're going to get fired.
Speaker 1: You can't fire a cat. We don't have contracts. We have naps. We have tuna. We have nine lives. What are they going to do? Fire me eight times? I'll be back. I'm always back. Like a boomerang. A furry boomerang.""",
    ]
    return random.choice(templates)


def generate_script_from_existing(topic):
    """Pick a script from existing files based on topic keywords."""
    scripts_dir = Path(SCRIPTS_DIR)

    if not scripts_dir.exists():
        return None

    scripts = list(scripts_dir.glob("*.txt"))
    if not scripts:
        return None

    # Try to match topic to script name
    topic_words = topic.lower().split()
    for script in scripts:
        name_words = script.stem.lower().replace("_", " ").split()
        if any(word in name_words for word in topic_words if len(word) > 3):
            print(f"  Found matching script: {script.name}")
            with open(script, 'r', encoding='utf-8') as f:
                return f.read()

    # Pick random script if no match
    random_script = random.choice(scripts)
    print(f"  Using random script: {random_script.name}")
    with open(random_script, 'r', encoding='utf-8') as f:
        return f.read()


# ============================================================
# MASTER AUTOMATION
# ============================================================

def run_full_automation(topic=None, publish=False):
    """Run the complete automated pipeline."""
    print("=" * 70)
    print("CAT PODCAST - MASTER AUTOMATION")
    print("=" * 70)
    print(f"Time: {datetime.now().isoformat()}")

    # Step 1: Select or generate topic
    if not topic:
        topic = random.choice(OFFICE_TOPICS)
    print(f"\n[TOPIC] {topic}")

    # Step 2: Generate or select script
    print("\n[STEP 1] Getting script...")

    # Try existing scripts first
    script_content = generate_script_from_existing(topic)

    # If no existing script, try AI generation
    if not script_content:
        if os.environ.get("OPENAI_API_KEY"):
            script_content = generate_script_with_ai(topic)
        else:
            print("  No OPENAI_API_KEY set, using template")
            script_content = generate_template_script(topic)

    # Save script
    os.makedirs(EPISODES_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = os.path.join(EPISODES_DIR, f"script_{timestamp}.txt")
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    print(f"  Script saved: {script_path}")

    # Step 3: Run video pipeline
    print("\n[STEP 2] Running video pipeline...")
    pipeline_result = run_pipeline(script_path, topic)

    if not pipeline_result:
        print("\nPIPELINE FAILED")
        return None

    # Step 4: Upload to YouTube
    print("\n[STEP 3] Uploading to YouTube...")
    upload_result = None

    if os.path.exists("youtube_token.pickle"):
        upload_result = upload_episode(
            video_path=pipeline_result["final_video"],
            episode_title=topic,
            thumbnail_path=pipeline_result.get("thumbnail"),
            publish=publish,
        )
    else:
        print("  No YouTube token found, skipping upload")
        print("  Run: python authenticate_youtube.py")

    # Step 5: Mark as processed
    episode_key = f"episode_{timestamp}"
    metadata = {
        "topic": topic,
        "script": script_path,
        "video": pipeline_result.get("final_video"),
        "thumbnail": pipeline_result.get("thumbnail"),
        "upload": upload_result,
    }
    mark_processed(episode_key, metadata)

    # Save full run record
    run_record = os.path.join(pipeline_result["output_dir"], "run_record.json")
    with open(run_record, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)

    print("\n" + "=" * 70)
    print("AUTOMATION COMPLETE!")
    print("=" * 70)
    print(f"\nScript: {script_path}")
    print(f"Video: {pipeline_result.get('final_video')}")
    print(f"Thumbnail: {pipeline_result.get('thumbnail')}")
    if upload_result:
        print(f"YouTube: {upload_result['url']}")

    return metadata


# ============================================================
# BATCH AUTOMATION
# ============================================================

def run_batch(count=5, publish=False):
    """Run automation multiple times."""
    print(f"\nRunning batch of {count} episodes...")

    results = []
    for i in range(count):
        print(f"\n{'='*50}")
        print(f"EPISODE {i+1} OF {count}")
        print(f"{'='*50}")

        result = run_full_automation(publish=publish)
        results.append(result)

    # Save batch summary
    summary_path = os.path.join(OUTPUT_DIR, f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nBatch complete! Summary: {summary_path}")
    return results


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cat Podcast Master Automation")
    parser.add_argument("--topic", type=str, help="Specific topic (optional)")
    parser.add_argument("--batch", type=int, help="Number of episodes to generate")
    parser.add_argument("--publish", action="store_true", help="Publish to YouTube (default: private)")

    args = parser.parse_args()

    if args.batch:
        run_batch(args.batch, args.publish)
    else:
        run_full_automation(args.topic, args.publish)