# n8n Step-by-Step Guide (Build It Yourself)

## What is n8n?

n8n is a workflow automation tool. Think of it like a visual programming tool where you connect blocks (nodes) to create automated pipelines.

**n8n = connecting things together automatically**

Example: When X happens → do Y → then do Z

---

## Part 1: Install n8n

### Option A: Docker (Recommended)

```bash
# Install Docker first (if not installed)
# Then run n8n:
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

### Option B: npm (Node.js)

```bash
# Install Node.js first from https://nodejs.org
# Then:
npm install n8n -g

# Start n8n:
n8n start
```

### Option C: Desktop App

- Download from https://n8n.io/download
- Install like any regular app
- Easiest option for beginners

### Access n8n

Open browser: http://localhost:5678

---

## Part 2: Understand n8n Concepts

### Nodes
- Each block in a workflow is a "node"
- Each node does one thing
- Examples: Read RSS, Call API, Send Email

### Connections
- Lines connecting nodes
- Data flows from one node to the next
- Output of node A = Input of node B

### Workflows
- A complete pipeline
- Multiple nodes connected
- Starts with a trigger

### Trigger
- The starting point
- What kicks off the workflow
- Examples: Schedule (cron), Webhook, Manual button

---

## Part 3: Your First Workflow (Manual Test)

### Step 1: Create New Workflow

1. Open n8n (http://localhost:5678)
2. Click "New Workflow"
3. Name it "Cat Podcast Test"

### Step 2: Add Manual Trigger

1. Click "+" button
2. Search for "Manual Trigger"
3. Click to add it
4. This is your starting point

### Step 3: Add HTTP Request Node

1. Click "+" after the trigger
2. Search for "HTTP Request"
3. Click to add
4. Configure:
   - Method: GET
   - URL: https://api.github.com/repos/microsoft/VibeVoice
5. Click "Test step"

You should see GitHub API response data.

### Step 4: Add Code Node

1. Click "+" after HTTP Request
2. Search for "Code"
3. Click to add
4. Enter this code:

```javascript
const data = $input.first().json;
return [{
  json: {
    name: data.name,
    stars: data.stargazers_count,
    description: data.description
  }
}];
```

5. Click "Test step"

You should see extracted data: name, stars, description.

### Step 5: Add Set Node

1. Click "+" after Code
2. Search for "Set"
3. Click to add
4. Configure:
   - Values to Set:
     - Field: `message`
     - Value: `={{ "VibeVoice has " + $json.stars + " stars!" }}`
5. Click "Test step"

### Step 6: Execute

1. Click "Test workflow" button (top right)
2. Watch data flow through each node
3. See the final output

**Congratulations! You just built your first n8n workflow!**

---

## Part 4: Cat Podcast Automation Workflow

Now build the real workflow. This will:
1. Run on a schedule
2. Pick a topic from a list
3. Generate a script using AI
4. Save the script to a file

### Step 1: Schedule Trigger

1. Add node: "Schedule Trigger"
2. Configure:
   - Rule: Every day at 9 AM
   - Or: Every 6 hours (for testing)

### Step 2: Code Node (Topic Picker)

1. Add node: "Code"
2. Paste this code:

```javascript
const topics = [
  "Why the manager's coffee is always cold",
  "The printer jam conspiracy",
  "Who stole my tuna from the fridge",
  "The meeting that should have been an email",
  "The new intern's first day disaster",
  "The WiFi password mystery",
  "The air conditioning war between departments",
  "The broken elevator and the stairwell drama",
  "The mysterious sticky note on the desk",
  "The lunch theft investigation"
];

const randomTopic = topics[Math.floor(Math.random() * topics.length)];

return [{
  json: {
    topic: randomTopic,
    timestamp: new Date().toISOString()
  }
}];
```

3. Test it - you should get a random topic each time

### Step 3: AI Script Generation (OpenAI)

1. Add node: "OpenAI"
2. You'll need an OpenAI API key
   - Go to https://platform.openai.com
   - Create account
   - Get API key
3. Configure OpenAI node:
   - Operation: Chat
   - Model: gpt-4
   - Messages:
     - Role: System
     - Content: "You write funny cat podcast scripts. Characters: Simba (confident, slightly stupid, works in marketing) and Meow (sarcastic, intelligent, works in finance). They work in the same office but different departments. Simba shares office gossip. Keep it 20-30 lines. Use format: Speaker 1: and Speaker 2:"
     - Role: User
     - Content: "Write a podcast episode about: {{ $json.topic }}"

### Step 4: Code Node (Format Script)

1. Add node: "Code"
2. Paste this code:

```javascript
const response = $input.first().json;
const script = response.choices[0].message.content;

// Save to file (n8n will handle this)
return [{
  json: {
    script: script,
    topic: $('Topic Picker').first().json.topic,
    timestamp: new Date().toISOString(),
    filename: `episode_${Date.now()}.txt`
  }
}];
```

### Step 5: Write to File

1. Add node: "Write Binary File"
2. Configure:
   - File Name: `={{ $json.filename }}`
   - Data: `={{ $json.script }}`
   - File Path: `/path/to/your/scripts/` (change this)

### Step 6: Execute and Test

1. Click "Test workflow"
2. Watch it:
   - Pick a random topic
   - Generate a script
   - Save to file
3. Check the file - you should see a complete script!

---

## Part 5: Add VibeVoice Audio Generation

This part connects to Colab for audio generation.

### Step 1: Webhook Trigger

1. Add node: "Webhook"
2. Configure:
   - Method: POST
   - Path: /generate-audio
3. This creates a URL like: http://localhost:5678/webhook/generate-audio

### Step 2: HTTP Request to Colab

1. Add node: "HTTP Request"
2. Configure:
   - Method: POST
   - URL: Your Colab webhook URL (you'll set this up)
   - Body: JSON
   - Body Parameters:
     - script: `={{ $json.script }}`

### How to Get Colab Webhook URL:

In Colab:
```python
# Install pyngrok for tunneling
!pip install pyngrok

# Create webhook
from flask import Flask, request
from pyngrok import ngrok

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    script = data['script']
    # ... generate audio with VibeVoice ...
    return {"status": "success", "file": "output.wav"}

# Create public URL
public_url = ngrok.connect(5000)
print(f"Webhook URL: {public_url}")

app.run(port=5000)
```

### Step 3: Save Audio to Drive

1. Add node: "Google Drive"
2. Configure:
   - Operation: Upload
   - File: `={{ $json.audio_file }}`
   - Folder: CatPodcast

---

## Part 6: Connect Everything

### Complete Workflow:

```
Schedule Trigger (daily)
    |
    v
Topic Picker (Code node)
    |
    v
AI Script Generation (OpenAI)
    |
    v
Format Script (Code node)
    |
    v
Save Script (Write File)
    |
    v
Send to Colab (HTTP Request)
    |
    v
Save Audio (Google Drive)
    |
    v
Send Notification (Email/Slack)
```

---

## Part 7: Test Each Part Separately

### Test 1: Topic Picker
- Run just the Code node
- Verify random topics appear

### Test 2: Script Generation
- Run Topic Picker + OpenAI
- Check script quality

### Test 3: File Writing
- Run through to Write File
- Check file is created

### Test 4: Full Pipeline
- Run everything
- Check audio is generated

---

## Part 8: Common Issues

### Issue: "Cannot find module"
**Fix:** Check node configuration, ensure all fields are filled

### Issue: "Authentication failed"
**Fix:** Re-enter API keys, check they're valid

### Issue: "Timeout"
**Fix:** Increase timeout in HTTP Request node settings

### Issue: "Data not passing between nodes"
**Fix:** Check expressions use `={{ $json.fieldname }}` syntax

---

## Part 9: n8n Tips

### 1. Use Expressions
- `={{ $json.field }}` - access data from previous node
- `={{ $('Node Name').first().json.field }}` - access specific node's data
- `={{ $json.field ? 'yes' : 'no' }}` - conditional logic

### 2. Use Code Nodes for Complex Logic
- JavaScript available
- Can process arrays, objects, strings
- Use for data transformation

### 3. Error Handling
- Add "Error Trigger" node
- Send notifications on failure
- Log errors for debugging

### 4. Save Work Frequently
- Click save often
- Use version history
- Test small changes first

---

## Part 10: Learning Resources

### Official Docs
- https://docs.n8n.io

### YouTube Tutorials
- Search "n8n tutorial for beginners"
- Official n8n YouTube channel

### Community
- https://community.n8n.io
- Ask questions
- Share workflows

### Practice Ideas
1. RSS feed reader workflow
2. Email auto-responder
3. Google Sheets updater
4. Slack notification system
5. File monitoring workflow

---

## Quick Reference

### Node Types You'll Use:
| Node | Purpose |
|------|---------|
| Schedule Trigger | Run on timer |
| Webhook | Receive HTTP requests |
| HTTP Request | Call APIs |
| Code | Write custom logic |
| Set | Set variables |
| OpenAI | AI text generation |
| Write File | Save to disk |
| Google Drive | Cloud storage |
| Email | Send emails |
| Slack | Send messages |

### Expression Syntax:
```
{{ $json.field }}           - Current node data
{{ $input.first().json }}   - First input item
{{ $('Node').first().json }} - Specific node data
{{ $now }}                  - Current timestamp
{{ $json.arr.length }}      - Array length
```

---

## Next Steps After This Guide

1. Install n8n
2. Build Part 3 (test workflow)
3. Build Part 4 (cat podcast workflow)
4. Test each part
5. Connect to Colab
6. Run first automated episode
7. Iterate and improve