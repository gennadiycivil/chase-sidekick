# Using Miclog with Zoom Meetings

Guide for transcribing Zoom meetings to capture everything everyone says (not just what you say).

## The Challenge

Miclog records from your **microphone**, but in a Zoom meeting:
- Your voice goes through your **microphone** (miclog can capture this)
- Others' voices come through your **speakers** (miclog cannot capture this by default)

**Solution:** Use audio loopback to route Zoom's audio output back as an input device that miclog can record.

---

## Option 1: Manual Transcription (Simplest)

Start miclog before each meeting manually.

### Setup Required

Install **BlackHole** (free, open-source audio loopback):

```bash
brew install blackhole-2ch
```

After installation, restart your Mac.

### Configure Audio Routing

You need to create a "Multi-Output Device" and "Aggregate Device" in macOS:

1. **Open Audio MIDI Setup:**
   - Applications → Utilities → Audio MIDI Setup
   - Or: Spotlight → "Audio MIDI Setup"

2. **Create Multi-Output Device:**
   - Click **+** (bottom left) → "Create Multi-Output Device"
   - Check these boxes:
     - ✅ Your current speakers/headphones (e.g., "CalDigit Thunderbolt 3 Audio" or "MacBook Pro Speakers")
     - ✅ BlackHole 2ch
   - Rename to: "Zoom Output + BlackHole"
   - This sends Zoom audio to both your speakers AND BlackHole

3. **Create Aggregate Device:**
   - Click **+** (bottom left) → "Create Aggregate Device"
   - Check these boxes:
     - ✅ Your microphone (e.g., "CalDigit Thunderbolt 3 Audio" or "MacBook Pro Microphone")
     - ✅ BlackHole 2ch
   - Rename to: "Mic + Zoom Audio"
   - This combines your mic input with Zoom audio from BlackHole

### Usage (Before Each Meeting)

**Step 1: Configure Zoom audio output**
```
Zoom → Settings → Audio
Output: Select "Zoom Output + BlackHole"
```

**Step 2: Start miclog transcription**
```bash
cd /Users/misterg/projects/misterg-sidekick

# List devices to find your "Mic + Zoom Audio" aggregate device
python -m sidekick.clients.miclog list-devices

# Start transcription (replace XX with your aggregate device ID)
python -m sidekick.clients.miclog transcribe --device XX \
  --output "meeting_$(date +%Y-%m-%d_%H%M).txt" --echo
```

**Step 3: Join Zoom meeting**

Your microphone still works normally in Zoom. Miclog will capture:
- ✅ Your voice (from your microphone)
- ✅ Others' voices (from Zoom, via BlackHole)

**Step 4: After meeting**

Press `Ctrl+C` to stop transcription. Your transcript file is saved.

**Step 5: Reset Zoom audio (optional)**
```
Zoom → Settings → Audio
Output: Select your normal speakers
```

---

## Option 2: Automatic Transcription (Advanced)

Automatically start transcription when Zoom meetings begin.

### Prerequisites

1. Install BlackHole (see Option 1 above)
2. Configure audio routing (see Option 1 above)
3. Set Zoom to always use "Zoom Output + BlackHole" (don't reset after meetings)

### Automatic Startup Script

I'll create a script that monitors for Zoom meetings and auto-starts transcription.

Create this file: `~/bin/zoom-transcribe-auto.sh`

```bash
#!/bin/bash

# Configuration
MICLOG_PATH="/Users/misterg/projects/misterg-sidekick"
DEVICE_ID="XX"  # Replace with your "Mic + Zoom Audio" device ID
OUTPUT_DIR="$HOME/Documents/Zoom Transcripts"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Monitoring for Zoom meetings..."

# Monitor Zoom process
while true; do
    # Check if Zoom meeting is active (window title contains "Zoom Meeting")
    ZOOM_MEETING=$(osascript -e 'tell application "System Events" to get name of every window of (every process whose name is "zoom.us")' 2>/dev/null | grep -i "zoom meeting")

    if [ ! -z "$ZOOM_MEETING" ]; then
        # Meeting detected
        TIMESTAMP=$(date +%Y-%m-%d_%H%M)
        OUTPUT_FILE="$OUTPUT_DIR/zoom_meeting_$TIMESTAMP.txt"

        echo "Zoom meeting detected! Starting transcription..."
        echo "Output: $OUTPUT_FILE"

        # Start transcription
        cd "$MICLOG_PATH"
        python -m sidekick.clients.miclog transcribe \
            --device "$DEVICE_ID" \
            --output "$OUTPUT_FILE" \
            --echo &

        MICLOG_PID=$!
        echo "Transcription started (PID: $MICLOG_PID)"

        # Wait for meeting to end
        while true; do
            sleep 10
            ZOOM_STILL_ACTIVE=$(osascript -e 'tell application "System Events" to get name of every window of (every process whose name is "zoom.us")' 2>/dev/null | grep -i "zoom meeting")

            if [ -z "$ZOOM_STILL_ACTIVE" ]; then
                echo "Meeting ended. Stopping transcription..."
                kill -INT $MICLOG_PID 2>/dev/null
                wait $MICLOG_PID 2>/dev/null
                echo "Transcript saved: $OUTPUT_FILE"
                break
            fi
        done
    fi

    sleep 5
done
```

Make it executable:
```bash
chmod +x ~/bin/zoom-transcribe-auto.sh
```

### Set Your Device ID

Find your aggregate device ID:
```bash
python -m sidekick.clients.miclog list-devices
```

Edit the script:
```bash
nano ~/bin/zoom-transcribe-auto.sh
# Change DEVICE_ID="XX" to your actual device ID
```

### Run Automatically on Login

**Option A: LaunchAgent (runs in background)**

Create `~/Library/LaunchAgents/com.user.zoom-transcribe.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.zoom-transcribe</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/misterg/bin/zoom-transcribe-auto.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/zoom-transcribe.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/zoom-transcribe.error.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.user.zoom-transcribe.plist
```

Unload it (to stop):
```bash
launchctl unload ~/Library/LaunchAgents/com.user.zoom-transcribe.plist
```

**Option B: Manual start**

Just run the script when you want auto-transcription:
```bash
~/bin/zoom-transcribe-auto.sh
```

Leave it running in a terminal. It will automatically transcribe all Zoom meetings.

---

## Option 3: Zoom's Built-in Transcription

**Important Note:** You already have access to Zoom's AI-generated transcripts via the sidekick Zoom client!

Your existing zoom.py client can fetch transcripts automatically:

```bash
# Get transcript for a specific meeting
python -m sidekick.clients.zoom get-transcript <meeting-id>

# Find meetings by date and get transcripts
python -m sidekick.clients.zoom list-meetings --from 2026-04-29

# Get summary (AI Companion summary)
python -m sidekick.clients.zoom get-summary <meeting-id>
```

**Comparison:**

| Feature | Miclog (Local) | Zoom API |
|---------|----------------|----------|
| **Requires Zoom recording** | No | Yes (cloud recording must be enabled) |
| **Real-time transcription** | Yes | No (after meeting ends) |
| **Works offline** | Yes (processing is local) | No (requires Zoom Cloud) |
| **Audio quality** | Depends on audio routing | High (Zoom's recording) |
| **Accuracy** | High (Whisper large model) | High (Zoom's AI) |
| **Storage** | Local files | Zoom Cloud (auto-deleted after 30 days) |
| **Setup complexity** | High (audio routing) | Low (just enable recording) |

**Recommendation:** Use both!
- Enable Zoom cloud recording for backup transcripts
- Use miclog for real-time, always-on transcription

---

## Quick Start Summary

### Simplest Approach (Manual, per-meeting):

1. **Install BlackHole:**
   ```bash
   brew install blackhole-2ch
   ```

2. **Configure audio routing** (see "Configure Audio Routing" section above)

3. **Before meeting:**
   ```bash
   # Set Zoom output to "Zoom Output + BlackHole"
   # Find your aggregate device
   python -m sidekick.clients.miclog list-devices

   # Start transcription
   python -m sidekick.clients.miclog transcribe --device <ID> \
     --output meeting.txt --echo
   ```

4. **Join Zoom meeting** - everything is recorded

5. **After meeting:** Press Ctrl+C

### Automatic Approach:

1. Complete "Simplest Approach" setup
2. Create and configure `~/bin/zoom-transcribe-auto.sh`
3. Run it: `~/bin/zoom-transcribe-auto.sh`
4. Leave running - it auto-transcribes all Zoom meetings

---

## Troubleshooting

**Can't hear Zoom audio?**
- Make sure "Zoom Output + BlackHole" multi-output device includes your speakers
- Check the "Drift Correction" box in Audio MIDI Setup for the multi-output device

**Transcription is empty or only has your voice?**
- Verify Zoom output is set to "Zoom Output + BlackHole"
- Check that miclog is using the "Mic + Zoom Audio" aggregate device
- Test BlackHole with: `sudo kextload /Library/Extensions/BlackHole.kext` (if needed)

**Audio quality is poor?**
- Use a good microphone (your CalDigit ID: 99 is probably best)
- Position yourself close to the microphone
- Ask Zoom participants to use good audio setups

**Automatic script not working?**
- Check logs: `tail -f /tmp/zoom-transcribe.log`
- Make sure Zoom window title contains "Zoom Meeting" when active
- Verify device ID is correct in the script

**Zoom's audio is delayed in transcription?**
- This is normal - there's a 5-10 second processing delay per chunk
- The transcript will catch up after the meeting

---

## Privacy & Ethics

**Important:**
- ⚠️ **Inform meeting participants** that you're recording/transcribing
- Many jurisdictions require consent for recording conversations
- Zoom meetings may already be recorded by the host
- Store transcripts securely (they contain sensitive information)
- Delete transcripts when no longer needed

**Best Practice:**
"I'm transcribing this meeting for my own notes. Is everyone okay with that?"

---

## Output Format

Transcripts look like this:

```
[2026-04-29 14:30:15] Okay everyone, let's get started with the standup.
[2026-04-29 14:30:22] Alice, can you go first and share what you worked on yesterday?
[2026-04-29 14:30:28] Sure, I finished the authentication refactor and deployed to staging.
[2026-04-29 14:30:35] Great work. Bob, you're next.
```

Each line has a timestamp showing when that 5-second chunk was spoken.

---

## Next Steps

1. **Test the setup:**
   - Install BlackHole
   - Configure audio routing
   - Start a test Zoom meeting with yourself
   - Verify transcription captures both sides

2. **Choose your approach:**
   - Manual (simpler, per-meeting)
   - Automatic (more complex, always-on)

3. **Create workflow:**
   - Where will transcripts be saved?
   - How long will you keep them?
   - Will you summarize them with AI after?

Need help setting this up? Let me know which approach you want to use and I'll guide you through each step.
