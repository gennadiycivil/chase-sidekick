# Microphone Selection Guide

When your Mac has multiple microphones (e.g., docked with external audio interface, webcam, or USB mic), you can choose which one to use for transcription.

## Quick Start

### 1. List Your Microphones

```bash
cd /Users/misterg/projects/misterg-sidekick
python -m sidekick.clients.miclog list-devices
```

**Example output:**
```
Available audio input devices:

  ID: 99  - CalDigit Thunderbolt 3 Audio
  ID: 95  - HD Pro Webcam C920
  ID: 83  - MacBook Pro Microphone (default)
  ID: 88  - ZoomAudioDevice
```

The `(default)` marker shows which microphone your Mac is currently using.

### 2. Use a Specific Microphone

Add `--device <ID>` to any transcribe command:

```bash
# Use device 99 (CalDigit audio interface)
python -m sidekick.clients.miclog transcribe --device 99 --duration 10

# Use device 95 (webcam mic) for meeting
python -m sidekick.clients.miclog transcribe --device 95 --output meeting.txt --echo
```

## Common Scenarios

### Docked Setup

When your Mac is docked with an external audio interface:

```bash
# Find your preferred dock microphone
python -m sidekick.clients.miclog list-devices

# Use it for transcription (example: device 99)
python -m sidekick.clients.miclog transcribe --device 99 --output notes.txt
```

### Webcam Microphone

If you want to use your webcam's microphone instead of the built-in Mac mic:

```bash
# List devices and find your webcam (e.g., "HD Pro Webcam")
python -m sidekick.clients.miclog list-devices

# Use webcam mic (example: device 95)
python -m sidekick.clients.miclog transcribe --device 95
```

### USB Microphone

For external USB microphones:

```bash
# Your USB mic will appear in the device list
python -m sidekick.clients.miclog list-devices

# Use it by ID
python -m sidekick.clients.miclog transcribe --device <ID>
```

## How It Works

When you specify `--device <ID>`, miclog:
1. Temporarily sets that device as the system default input
2. Records using that device
3. The change only affects the miclog process
4. Your system default returns to normal after recording stops

## No Device Specified?

If you don't specify `--device`, miclog uses your Mac's current default input device (marked with `(default)` in the list).

## Direct Binary Usage

You can also use the Swift binary directly:

```bash
cd /Users/misterg/projects/misterg-sidekick/miclog

# List devices
./miclog --list-devices

# Use specific device
./miclog --device 99 --test 30

# Combine with other options
./miclog --device 95 --test 60 > transcript.txt
```

## Finding the Right Microphone

Not sure which device to use? Try this:

1. **List all devices:**
   ```bash
   python -m sidekick.clients.miclog list-devices
   ```

2. **Test each one:**
   ```bash
   # Try device 99
   python -m sidekick.clients.miclog transcribe --device 99 --duration 5
   # Say "Testing device 99" while recording

   # Try device 95
   python -m sidekick.clients.miclog transcribe --device 95 --duration 5
   # Say "Testing device 95" while recording
   ```

3. **Pick the one that:**
   - Transcribes your voice most clearly
   - Has the best audio quality
   - Is positioned where you'll be speaking

## Tips

- **Built-in Mac mic** is usually good enough for solo use
- **Webcam mics** work well when you're facing the webcam
- **External USB/audio interface mics** provide the best quality
- **Test before important meetings** to make sure you've selected the right device

## Troubleshooting

**Device not appearing?**
- Make sure it's plugged in and recognized by macOS
- Check System Settings → Sound → Input to verify it's listed

**Transcription is empty?**
- Device might not be picking up audio
- Try a different device from the list
- Check microphone volume in System Settings → Sound → Input

**"Could not set audio input device" warning?**
- The device ID might be invalid
- Re-run `list-devices` to get current device IDs
- Device might have disconnected (unplug/replug and try again)
