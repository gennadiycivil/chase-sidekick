---
skill: video
description: Analyze MP4 videos by extracting frames, audio, and subtitles
dependencies: ffmpeg, ffprobe
---

# Video Analysis Skill

Analyze MP4 video files by extracting frames, audio tracks, and embedded subtitles using the video client.

## Prerequisites

Requires `ffmpeg` and `ffprobe` to be installed:

```bash
# macOS
brew install ffmpeg

# Linux (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Check installation
which ffmpeg ffprobe
```

## Commands

### Get Video Information

```bash
python -m sidekick.clients.video info video.mp4
```

Output:
```
Duration: 2m 34s
Size: 45.2 MB
Format: mov,mp4,m4a,3gp,3g2,mj2
Resolution: 1920x1080
Codec: h264
FPS: 30.00
Audio: aac
```

### Extract Frames

Extract frames at regular intervals:

```bash
# Extract 1 frame every 5 seconds
python -m sidekick.clients.video extract-frames video.mp4 ./frames --interval 5.0

# Extract maximum 20 frames
python -m sidekick.clients.video extract-frames video.mp4 ./frames --max-frames 20

# Both options
python -m sidekick.clients.video extract-frames video.mp4 ./frames --interval 10.0 --max-frames 15
```

Frames are saved as PNG files: `frame_0001.png`, `frame_0002.png`, etc.

### Extract Audio

Extract audio track as WAV file:

```bash
python -m sidekick.clients.video extract-audio video.mp4 audio.wav
```

Output is mono, 16kHz WAV file suitable for speech transcription.

### Extract Subtitles

Extract embedded subtitles if present:

```bash
python -m sidekick.clients.video extract-subtitles video.mp4 subtitles.srt
```

Returns nothing if no subtitles are embedded in the video.

### Full Analysis

Perform complete analysis (frames + audio + subtitles):

```bash
python -m sidekick.clients.video analyze video.mp4 --interval 5.0 --max-frames 20
```

This creates a temporary directory with:
- `frames/` - Extracted frame images
- `audio.wav` - Audio track (if present)
- `subtitles.srt` - Subtitles (if present)

## Python API

```python
from sidekick.clients.video import VideoClient

client = VideoClient()

# Get video metadata
info = client.get_video_info("video.mp4")
print(f"Duration: {info['duration']} seconds")
print(f"Resolution: {info['width']}x{info['height']}")

# Extract frames
frames = client.extract_frames(
    "video.mp4",
    "./frames",
    interval_seconds=5.0,
    max_frames=20
)
print(f"Extracted {len(frames)} frames")

# Extract audio
if info.get("has_audio"):
    audio_path = client.extract_audio("video.mp4", "audio.wav")
    print(f"Audio saved to: {audio_path}")

# Extract subtitles
subtitle_path = client.extract_subtitles("video.mp4", "subtitles.srt")
if subtitle_path:
    print(f"Subtitles saved to: {subtitle_path}")

# Full analysis
result = client.analyze_video("video.mp4", interval_seconds=5.0, max_frames=20)
print(f"Extracted {len(result['frames'])} frames")
print(f"Audio: {result.get('audio', 'none')}")
print(f"Subtitles: {result.get('subtitles', 'none')}")
print(f"Temp dir: {result['temp_dir']}")
```

## Claude Code Integration

When Claude needs to analyze a video:

1. **Extract frames** at appropriate intervals (5-10 seconds for long videos, 1-2 seconds for short ones)
2. **Read each frame** using Claude's Read tool (supports images)
3. **Extract subtitles** if available for text content
4. **Combine analysis** from frames + subtitles to understand video content

Example workflow:

```python
# 1. Analyze video
result = client.analyze_video("demo.mp4", interval_seconds=5.0, max_frames=20)

# 2. Claude reads each frame (using Read tool on each frame path)
# frames are in result['frames']

# 3. Claude reads subtitles if present
# subtitle file is at result['subtitles']

# 4. Claude combines all information to answer questions about the video
```

## Use Cases

- **Compare videos**: Extract frames from multiple videos and analyze differences
- **Demo analysis**: Understand what's shown in product demo videos
- **Meeting recordings**: Extract key frames from recorded meetings
- **Tutorial videos**: Analyze step-by-step tutorials
- **Progress updates**: Compare "before" and "after" videos

## Limitations

- **No built-in transcription**: Audio extraction works, but transcription requires external service (not yet implemented)
- **Frame-based analysis**: Video is analyzed as static frames, not continuous motion
- **Subtitle extraction**: Only works if subtitles are embedded in the MP4 file
- **Large videos**: Very long videos should use larger intervals or lower max_frames to avoid excessive extraction time

## Notes

- Extracted frames are PNG format for best quality with Claude's vision
- Audio is extracted as 16kHz mono WAV (standard for speech recognition)
- Temp directory from `analyze_video()` should be cleaned up after use
- ffmpeg timeout is 5 minutes for extraction operations
