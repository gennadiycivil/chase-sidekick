"""Video Analysis Client - extract frames, audio, and subtitles from MP4 files."""

import sys
import json
import subprocess
import tempfile
import os
import base64
from typing import Optional, List, Dict


class VideoClient:
    """Video analysis client using ffmpeg for extraction."""

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        """Initialize Video client.

        Args:
            ffmpeg_path: Path to ffmpeg binary
            ffprobe_path: Path to ffprobe binary
        """
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

    def get_video_info(self, video_path: str) -> dict:
        """Get video metadata using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            Dict with duration, width, height, fps, codec info

        Raises:
            ValueError: If video_path is empty or file not found
            RuntimeError: If ffprobe fails
        """
        if not video_path:
            raise ValueError("video_path is required")
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not found: {video_path}")

        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffprobe failed: {result.stderr}")

            data = json.loads(result.stdout)

            # Extract video stream info
            video_stream = None
            audio_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video" and not video_stream:
                    video_stream = stream
                elif stream.get("codec_type") == "audio" and not audio_stream:
                    audio_stream = stream

            format_info = data.get("format", {})

            info = {
                "duration": float(format_info.get("duration", 0)),
                "size_bytes": int(format_info.get("size", 0)),
                "format_name": format_info.get("format_name", "unknown"),
            }

            if video_stream:
                info.update({
                    "width": int(video_stream.get("width", 0)),
                    "height": int(video_stream.get("height", 0)),
                    "codec": video_stream.get("codec_name", "unknown"),
                    "fps": eval(video_stream.get("r_frame_rate", "0/1")),
                })

            if audio_stream:
                info["has_audio"] = True
                info["audio_codec"] = audio_stream.get("codec_name", "unknown")
            else:
                info["has_audio"] = False

            return info

        except subprocess.TimeoutExpired:
            raise RuntimeError("ffprobe timed out")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse ffprobe output: {e}")
        except Exception as e:
            raise RuntimeError(f"Error getting video info: {e}")

    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        interval_seconds: float = 5.0,
        max_frames: Optional[int] = None
    ) -> List[str]:
        """Extract frames from video at regular intervals.

        Args:
            video_path: Path to video file
            output_dir: Directory to save extracted frames
            interval_seconds: Extract one frame every N seconds
            max_frames: Maximum number of frames to extract (None = all)

        Returns:
            List of paths to extracted frame images

        Raises:
            ValueError: If paths are invalid
            RuntimeError: If ffmpeg fails
        """
        if not video_path or not output_dir:
            raise ValueError("video_path and output_dir are required")
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not found: {video_path}")

        os.makedirs(output_dir, exist_ok=True)

        # Get video duration to calculate frame count
        info = self.get_video_info(video_path)
        duration = info.get("duration", 0)

        if duration == 0:
            raise ValueError("Could not determine video duration")

        # Calculate how many frames we'll extract
        total_frames = int(duration / interval_seconds) + 1
        if max_frames and total_frames > max_frames:
            # Adjust interval to fit max_frames
            interval_seconds = duration / max_frames

        output_pattern = os.path.join(output_dir, "frame_%04d.png")

        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-vf", f"fps=1/{interval_seconds}",
            "-frames:v", str(max_frames) if max_frames else str(total_frames),
            output_pattern
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr}")

            # List extracted frames
            frames = sorted([
                os.path.join(output_dir, f)
                for f in os.listdir(output_dir)
                if f.startswith("frame_") and f.endswith(".png")
            ])

            return frames

        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg timed out during frame extraction")
        except Exception as e:
            raise RuntimeError(f"Error extracting frames: {e}")

    def extract_audio(
        self,
        video_path: str,
        output_path: str,
        format: str = "wav"
    ) -> str:
        """Extract audio track from video.

        Args:
            video_path: Path to video file
            output_path: Path to save audio file
            format: Output audio format (wav, mp3)

        Returns:
            Path to extracted audio file

        Raises:
            ValueError: If paths are invalid
            RuntimeError: If ffmpeg fails
        """
        if not video_path or not output_path:
            raise ValueError("video_path and output_path are required")
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not found: {video_path}")

        # Check if video has audio
        info = self.get_video_info(video_path)
        if not info.get("has_audio"):
            raise ValueError("Video has no audio track")

        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-vn",  # No video
            "-acodec", "pcm_s16le" if format == "wav" else "libmp3lame",
            "-ar", "16000",  # 16kHz sample rate for speech
            "-ac", "1",  # Mono
            output_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr}")

            return output_path

        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg timed out during audio extraction")
        except Exception as e:
            raise RuntimeError(f"Error extracting audio: {e}")

    def extract_subtitles(self, video_path: str, output_path: str) -> Optional[str]:
        """Extract embedded subtitles from video.

        Args:
            video_path: Path to video file
            output_path: Path to save subtitle file (.srt)

        Returns:
            Path to subtitle file if found, None if no subtitles

        Raises:
            ValueError: If paths are invalid
            RuntimeError: If ffmpeg fails
        """
        if not video_path or not output_path:
            raise ValueError("video_path and output_path are required")
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not found: {video_path}")

        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-map", "0:s:0",  # First subtitle stream
            output_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            # If no subtitle stream, ffmpeg returns error
            if result.returncode != 0:
                if "does not contain any stream" in result.stderr or \
                   "Stream map" in result.stderr:
                    return None
                raise RuntimeError(f"ffmpeg failed: {result.stderr}")

            return output_path if os.path.exists(output_path) else None

        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg timed out during subtitle extraction")
        except Exception as e:
            raise RuntimeError(f"Error extracting subtitles: {e}")

    def analyze_video(
        self,
        video_path: str,
        interval_seconds: float = 5.0,
        max_frames: int = 20
    ) -> dict:
        """Analyze video by extracting frames, audio, and subtitles.

        Args:
            video_path: Path to video file
            interval_seconds: Extract one frame every N seconds
            max_frames: Maximum number of frames to extract

        Returns:
            Dict with:
                - info: Video metadata
                - frames: List of frame file paths
                - audio: Audio file path if extracted
                - subtitles: Subtitle file path if found

        Raises:
            ValueError: If video_path is invalid
            RuntimeError: If extraction fails
        """
        if not video_path:
            raise ValueError("video_path is required")

        # Get video info
        info = self.get_video_info(video_path)

        # Create temp directory for extraction
        temp_dir = tempfile.mkdtemp(prefix="video_analysis_")

        result = {
            "info": info,
            "frames": [],
            "audio": None,
            "subtitles": None,
            "temp_dir": temp_dir
        }

        try:
            # Extract frames
            frames_dir = os.path.join(temp_dir, "frames")
            result["frames"] = self.extract_frames(
                video_path,
                frames_dir,
                interval_seconds,
                max_frames
            )

            # Extract audio if present
            if info.get("has_audio"):
                audio_path = os.path.join(temp_dir, "audio.wav")
                try:
                    result["audio"] = self.extract_audio(video_path, audio_path)
                except Exception as e:
                    # Audio extraction is optional
                    result["audio_error"] = str(e)

            # Extract subtitles if present
            subtitle_path = os.path.join(temp_dir, "subtitles.srt")
            try:
                result["subtitles"] = self.extract_subtitles(video_path, subtitle_path)
            except Exception as e:
                # Subtitles are optional
                result["subtitle_error"] = str(e)

            return result

        except Exception as e:
            # Clean up temp directory on error
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise


def _format_video_info(info: dict) -> str:
    """Format video info as human-readable text."""
    duration_min = int(info.get("duration", 0) / 60)
    duration_sec = int(info.get("duration", 0) % 60)
    size_mb = info.get("size_bytes", 0) / (1024 * 1024)

    lines = [
        f"Duration: {duration_min}m {duration_sec}s",
        f"Size: {size_mb:.1f} MB",
        f"Format: {info.get('format_name', 'unknown')}",
    ]

    if "width" in info:
        lines.append(f"Resolution: {info['width']}x{info['height']}")
        lines.append(f"Codec: {info.get('codec', 'unknown')}")
        lines.append(f"FPS: {info.get('fps', 0):.2f}")

    if info.get("has_audio"):
        lines.append(f"Audio: {info.get('audio_codec', 'unknown')}")
    else:
        lines.append("Audio: none")

    return "\n".join(lines)


def main():
    """CLI entry point for Video client.

    Usage:
        python3 -m sidekick.clients.video info <video-path>
        python3 -m sidekick.clients.video extract-frames <video-path> <output-dir> [--interval 5.0] [--max-frames 20]
        python3 -m sidekick.clients.video extract-audio <video-path> <output-path>
        python3 -m sidekick.clients.video extract-subtitles <video-path> <output-path>
        python3 -m sidekick.clients.video analyze <video-path> [--interval 5.0] [--max-frames 20]
    """
    if len(sys.argv) < 2:
        print("Usage: python3 -m sidekick.clients.video <command> [args...]")
        print("\nCommands:")
        print("  info <video-path>")
        print("  extract-frames <video-path> <output-dir> [--interval N] [--max-frames N]")
        print("  extract-audio <video-path> <output-path>")
        print("  extract-subtitles <video-path> <output-path>")
        print("  analyze <video-path> [--interval N] [--max-frames N]")
        sys.exit(1)

    try:
        client = VideoClient()
        command = sys.argv[1]

        if command == "info":
            if len(sys.argv) < 3:
                print("Error: video-path required", file=sys.stderr)
                sys.exit(1)
            info = client.get_video_info(sys.argv[2])
            print(_format_video_info(info))

        elif command == "extract-frames":
            if len(sys.argv) < 4:
                print("Error: video-path and output-dir required", file=sys.stderr)
                sys.exit(1)

            video_path = sys.argv[2]
            output_dir = sys.argv[3]
            interval = 5.0
            max_frames = None

            # Parse optional args
            for i in range(4, len(sys.argv)):
                if sys.argv[i] == "--interval" and i + 1 < len(sys.argv):
                    interval = float(sys.argv[i + 1])
                elif sys.argv[i] == "--max-frames" and i + 1 < len(sys.argv):
                    max_frames = int(sys.argv[i + 1])

            frames = client.extract_frames(video_path, output_dir, interval, max_frames)
            print(f"Extracted {len(frames)} frames to {output_dir}:")
            for frame in frames:
                print(f"  {frame}")

        elif command == "extract-audio":
            if len(sys.argv) < 4:
                print("Error: video-path and output-path required", file=sys.stderr)
                sys.exit(1)

            audio_path = client.extract_audio(sys.argv[2], sys.argv[3])
            print(f"Extracted audio to: {audio_path}")

        elif command == "extract-subtitles":
            if len(sys.argv) < 4:
                print("Error: video-path and output-path required", file=sys.stderr)
                sys.exit(1)

            subtitle_path = client.extract_subtitles(sys.argv[2], sys.argv[3])
            if subtitle_path:
                print(f"Extracted subtitles to: {subtitle_path}")
            else:
                print("No subtitles found in video")

        elif command == "analyze":
            if len(sys.argv) < 3:
                print("Error: video-path required", file=sys.stderr)
                sys.exit(1)

            video_path = sys.argv[2]
            interval = 5.0
            max_frames = 20

            # Parse optional args
            for i in range(3, len(sys.argv)):
                if sys.argv[i] == "--interval" and i + 1 < len(sys.argv):
                    interval = float(sys.argv[i + 1])
                elif sys.argv[i] == "--max-frames" and i + 1 < len(sys.argv):
                    max_frames = int(sys.argv[i + 1])

            result = client.analyze_video(video_path, interval, max_frames)

            print("Video Analysis")
            print("=" * 60)
            print("\nVideo Info:")
            print(_format_video_info(result["info"]))
            print(f"\nExtracted {len(result['frames'])} frames")
            if result.get("audio"):
                print(f"Extracted audio: {result['audio']}")
            if result.get("subtitles"):
                print(f"Extracted subtitles: {result['subtitles']}")
            print(f"\nAll files saved to: {result['temp_dir']}")
            print("\nNote: Temp directory will be cleaned up on exit.")

        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            sys.exit(1)

    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
