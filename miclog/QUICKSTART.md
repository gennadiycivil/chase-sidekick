# Miclog Quick Start Guide

Everything is installed and ready to use!

## Selecting Your Microphone

If you have multiple microphones (e.g., docked with external mic), first list available devices:

```bash
cd /Users/misterg/projects/misterg-sidekick
python -m sidekick.clients.miclog list-devices
```

You'll see output like:
```
Available audio input devices:

  ID: 99  - CalDigit Thunderbolt 3 Audio
  ID: 95  - HD Pro Webcam C920
  ID: 83  - MacBook Pro Microphone (default)
  ID: 88  - ZoomAudioDevice
```

Then use `--device <ID>` with the transcribe command to select which microphone to use.

## Basic Usage

### 1. Quick Test (5 seconds)
```bash
cd /Users/misterg/projects/misterg-sidekick
python -m sidekick.clients.miclog transcribe --duration 5
```

This will:
- Start recording from your microphone
- Transcribe for 5 seconds
- Show output with timestamps like: `[2026-04-29 12:30:15] Your transcribed text here`

### 2. Meeting Transcription (save to file)
```bash
# Start before your meeting
python -m sidekick.clients.miclog transcribe --output meeting_notes.txt --echo

# Let it run during the meeting
# Press Ctrl+C when done
```

The `--echo` flag shows transcription on screen AND saves to file.

### 3. Daily Log (append mode)
```bash
# Each time you run this, it appends to the same file
python -m sidekick.clients.miclog transcribe --output daily_log_$(date +%Y-%m-%d).txt
```

### 4. Simple Transcription (to screen only)
```bash
# Transcribe until you press Ctrl+C
python -m sidekick.clients.miclog transcribe

# Or transcribe for 30 seconds
python -m sidekick.clients.miclog transcribe --duration 30

# Use a specific microphone
python -m sidekick.clients.miclog transcribe --device 99
```

## Direct Binary Usage (Advanced)

If you prefer using the Swift binary directly:

```bash
cd /Users/misterg/projects/misterg-sidekick/miclog

# List available devices
./miclog --list-devices

# Transcribe to screen
./miclog

# Use specific device
./miclog --device 99

# Test mode (30 seconds)
./miclog --test 30

# Use specific device with test mode
./miclog --device 99 --test 30

# Save to file
./miclog > transcript.txt

# Live view while saving
./miclog 2>&1 | tee -a ~/meeting.txt
```

## Output Format

Each line includes a timestamp:
```
[2026-04-29 15:05:03] This is the first thing you said.
[2026-04-29 15:05:08] This is the second thing you said.
[2026-04-29 15:05:13] And this is the third segment.
```

## Tips

1. **Microphone Permission**: macOS will prompt for microphone access on first run - click "Allow"

2. **Processing Time**: There's a 5-10 second delay as it processes each 5-second chunk of audio

3. **Silent Chunks**: If no one is speaking, it automatically skips transcription to save CPU

4. **Stopping**: Press `Ctrl+C` to stop - it will finish processing any remaining audio chunks

5. **Meeting Workflow**:
   ```bash
   # Before meeting
   python -m sidekick.clients.miclog transcribe --output meeting.txt

   # During meeting - let it run

   # After meeting - press Ctrl+C

   # Summarize with AI
   # Copy meeting.txt and paste into Claude/ChatGPT
   # Ask: "Summarize this meeting with key points and action items"
   ```

## Check Setup Anytime

```bash
python -m sidekick.clients.miclog check-setup
```

This verifies:
- Binary is compiled
- whisper-cli is installed
- Model file is downloaded

## Troubleshooting

**No output appearing?**
- Wait 5-10 seconds - it processes in chunks
- Speak clearly into your microphone
- Check System Settings → Privacy & Security → Microphone

**"Model not found"?**
- The model is downloading in the background (~3GB)
- Check: `ls -lh .whisper-models/`
- Should see: `ggml-large-v3.bin (~3.1GB)`

**Slow transcription?**
- Normal - large model is accurate but CPU-intensive
- Processing is ~1x realtime (5 seconds of audio takes 5-10 seconds)

**Want faster transcription?**
- Download a smaller model (medium/small/base)
- Edit `miclog/main.swift` to use the smaller model
- Run `cd miclog && make` to rebuild

## Python API (for scripts)

```python
from sidekick.clients.miclog import MiclogClient

client = MiclogClient()

# Stream transcription
for line in client.transcribe(duration=30):
    print(line)
    # Do something with each transcribed line

# Save to file with echo
client.transcribe_to_file(
    output_file="transcript.txt",
    echo=True
)
```

## Ready to Try?

Run this now to test:
```bash
cd /Users/misterg/projects/misterg-sidekick
python -m sidekick.clients.miclog transcribe --duration 5
```

Then say something into your microphone and watch the transcription appear!
