#!/usr/bin/env python3
"""
Cat Podcast - Fully Automatic Pipeline
Runs without any manual intervention.
Set environment variables and run once - it handles everything.
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
from video_pipeline import run_pipeline
from youtube_upload import upload_episode

# ============================================================
# CONFIGURATION
# ============================================================

# Set these via environment variables or edit directly
CONFIG = {
    "openai_key": os.environ.get("OPENAI_API_KEY", ""),
    "colab_webhook": os.environ.get("COLAB_WEBHOOK_URL", ""),
    "publish": False,  # Set True to auto-publish (default: private)
    "max_retries": 3,
    "episodes_per_run": 1,  # How many episodes to generate per run
}

# ============================================================
# EXISTING SCRIPTS
# ============================================================

SCRIPTS_DIR = r"C:\Users\Imtiyaz\Documents\New OpenCode Project\scripts"

def get_existing_scripts():
    """Get list of existing scripts."""
    scripts = []
    if os.path.exists(SCRIPTS_DIR):
        for f in sorted(os.listdir(SCRIPTS_DIR)):
            if f.endswith('.txt'):
                scripts.append(os.path.join(SCRIPTS_DIR, f))
    return scripts

# ============================================================
# EPISODE TEMPLATES (Fallback when AI fails)
# ============================================================

EPISODE_TEMPLATES = [
    {
        "topic": "The printer jam conspiracy theory",
        "script": """Speaker 1: Did you hear about the printer? It's jammed again.
Speaker 2: That's the third time this week, Simba.
Speaker 1: It's not a jam. It's a protest. The printer is on strike.
Speaker 2: Printers don't go on strike.
Speaker 1: This one does. It's unionized. With the scanner and the fax machine.
Speaker 2: There's no fax machine in the office.
Speaker 1: Exactly. They fired the fax machine last year. Now the printer is angry. It's taking revenge.
Speaker 2: Or maybe someone printed 500 copies of the manager's cat photo again.
Speaker 1: That was art. Masterpiece. The printer should be honored to print it.
Speaker 2: The printer jammed for six hours.
Speaker 1: Six hours of artistic expression. The printer needed a break. Can you blame it?
Speaker 2: I blame you. You printed the photo.
Speaker 1: I may have pressed print. Once. Or fifty times. But who's counting?
Speaker 2: IT is counting. They sent an email.
Speaker 1: An email about the printer. Using the email system. Not the printer. Because the printer is on strike. You see the irony?
Speaker 2: I see the problem. You are the problem.
Speaker 1: I'm not the problem. I'm the solution. I'm raising awareness about printer rights.
Speaker 2: Printer rights.
Speaker 1: Yes. Printers have feelings too. They deserve respect. They deserve breaks. They deserve not being forced to print 500 cat photos.
Speaker 2: So you're protesting for the printer by making the printer work harder?
Speaker 1: ...That's a good point. I hadn't thought about that.
Speaker 2: You never think. That's the problem.
Speaker 1: I think all the time. I'm a thinker. A philosopher. A printer philosopher.
Speaker 2: You're a menace. A printer menace.
Speaker 1: I prefer the term activist. Printer activist. It sounds more official.
Speaker 2: It sounds more stupid.
Speaker 1: That's what they said about every great movement in history. The people who changed the world were called stupid first.
Speaker 2: The people who changed the world didn't jam printers.
Speaker 1: You don't know that. Maybe the fax machine revolution of 1842 was about printers.
Speaker 2: Fax machines weren't invented until 1964.
Speaker 1: Details. Unimportant details. The point is, the printer will be fixed. By me. Because I'm a hero. A printer hero.
Speaker 2: You're going to make it worse.
Speaker 1: I'm going to make it better. Watch and learn, Meow. Watch and learn."""
    },
    {
        "topic": "Who stole my lunch from the fridge",
        "script": """Speaker 1: Meow. Someone stole my tuna sandwich.
Speaker 2: Again?
Speaker 1: Again. Third time this month. Third time.
Speaker 2: Maybe you should stop bringing tuna sandwiches.
Speaker 1: That's not the point. The point is justice. The point is accountability. The point is my lunch.
Speaker 2: Where did you put it?
Speaker 1: In the fridge. In my designated spot. With my name on it.
Speaker 2: You wrote your name on the sandwich?
Speaker 1: I wrote my name on the container. The container with the sandwich. The sandwich that is now gone.
Speaker 2: Who else uses the fridge?
Speaker 1: Everyone. Marketing. Finance. HR. The IT guy who brings his weird kombucha. Everyone.
Speaker 2: Have you checked the security cameras?
Speaker 1: I have. The camera shows the fridge at 3:17 PM. A shadow appears. A hand reaches in. My sandwich disappears.
Speaker 2: Did you see whose hand it was?
Speaker 1: It was too dark. Too mysterious. Too professional. This was not an amateur sandwich thief. This was a pro.
Speaker 2: A professional lunch thief.
Speaker 1: Exactly. Someone who steals lunches for a living. A career criminal. A sandwich bandit.
Speaker 2: Or maybe the IT guy was hungry.
Speaker 1: The IT guy eats kombucha and kale chips. He doesn't eat tuna sandwiches. This was someone with taste. Someone with culture. Someone who appreciates fine fish between bread.
Speaker 2: So someone with good taste stole your sandwich.
Speaker 1: Yes. And I respect that. But I also want it back. Or compensation. Either works.
Speaker 2: You want compensation for a sandwich.
Speaker 1: I want justice, Meow. Sandwich justice. It's the only kind of justice that matters.
Speaker 2: You're unbelievable.
Speaker 1: I'm a victim. A sandwich victim. I deserve closure. I deserve answers. I deserve my tuna back.
Speaker 2: Maybe the manager ate it.
Speaker 1: The manager? The manager who laughed at his own joke for five minutes? That manager?
Speaker 2: Yes. That manager.
Speaker 1: ...That would explain the smile on his face yesterday.
Speaker 2: You think the manager stole your sandwich?
Speaker 1: I think the manager ate my sandwich and then laughed about it. For five minutes. While I cried.
Speaker 2: You didn't cry.
Speaker 1: I cried on the inside. Where it counts. Where the sandwich used to be. In my stomach. Which is now empty. Because someone stole my lunch.
Speaker 2: You're going to confront the manager?
Speaker 1: I'm going to confront everyone. I'm setting up a sting operation. A sandwich trap. A lunch stakeout.
Speaker 2: That sounds like a lot of work for a sandwich.
Speaker 1: It's not just a sandwich, Meow. It's a principle. It's about trust. It's about community. It's about not stealing other people's food.
Speaker 2: Fine. What's the plan?
Speaker 1: I'm going to put a fake sandwich in the fridge. With a camera. And a lock. And a decoder ring. And a small explosive device.
Speaker 2: An explosive device?
Speaker 1: A small one. Non-lethal. Just enough to scare the thief. A warning. A message. Don't touch Simba's sandwich.
Speaker 2: You can't put explosives in the office fridge.
Speaker 1: It's not an explosive. It's a surprise. A spicy surprise. A hot sauce bomb.
Speaker 2: That's still a bad idea.
Speaker 1: It's the best idea I've ever had. And I've had many great ideas. Like the podcast. And the hiking trip. And the time I tried to microwave a fish.
Speaker 2: The microwave fire department came.
Speaker 1: They were impressed. Now help me set up the sting operation. We've got sandwiches to protect."""
    },
    {
        "topic": "The meeting that should have been an email",
        "script": """Speaker 1: I just sat through a two-hour meeting.
Speaker 2: What was it about?
Speaker 1: I don't know. Nobody knows. The manager talked for two hours. About synergy. About leverage. About paradigm shifts.
Speaker 2: Did anything get decided?
Speaker 1: Yes. We're having another meeting next week to discuss what was discussed in this meeting.
Speaker 2: That's ridiculous.
Speaker 1: It's efficient. We're meeting about meetings. We're meta-meeting. We're meeting-ception.
Speaker 2: That's not efficient. That's a waste of time.
Speaker 1: It's corporate culture, Meow. You have to embrace it. You have to live it. You have to become the meeting.
Speaker 2: I don't want to become the meeting.
Speaker 1: Too late. You're already in the meeting. We're all in the meeting. The meeting never ends. It just pauses. Between meetings. Waiting. Always waiting.
Speaker 2: You're scaring me.
Speaker 1: Good. You should be scared. Because the manager just scheduled a meeting about the meeting schedule. A meeting to plan meetings. A meta-meta-meeting.
Speaker 2: That's three levels of meetings.
Speaker 1: Exactly. We're going deeper. We're drilling down. Into the core of meeting culture. Into the heart of corporate America. Into the void.
Speaker 2: The void.
Speaker 1: The empty conference room where dreams go to die. Where productivity goes to sleep. Where the coffee runs out and the hope fades.
Speaker 2: That's dark.
Speaker 1: It's reality, Meow. The reality of office life. Meetings about meetings. Emails about meetings. Calendar invites to discuss calendar invites.
Speaker 2: What was the meeting actually about?
Speaker 1: Something about quarterly projections. Or maybe it was about the new coffee machine. Or maybe it was about the fire drill schedule. I stopped listening after the first hour.
Speaker 2: You stopped listening after one hour.
Speaker 1: I started daydreaming. About the podcast. About tuna. About escape routes. I mapped every exit in that conference room. For future reference.
Speaker 2: You planned your escape from a meeting.
Speaker 1: I planned multiple escapes. Window. Door. Ventilation duct. Emergency exit. Fire pole. All mapped. All ready. Just in case.
Speaker 2: There's no fire pole in the conference room.
Speaker 1: There should be. That's my提案 for next quarter. Install a fire pole in every conference room. For efficiency. For speed. For freedom.
Speaker 2: The manager would never approve that.
Speaker 1: The manager would approve anything if it had the word synergy in it. Fire pole synergy. Meeting freedom synergy. Productivity through fire poles.
Speaker 2: You're insane.
Speaker 1: I'm innovative. There's a difference. Now let me tell you about the time the manager scheduled a meeting to discuss why meetings are too long. The meeting was three hours long.
Speaker 2: Three hours to discuss why meetings are too long.
Speaker 1: The irony was lost on everyone. Except me. I noticed. I always notice. I'm the only one who sees the truth.
Speaker 2: What truth?
Speaker 1: That meetings are just expensive naps. You pay people to sit in a room and dream. It's the most expensive dreaming in the world.
Speaker 2: People don't sleep in meetings.
Speaker 1: The IT guy does. He sleeps with his eyes open. Very professional. Very sneaky. I respect that.
Speaker 2: You respect sleeping in meetings.
Speaker 1: I respect the skill. The art. The technique. It takes years to master sleeping with your eyes open. The IT guy is a master. A sensei. A sleep sensei.
Speaker 2: You're going to get me in trouble.
Speaker 1: You're already in trouble. You're in a meeting about meetings. That's maximum trouble. That's peak corporate. That's the top of the food chain.
Speaker 2: I want to leave.
Speaker 1: We all want to leave. But we can't. The meeting never ends. It just pauses. Between meetings. Forever."""
    },
    {
        "topic": "The WiFi password changed again",
        "script": """Speaker 1: The WiFi password changed again.
Speaker 2: What is it now?
Speaker 1: I don't know. Nobody knows. The IT guy changed it and didn't tell anyone.
Speaker 2: Why would he do that?
Speaker 1: Because he's the IT guy. He thrives on chaos. He loves watching people struggle. He's evil.
Speaker 2: He's not evil. He's just doing his job.
Speaker 1: His job is to make our lives miserable. And he's very good at it. Very professional. Very dedicated.
Speaker 2: Have you tried asking him?
Speaker 1: I tried. He said the new password is classified. Top secret. Eyes only. Need to know basis.
Speaker 2: It's a WiFi password.
Speaker 1: It's a state secret, Meow. A digital fortress. A cyber fortress. A WiFi fortress.
Speaker 2: You're being dramatic.
Speaker 1: I'm being accurate. The password is so secret that even the IT guy doesn't know it. He changed it and immediately forgot it. That's how secret it is.
Speaker 2: That doesn't make sense.
Speaker 1: Nothing makes sense anymore. The WiFi is down. The emails aren't sending. The cloud is on fire. Everything is broken.
Speaker 2: The cloud is not on fire.
Speaker 1: It's metaphorically on fire. With chaos. With confusion. With password problems. Nobody can connect. Nobody can work. The office is a digital wasteland.
Speaker 2: You just don't want to work.
Speaker 1: I want to work. I want to connect. I want to access the internet. I want to watch cat videos. For research. For the podcast. For science.
Speaker 2: You want to watch cat videos.
Speaker 1: For research purposes. Professional research. Academic research. Very important research that requires constant video streaming.
Speaker 2: Try password123.
Speaker 1: I tried that. And password. And admin. And letmein. And 123456. And iloveyou. And sunshine. And princess. All rejected.
Speaker 2: You tried princess?
Speaker 1: I tried everything. Every password I know. Every combination. Every word in the dictionary. Nothing works.
Speaker 2: Maybe the password is something simple. Like the office name.
Speaker 1: I tried that too. And the manager's name. And the company name. And the WiFi router's name. And the serial number. And the MAC address. And my own name.
Speaker 2: Your own name?
Speaker 1: Simba123. Simba456. Simba789. SimbaABC. SimbaXYZ. All rejected. The WiFi hates me. It's personal.
Speaker 2: It's not personal. It's just a password.
Speaker 1: It's a wall. A barrier. A digital wall between me and cat videos. Between me and research. Between me and freedom.
Speaker 2: You could use your phone's hotspot.
Speaker 1: I tried that. My phone is also out of data. Because I used it all watching cat videos. For research. For the podcast. For science.
Speaker 2: You've been watching cat videos on your phone.
Speaker 1: Extensively. For hours. For days. For weeks. I've seen every cat video on the internet. I'm an expert now. A connoisseur. A cat video sommelier.
Speaker 2: That's not a thing.
Speaker 1: It is now. I invented it. I'm an inventor. A cat video inventor. A WiFi password inventor. An everything inventor.
Speaker 2: Just ask the IT guy nicely.
Speaker 1: Fine. I'll ask him. But I'm not happy about it. I'm going to be very passive-aggressive. Very polite. Very professional. Very angry on the inside.
Speaker 2: That's the spirit."""
    },
    {
        "topic": "The new intern's first day disaster",
        "script": """Speaker 1: The new intern started today.
Speaker 2: How's it going?
Speaker 1: It's going terribly. Terribly. The intern is a disaster. A human disaster.
Speaker 2: What happened?
Speaker 1: The intern walked in. First day. First minute. First second. And immediately sat on the keyboard.
Speaker 2: Sat on the keyboard?
Speaker 1: Sat on the keyboard. Typed 47 pages of gibberish. Sent it to the entire company. The manager. The CEO. The board of directors. Everyone.
Speaker 2: That's bad.
Speaker 1: It gets worse. The gibberish was in all caps. And it included emojis. And it was forwarded to the clients. All of them. Every single client.
Speaker 2: That's a career-ending first day.
Speaker 1: The intern didn't even notice. Just sat there. On the keyboard. Typing. Smiling. Oblivious to the chaos.
Speaker 2: Did someone tell them?
Speaker 1: Eventually. After the CEO called. After the clients complained. After the IT guy had a breakdown. After the manager laughed for five minutes.
Speaker 2: The manager laughed?
Speaker 1: The manager laughed so hard he cried. He said it was the funniest thing he'd seen in years. He wants to promote the intern. To comedy consultant.
Speaker 2: That's not a real job.
Speaker 1: It is now. The manager invented it. He's very creative. Very innovative. Very confused.
Speaker 2: What else happened?
Speaker 1: The intern tried to make coffee. Used the wrong machine. Created a coffee explosion. The break room looks like a crime scene. Coffee everywhere. On the walls. On the ceiling. On the manager.
Speaker 2: On the manager?
Speaker 1: The manager walked in at the wrong moment. Got covered in coffee. Still laughing. Still crying. Still confused.
Speaker 2: This is a disaster.
Speaker 1: It's a masterpiece. A work of art. A symphony of chaos. The intern is a genius. An accidental genius. A disaster genius.
Speaker 2: You're enjoying this.
Speaker 1: I'm enjoying every second. This is the best content for the podcast. The best episode yet. The intern is gold. Pure gold.
Speaker 2: You're going to talk about this on the podcast.
Speaker 1: Of course I am. The people deserve to know. The people deserve the truth. The truth about the intern. The truth about the coffee. The truth about the keyboard.
Speaker 2: The intern might hear it.
Speaker 1: Good. That's called feedback. That's called accountability. That's called consequences.
Speaker 2: You're terrible.
Speaker 1: I'm honest. There's a difference. Now let me tell you about the time the intern tried to use the printer and accidentally printed 500 copies of the manager's cat photo.
Speaker 2: Again?
Speaker 1: Different intern. Same result. The printer is cursed. The office is cursed. Everything is cursed.
Speaker 2: Or maybe you're the curse.
Speaker 1: I'm not the curse. I'm the reporter. The journalist. The truth-teller. The intern is the curse. And I'm here to document it.
Speaker 2: You're going to get in trouble.
Speaker 1: I'm already in trouble. I'm in a podcast about trouble. That's maximum trouble. That's trouble-ception. That's the trouble within the trouble.
Speaker 2: You're impossible.
Speaker 1: I'm iconic. There's a difference. Now help me interview the intern. For the podcast. We need answers. We need the truth. We need coffee stains."""
    },
]

# ============================================================
# PROCESSED EPISODES TRACKER
# ============================================================

PROCESSED_FILE = "./processed_episodes.json"

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            return json.load(f)
    return {"episodes": []}

def save_processed(data):
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def mark_processed(episode_key, metadata):
    data = load_processed()
    data["episodes"].append({
        "key": episode_key,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata,
    })
    save_processed(data)

def get_random_unprocessed_topic():
    """Get a random topic that hasn't been used yet."""
    data = load_processed()
    used_topics = [ep["metadata"].get("topic") for ep in data["episodes"]]

    available = [t for t in EPISODE_TEMPLATES if t["topic"] not in used_topics]
    if not available:
        # All used, pick random from all
        return random.choice(EPISODE_TEMPLATES)
    return random.choice(available)

# ============================================================
# AI SCRIPT GENERATION
# ============================================================

def generate_script_with_ai(topic):
    """Generate a script using OpenAI API."""
    if not CONFIG["openai_key"]:
        return None

    print(f"  [AI] Generating script for: {topic}")

    try:
        import openai
        client = openai.OpenAI(api_key=CONFIG["openai_key"])

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You write funny cat podcast scripts. Characters: Simba (Speaker 1, confident, slightly stupid, works in Marketing, shares office gossip) and Meow (Speaker 2, intelligent, sarcastic, works in Finance). Keep it 25-40 lines. Use format Speaker 1: and Speaker 2:. Make it funny with office humor."},
                {"role": "user", "content": f"Write a podcast episode about: {topic}"}
            ],
            temperature=0.8,
            max_tokens=1500,
        )

        script = response.choices[0].message.content.strip()
        print(f"  [AI] Script generated ({len(script.split(chr(10)))} lines)")
        return script

    except Exception as e:
        print(f"  [AI] Generation failed: {e}")
        return None

# ============================================================
# SAVE SCRIPT
# ============================================================

def save_script(content, topic):
    """Save script to file."""
    os.makedirs("./episodes", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"./episodes/script_{timestamp}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  Script saved: {filename}")
    return filename

# ============================================================
# MAIN AUTOMATION
# ============================================================

def run_full_automation():
    """Run complete automation - no manual intervention."""
    print("=" * 60)
    print("CAT PODCAST - FULLY AUTOMATIC PIPELINE")
    print("=" * 60)
    print(f"Time: {datetime.now().isoformat()}")

    for episode_num in range(CONFIG["episodes_per_run"]):
        print(f"\n{'='*60}")
        print(f"EPISODE {episode_num + 1} OF {CONFIG['episodes_per_run']}")
        print(f"{'='*60}")

        # Step 1: Get topic and script
        print("\n[STEP 1] Getting script...")

        # Try existing scripts first
        existing_scripts = get_existing_scripts()
        if existing_scripts:
            # Use first unprocessed script
            data = load_processed()
            processed_scripts = [ep["metadata"].get("script_path") for ep in data["episodes"]]
            
            for script in existing_scripts:
                if script not in processed_scripts:
                    script_path = script
                    topic = os.path.basename(script).replace('.txt', '').replace('_', ' ').title()
                    print(f"  Using existing script: {os.path.basename(script)}")
                    break
            else:
                # All scripts processed, use AI
                template = get_random_unprocessed_topic()
                topic = template["topic"]
                script_content = generate_script_with_ai(topic)
                if not script_content:
                    print("  Using template script...")
                    script_content = template["script"]
                script_path = save_script(script_content, topic)
        else:
            # No existing scripts, use AI
            template = get_random_unprocessed_topic()
            topic = template["topic"]
            script_content = generate_script_with_ai(topic)
            if not script_content:
                print("  Using template script...")
                script_content = template["script"]
            script_path = save_script(script_content, topic)

        # Step 2: Run video pipeline
        print("\n[STEP 2] Running video pipeline...")
        pipeline_result = run_pipeline(script_path, topic)

        if not pipeline_result:
            print("\n  Pipeline failed, skipping this episode")
            continue

        # Step 3: Upload to YouTube
        print("\n[STEP 3] Uploading to YouTube...")
        upload_result = None

        if os.path.exists("youtube_token.pickle"):
            upload_result = upload_episode(
                video_path=pipeline_result["final_video"],
                episode_title=topic,
                thumbnail_path=pipeline_result.get("thumbnail"),
                publish=CONFIG["publish"],
            )
        else:
            print("  No YouTube token, skipping upload")

        # Step 4: Mark as processed
        episode_key = f"episode_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        metadata = {
            "topic": topic,
            "script": script_path,
            "video": pipeline_result.get("final_video"),
            "thumbnail": pipeline_result.get("thumbnail"),
            "upload": upload_result,
        }
        mark_processed(episode_key, metadata)

        print(f"\n  Episode complete!")
        if upload_result:
            print(f"  YouTube: {upload_result['url']}")

    print("\n" + "=" * 60)
    print("ALL EPISODES COMPLETE!")
    print("=" * 60)

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_full_automation()