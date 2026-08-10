# n8n Setup Guide - Cat Podcast Automation

## Quick Start (5 minutes)

### Step 1: Install n8n
```bash
npm install n8n -g
```

### Step 2: Start n8n
```bash
n8n start
```
Open: http://localhost:5678

### Step 3: Import Workflow
1. Click the **+** button
2. Select **Import from File**
3. Choose `n8n_workflow.json` from this folder
4. Click **Import**

### Step 4: Set Up Environment Variables
In n8n, go to **Settings** → **Variables** and add:

| Variable | Value |
|----------|-------|
| `COLAB_WEBHOOK_URL` | Your Colab ngrok URL (e.g., `https://xxxx.ngrok.io/generate`) |
| `KAGGLE_WEBHOOK_URL` | Your Kaggle ngrok URL |

### Step 5: Activate the Workflow
Click the **Active** toggle in the top-right corner.

---

## How It Works

```
Schedule (Mon/Wed/Fri 10AM)
    ↓
Run generate_episode.py
    ↓
Check Result
    ↓
Log Success or Failure
```

The workflow:
1. **Triggers** every Monday, Wednesday, Friday at 10:00 AM
2. **Runs** `generate_episode.py` which:
   - Picks the next unprocessed script (episodes 1-10)
   - Sends script to Colab/Kaggle for VibeVoice audio
   - Creates video with FFmpeg (Ken Burns effect)
   - Uploads to YouTube as PUBLIC
3. **Logs** the result (success/failure)

---

## Manual Trigger

You can also trigger manually:
1. Open the workflow in n8n
2. Click **Test Workflow**
3. Or send a POST request to: `http://localhost:5678/webhook/generate-episode`

---

## Updating the Webhook URL

When Colab/Kaggle restarts, the ngrok URL changes. To update:

1. Start Colab/Kaggle notebook
2. Copy the new ngrok URL from output
3. In n8n: Settings → Variables → Update `COLAB_WEBHOOK_URL`
4. Or set it in `run_episode.bat`

---

## Without n8n (Alternative)

If you don't want n8n, use Windows Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Weekly → Mon, Wed, Fri at 10:00 AM
4. Action: Start Program
   - Program: `C:\Users\Imtiyaz\Documents\New OpenCode Project\automation\run_episode.bat`

---

## Troubleshooting

**"No webhook URL set"**
- Colab/Kaggle notebook isn't running
- Start the notebook and copy the ngrok URL

**"YouTube token expired"**
- Run: `python authenticate_youtube.py`

**"FFmpeg not found"**
- Reinstall: `winget install Gyan.FFmpeg`

**"Script not found"**
- Check `scripts/` folder has episode_*.txt files
