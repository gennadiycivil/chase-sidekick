#!/usr/bin/env python3
"""
Miclog client - Real-time microphone transcription using whisper.cpp

This client wraps the miclog Swift CLI tool for transcribing audio from
the macOS microphone. It provides both a Python API and command-line interface.

Requirements:
    - macOS (uses AVFoundation)
    - whisper.cpp (brew install whisper-cpp)
    - Whisper large model (see setup instructions)

Architecture:
    - Swift CLI tool (miclog/miclog) handles audio recording + transcription
    - Python client provides process management and output streaming
    - No external Python dependencies (stdlib only)
"""

import os
import subprocess
import sys
import signal
import time
from pathlib import Path
from typing import Optional, Iterator


class MiclogClient:
    """Client for real-time microphone transcription using whisper.cpp"""

    def __init__(self, binary_path: Optional[str] = None):
        """
        Initialize miclog client

        Args:
            binary_path: Path to miclog binary (default: searches standard locations)
        """
        self.binary_path = binary_path or self._find_miclog_binary()
        if not self.binary_path:
            raise RuntimeError("miclog binary not found - run 'make' in miclog/ directory")

        if not os.path.exists(self.binary_path):
            raise RuntimeError(f"miclog binary not found at: {self.binary_path}")

    def _find_miclog_binary(self) -> Optional[str]:
        """Find miclog binary in standard locations"""
        # Check sidekick project directory
        project_root = Path(__file__).parent.parent.parent
        possible_paths = [
            project_root / "miclog" / "miclog",
            Path.home() / "bin" / "miclog",
            Path("/usr/local/bin/miclog"),
            Path("/opt/homebrew/bin/miclog"),
        ]

        for path in possible_paths:
            if path.exists() and os.access(path, os.X_OK):
                return str(path)

        return None

    def list_devices(self) -> list[dict]:
        """
        List available audio input devices

        Returns:
            List of dicts with 'id', 'name', and 'is_default' keys
        """
        if not self.binary_path:
            raise RuntimeError("miclog binary not found")

        result = subprocess.run(
            [self.binary_path, "--list-devices"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to list devices: {result.stderr}")

        devices = []
        for line in result.stderr.split('\n'):
            # Parse lines like: "  ID: 99 - CalDigit Thunderbolt 3 Audio (default)"
            if line.strip().startswith("ID:"):
                parts = line.strip().split(" - ", 1)
                if len(parts) == 2:
                    device_id = parts[0].replace("ID:", "").strip()
                    name_part = parts[1]
                    is_default = "(default)" in name_part
                    name = name_part.replace(" (default)", "").strip()

                    devices.append({
                        "id": device_id,
                        "name": name,
                        "is_default": is_default
                    })

        return devices

    def check_setup(self) -> dict:
        """
        Check if miclog is properly set up (whisper-cli and model)

        Returns:
            dict with status information
        """
        if not self.binary_path:
            return {
                "binary_found": False,
                "whisper_installed": False,
                "model_found": False,
                "ready": False,
                "stderr": "miclog binary not found"
            }

        result = subprocess.run(
            [self.binary_path, "--test", "0"],
            capture_output=True,
            text=True
        )

        return {
            "binary_found": True,
            "whisper_installed": "whisper-cli not found" not in result.stderr,
            "model_found": "Model not found" not in result.stderr,
            "ready": result.returncode == 0,
            "stderr": result.stderr
        }

    def transcribe(
        self,
        duration: Optional[int] = None,
        output_file: Optional[str] = None,
        device_id: Optional[str] = None,
        append: bool = False
    ) -> Iterator[str]:
        """
        Start real-time transcription

        Args:
            duration: Optional duration in seconds (None = run until stopped)
            output_file: Optional file path to save transcription
            device_id: Optional audio device ID to use
            append: If True, append to existing file; otherwise overwrite

        Yields:
            Transcribed text lines as they become available
        """
        if not self.binary_path:
            raise RuntimeError("miclog binary not found")

        cmd = [self.binary_path]

        if device_id is not None:
            cmd.extend(["--device", device_id])

        if duration is not None:
            cmd.extend(["--test", str(duration)])

        # Open output file if specified
        output_fh = None
        if output_file:
            mode = 'a' if append else 'w'
            output_fh = open(output_file, mode)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )

            # Stream output line by line
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        line = line.rstrip('\n')
                        if output_fh:
                            output_fh.write(line + '\n')
                            output_fh.flush()
                        yield line

            process.wait()

        finally:
            if output_fh:
                output_fh.close()

    def transcribe_to_file(
        self,
        output_file: str,
        duration: Optional[int] = None,
        echo: bool = True,
        device_id: Optional[str] = None,
        append: bool = False
    ) -> None:
        """
        Transcribe to file with optional console echo

        Args:
            output_file: Path to save transcription
            duration: Optional duration in seconds
            echo: If True, also print to stdout
            device_id: Optional audio device ID to use
            append: If True, append to existing file; otherwise overwrite
        """
        for line in self.transcribe(duration=duration, output_file=output_file, device_id=device_id, append=append):
            if echo:
                print(line)


def main():
    """Command-line interface for miclog client"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Real-time microphone transcription using whisper.cpp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check if miclog is set up correctly
  python -m sidekick.clients.miclog check-setup

  # Transcribe to stdout until Ctrl+C
  python -m sidekick.clients.miclog transcribe

  # Transcribe for 30 seconds
  python -m sidekick.clients.miclog transcribe --duration 30

  # Save to file
  python -m sidekick.clients.miclog transcribe --output transcript.txt

  # Save to file with console echo
  python -m sidekick.clients.miclog transcribe --output transcript.txt --echo

Setup Instructions:
  1. Build the miclog binary:
     cd miclog && make

  2. Install whisper.cpp:
     brew install whisper-cpp

  3. Download Whisper large model:
     mkdir -p .whisper-models
     curl -L https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin \\
       -o .whisper-models/ggml-large-v3.bin
        """
    )

    parser.add_argument(
        "--binary",
        help="Path to miclog binary (default: auto-detect)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-devices command
    subparsers.add_parser(
        "list-devices",
        help="List available audio input devices"
    )

    # check-setup command
    subparsers.add_parser(
        "check-setup",
        help="Check if miclog is properly configured"
    )

    # transcribe command
    transcribe_parser = subparsers.add_parser(
        "transcribe",
        help="Start real-time transcription"
    )
    transcribe_parser.add_argument(
        "--device",
        help="Audio device ID to use (see list-devices)"
    )
    transcribe_parser.add_argument(
        "--duration",
        type=int,
        help="Duration in seconds (default: run until Ctrl+C)"
    )
    transcribe_parser.add_argument(
        "--output",
        help="Save transcription to file"
    )
    transcribe_parser.add_argument(
        "--echo",
        action="store_true",
        help="Echo to stdout when saving to file"
    )
    transcribe_parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing file instead of overwriting"
    )

    args = parser.parse_args()

    try:
        client = MiclogClient(binary_path=args.binary)

        if args.command == "list-devices":
            devices = client.list_devices()
            if not devices:
                print("No audio input devices found")
                sys.exit(1)

            print("Available audio input devices:\n")
            for device in devices:
                default_marker = " (default)" if device['is_default'] else ""
                print(f"  ID: {device['id']:3s} - {device['name']}{default_marker}")

            print("\nUse --device <ID> with the transcribe command to select a device")

        elif args.command == "check-setup":
            status = client.check_setup()
            print("Miclog Setup Status:")
            print(f"  Binary found: {status['binary_found']}")
            print(f"  whisper-cli installed: {status['whisper_installed']}")
            print(f"  Model found: {status['model_found']}")
            print(f"  Ready: {status['ready']}")

            if not status['ready']:
                print("\nSetup required:")
                print(status['stderr'])
                sys.exit(1)
            else:
                print("\n✓ Miclog is ready to use")

        elif args.command == "transcribe":
            device_id = getattr(args, 'device', None)
            append = getattr(args, 'append', False)
            if args.output:
                client.transcribe_to_file(
                    output_file=args.output,
                    duration=args.duration,
                    echo=args.echo,
                    device_id=device_id,
                    append=append
                )
            else:
                for line in client.transcribe(duration=args.duration, device_id=device_id):
                    print(line)

    except KeyboardInterrupt:
        print("\nStopped by user", file=sys.stderr)
        sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
