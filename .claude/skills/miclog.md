---
name: miclog
description: Real-time microphone transcription for meeting notes
enabled: true
---

# Miclog Skill

Real-time microphone transcription using whisper.cpp. Useful for transcribing meetings, brainstorming sessions, or any spoken audio.

## Prerequisites Check

Before using, verify setup:

```bash
python -m sidekick.clients.miclog check-setup
```

If not set up, follow these steps:

1. **Build the miclog binary:**
   ```bash
   cd miclog && make
   ```

2. **Install whisper.cpp:**
   ```bash
   brew install whisper-cpp
   ```

3. **Download Whisper large model (~3GB):**
   ```bash
   mkdir -p .whisper-models
   curl -L https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin \
     -o .whisper-models/ggml-large-v3.bin
   ```

## Usage Patterns

### List Available Microphones
```bash
# See all audio input devices
python -m sidekick.clients.miclog list-devices
```

Output:
```
Available audio input devices:

  ID: 99  - CalDigit Thunderbolt 3 Audio
  ID: 95  - HD Pro Webcam C920
  ID: 83  - MacBook Pro Microphone (default)
```

### Quick Test (5 seconds)
```bash
# Use default microphone
python -m sidekick.clients.miclog transcribe --duration 5

# Use specific microphone
python -m sidekick.clients.miclog transcribe --duration 5 --device 99
```

### Meeting Transcription (save to file)
```bash
# Start before meeting (use default mic)
python -m sidekick.clients.miclog transcribe --output meeting_notes.txt --echo

# Or use specific microphone (useful when docked)
python -m sidekick.clients.miclog transcribe --device 99 --output meeting_notes.txt --echo

# Stop with Ctrl+C when meeting ends
```

### Daily Log (append mode)
```bash
# Each session appends to the same file
python -m sidekick.clients.miclog transcribe --output daily_$(date +%Y-%m-%d).txt
```

### Direct Binary Usage
```bash
# For maximum control, use the Swift binary directly
cd miclog
./miclog > transcript.txt
./miclog --test 30
```

## Output Format

Each line includes a timestamp:
```
[2026-04-29 15:05:03] This is the first transcribed segment.
[2026-04-29 15:05:08] This is the second transcribed segment.
```

## Meeting Workflow

1. **Before meeting:** Start transcription
   ```bash
   python -m sidekick.clients.miclog transcribe --output meeting.txt
   ```

2. **During meeting:** Let it run in background

3. **After meeting:** Press Ctrl+C to stop

4. **Summarize:** Use Claude or ChatGPT
   - Read `meeting.txt`
   - Ask: "Summarize this meeting transcript with key points and action items"

## Performance Notes

- **Latency:** 5-10 seconds per audio chunk
- **Accuracy:** High (uses large Whisper model)
- **Silent chunks:** Automatically skipped (no transcription)
- **Disk space:** Minimal (chunks auto-deleted)
- **Memory:** ~1-2GB (model loaded in memory)

## Troubleshooting

**"whisper-cli not found"**
```bash
brew install whisper-cpp
which whisper-cli  # Should show /opt/homebrew/bin/whisper-cli
```

**"Model not found"**
```bash
mkdir -p .whisper-models
curl -L https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin \
  -o .whisper-models/ggml-large-v3.bin
```

**"Permission denied" (microphone access)**
- Go to System Settings → Privacy & Security → Microphone
- Allow Terminal (or your IDE) to access the microphone

**Slow transcription**
- Large model is slow but accurate (~1x realtime on modern Macs)
- For faster results, download a smaller model (medium/small/base)

## Python API

```python
from sidekick.clients.miclog import MiclogClient

client = MiclogClient()

# Check setup
status = client.check_setup()
print(f"Ready: {status['ready']}")

# Stream transcription
for line in client.transcribe(duration=30):
    print(line)

# Save to file with echo
client.transcribe_to_file(
    output_file="transcript.txt",
    echo=True
)
```

## When to Use

- ✅ Recording meetings where you need a transcript
- ✅ Brainstorming sessions that you want to capture
- ✅ Interviews or conversations you want documented
- ✅ Dictating notes or ideas hands-free
- ✅ Any situation where meeting recording features are unavailable

## Privacy Notes

- All processing is **local** (no cloud APIs)
- Audio chunks stored temporarily in `/tmp/` and auto-deleted
- You control where transcripts are saved
- No data leaves your machine
