# Zoom Transcription Quick Start

**Goal:** Automatically transcribe everything everyone says in your Zoom meetings.

## TL;DR

```bash
# Run the setup script (one time)
cd /Users/misterg/projects/misterg-sidekick/miclog
./setup-zoom-transcription.sh

# Before each meeting
zoom-transcribe.sh

# Join Zoom meeting (audio works normally)

# After meeting: Press Ctrl+C
```

Transcripts saved to: `~/Documents/Zoom Transcripts/`

---

## Why This is Needed

**The Problem:**
- Miclog records from your **microphone** (captures your voice ✓)
- Zoom audio comes through **speakers** (miclog can't hear this ✗)

**The Solution:**
- Install **BlackHole** (audio loopback)
- Route Zoom audio → BlackHole → miclog
- Result: Transcribes both you AND others ✓

---

## One-Time Setup (15 minutes)

### Step 1: Run Setup Script

```bash
cd /Users/misterg/projects/misterg-sidekick/miclog
./setup-zoom-transcription.sh
```

This will:
1. Install BlackHole (requires Mac restart)
2. Guide you through audio device configuration
3. Create helper scripts for easy use

### Step 2: Configure Audio Devices

The script will open **Audio MIDI Setup** and guide you to create:

**Multi-Output Device:** "Zoom Output + BlackHole"
- ☑ Your speakers (so you hear audio)
- ☑ BlackHole 2ch (so miclog captures it)

**Aggregate Device:** "Mic + Zoom Audio"
- ☑ Your microphone (captures your voice)
- ☑ BlackHole 2ch (captures Zoom audio)

### Step 3: Test It

```bash
zoom-transcribe-test.sh
```

Speak into your mic for 10 seconds. You should see transcription appear.

---

## Daily Usage

### Manual Mode (Recommended to Start)

**Before each Zoom meeting:**

1. **Set Zoom output:**
   ```
   Zoom → Settings → Audio
   Output: "Zoom Output + BlackHole"
   ```

2. **Start transcription:**
   ```bash
   zoom-transcribe.sh
   ```

   Or with custom filename:
   ```bash
   zoom-transcribe.sh ~/meetings/standup.txt
   ```

3. **Join Zoom meeting** - audio works normally

4. **After meeting:** Press `Ctrl+C`

**Your transcript is saved!** Default location: `~/Documents/Zoom Transcripts/`

---

## Automatic Mode (Advanced)

Want transcription to start automatically when Zoom meetings begin?

See the full guide: [ZOOM_INTEGRATION.md](ZOOM_INTEGRATION.md#option-2-automatic-transcription-advanced)

---

## What You'll Get

Transcript format:
```
[2026-04-29 14:30:15] Okay everyone, let's get started with the standup.
[2026-04-29 14:30:22] Alice, can you go first?
[2026-04-29 14:30:28] Sure, I finished the authentication refactor.
[2026-04-29 14:30:35] Great work. Bob, you're next.
```

Each line = 5 seconds of audio with timestamp.

---

## Common Issues

**Can't hear Zoom audio anymore?**
- You forgot to include your speakers in the Multi-Output Device
- Or Zoom output isn't set to "Zoom Output + BlackHole"

**Transcription only has your voice?**
- Zoom output must be set to "Zoom Output + BlackHole"
- Check: Zoom → Settings → Audio → Output

**Transcription is empty?**
- Wrong device ID in the script
- Run: `python -m sidekick.clients.miclog list-devices`
- Look for "Mic + Zoom Audio" and note its ID

**Audio is delayed?**
- Normal! There's a 5-10 second processing delay
- Real-time transcription, not instant

---

## Alternative: Use Zoom's Built-in Transcripts

If audio routing is too complex, you can use Zoom's built-in transcription:

**Enable in Zoom:**
```
Zoom → Settings → Recording
☑ Cloud recording
☑ Audio transcript
```

**Fetch transcripts after meetings:**
```bash
# List recent meetings
python -m sidekick.clients.zoom list-meetings --from 2026-04-29

# Get transcript
python -m sidekick.clients.zoom get-transcript <meeting-id>
```

**Pros of Zoom method:**
- No audio routing setup
- High accuracy
- Automatic

**Cons of Zoom method:**
- Requires cloud recording (must be meeting host)
- Only available after meeting ends
- Transcripts auto-delete after 30 days

**Recommendation:** Use both!
- Miclog for real-time, always-on transcription
- Zoom built-in for backup/verification

---

## Scripts Created by Setup

After running setup, you'll have:

| Script | Purpose |
|--------|---------|
| `zoom-transcribe.sh` | Start transcription manually |
| `zoom-transcribe-test.sh` | Test setup (10 second recording) |

Located in: `~/bin/` (already in your PATH)

---

## Privacy Note

⚠️ **Always inform meeting participants** that you're recording/transcribing.

Many jurisdictions require consent for recording. Say:
> "I'm transcribing this meeting for my own notes. Is everyone okay with that?"

---

## Need Help?

**Full documentation:**
- [ZOOM_INTEGRATION.md](ZOOM_INTEGRATION.md) - Complete guide with automatic mode
- [QUICKSTART.md](QUICKSTART.md) - General miclog usage
- [DEVICE_SELECTION.md](DEVICE_SELECTION.md) - Microphone selection

**Test your setup:**
```bash
zoom-transcribe-test.sh
```

**Check your devices:**
```bash
python -m sidekick.clients.miclog list-devices
```

**Check BlackHole installation:**
```bash
brew list blackhole-2ch
```
