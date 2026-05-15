#!/bin/bash

# Setup helper for Zoom + miclog transcription
# This script guides you through the setup process

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "Zoom + Miclog Transcription Setup"
echo "=========================================="
echo ""

# Step 1: Check BlackHole
echo "Step 1: Checking BlackHole installation..."
if ! brew list blackhole-2ch &>/dev/null; then
    echo ""
    echo "BlackHole is not installed. BlackHole is required to route Zoom audio."
    echo "BlackHole is free, open-source, and safe (created by Existential Audio)."
    echo ""
    read -p "Install BlackHole now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Installing BlackHole..."
        brew install blackhole-2ch
        echo ""
        echo "✓ BlackHole installed!"
        echo ""
        echo "⚠️  You MUST restart your Mac for BlackHole to work."
        echo "After restart, run this script again to continue setup."
        echo ""
        read -p "Restart now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo shutdown -r now
        else
            echo "Please restart manually, then run this script again."
            exit 0
        fi
    else
        echo "Cannot continue without BlackHole. Exiting."
        exit 1
    fi
else
    echo "✓ BlackHole is installed"
fi

echo ""
echo "Step 2: Audio device configuration..."
echo ""
echo "You need to create two virtual audio devices in Audio MIDI Setup:"
echo ""
echo "1. Multi-Output Device (sends Zoom audio to speakers AND BlackHole)"
echo "2. Aggregate Device (combines your mic + BlackHole for recording)"
echo ""
echo "Opening Audio MIDI Setup for you..."
echo ""
read -p "Press Enter to open Audio MIDI Setup..." -r

open -a "Audio MIDI Setup"

echo ""
echo "=========================================="
echo "Manual Configuration Required"
echo "=========================================="
echo ""
echo "In Audio MIDI Setup, do the following:"
echo ""
echo "CREATE MULTI-OUTPUT DEVICE:"
echo "  1. Click '+' (bottom left) → 'Create Multi-Output Device'"
echo "  2. Check these boxes:"
echo "     ☑ Your speakers/headphones (e.g., 'CalDigit Thunderbolt 3 Audio')"
echo "     ☑ BlackHole 2ch"
echo "  3. Rename to: 'Zoom Output + BlackHole'"
echo "  4. Check 'Drift Correction' for your main output"
echo ""
echo "CREATE AGGREGATE DEVICE:"
echo "  1. Click '+' (bottom left) → 'Create Aggregate Device'"
echo "  2. Check these boxes:"
echo "     ☑ Your microphone (e.g., 'CalDigit Thunderbolt 3 Audio')"
echo "     ☑ BlackHole 2ch"
echo "  3. Rename to: 'Mic + Zoom Audio'"
echo "  4. Check 'Drift Correction' for BlackHole 2ch"
echo ""
read -p "Press Enter when you've completed these steps..." -r

echo ""
echo "Step 3: Finding your aggregate device..."
echo ""

cd "$PROJECT_ROOT"
python -m sidekick.clients.miclog list-devices

echo ""
echo "Look for your 'Mic + Zoom Audio' device in the list above."
echo "Note its ID number - you'll need this!"
echo ""
read -p "What is the device ID? (just the number): " DEVICE_ID

if [[ ! $DEVICE_ID =~ ^[0-9]+$ ]]; then
    echo "Invalid device ID. Please run this script again."
    exit 1
fi

echo ""
echo "✓ Device ID: $DEVICE_ID"
echo ""

# Step 4: Create helper scripts
echo "Step 4: Creating helper scripts..."
echo ""

SCRIPTS_DIR="$HOME/bin"
mkdir -p "$SCRIPTS_DIR"

# Create manual transcription script
cat > "$SCRIPTS_DIR/zoom-transcribe.sh" <<EOFSRIPT
#!/bin/bash

# Quick script to start Zoom meeting transcription
# Usage: zoom-transcribe.sh [optional-output-file]

MICLOG_PATH="$PROJECT_ROOT"
DEVICE_ID="$DEVICE_ID"
OUTPUT_DIR="\$HOME/Documents/Zoom Transcripts"

mkdir -p "\$OUTPUT_DIR"

if [ -z "\$1" ]; then
    TIMESTAMP=\$(date +%Y-%m-%d_%H%M)
    OUTPUT_FILE="\$OUTPUT_DIR/zoom_meeting_\$TIMESTAMP.txt"
else
    OUTPUT_FILE="\$1"
fi

echo "Starting Zoom meeting transcription..."
echo "Output: \$OUTPUT_FILE"
echo ""
echo "⚠️  Make sure Zoom output is set to 'Zoom Output + BlackHole'!"
echo "   (Zoom → Settings → Audio → Output)"
echo ""
echo "Press Ctrl+C to stop transcription"
echo ""

cd "\$MICLOG_PATH"
python -m sidekick.clients.miclog transcribe \\
    --device "\$DEVICE_ID" \\
    --output "\$OUTPUT_FILE" \\
    --echo
EOFSRIPT

chmod +x "$SCRIPTS_DIR/zoom-transcribe.sh"

echo "✓ Created $SCRIPTS_DIR/zoom-transcribe.sh"
echo ""

# Create test script
cat > "$SCRIPTS_DIR/zoom-transcribe-test.sh" <<EOFTEST
#!/bin/bash

# Test your Zoom transcription setup
# This records for 10 seconds so you can verify it's working

MICLOG_PATH="$PROJECT_ROOT"
DEVICE_ID="$DEVICE_ID"

echo "Testing Zoom transcription setup (10 seconds)..."
echo ""
echo "Speak clearly into your microphone."
echo "If you have Zoom audio playing, it should also be captured."
echo ""

cd "\$MICLOG_PATH"
python -m sidekick.clients.miclog transcribe \\
    --device "\$DEVICE_ID" \\
    --duration 10
EOFTEST

chmod +x "$SCRIPTS_DIR/zoom-transcribe-test.sh"

echo "✓ Created $SCRIPTS_DIR/zoom-transcribe-test.sh"
echo ""

# Update PATH if needed
if [[ ":$PATH:" != *":$SCRIPTS_DIR:"* ]]; then
    echo "Adding $SCRIPTS_DIR to your PATH..."

    SHELL_RC=""
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    fi

    if [ -n "$SHELL_RC" ]; then
        echo "" >> "$SHELL_RC"
        echo "# Zoom transcription scripts" >> "$SHELL_RC"
        echo "export PATH=\"\$PATH:$SCRIPTS_DIR\"" >> "$SHELL_RC"
        echo "✓ Updated $SHELL_RC"
        export PATH="$PATH:$SCRIPTS_DIR"
    fi
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Created helper scripts in $SCRIPTS_DIR:"
echo "  • zoom-transcribe.sh - Start manual transcription"
echo "  • zoom-transcribe-test.sh - Test your setup (10 seconds)"
echo ""
echo "Transcripts will be saved to:"
echo "  $HOME/Documents/Zoom Transcripts/"
echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. TEST YOUR SETUP:"
echo "   Run: zoom-transcribe-test.sh"
echo "   Speak into your microphone and verify it transcribes."
echo ""
echo "2. CONFIGURE ZOOM:"
echo "   Zoom → Settings → Audio"
echo "   Output: Select 'Zoom Output + BlackHole'"
echo ""
echo "3. START TRANSCRIBING:"
echo "   Before your next Zoom meeting, run:"
echo "   zoom-transcribe.sh"
echo ""
echo "   Or with a custom filename:"
echo "   zoom-transcribe.sh ~/my-meeting.txt"
echo ""
echo "4. JOIN ZOOM MEETING:"
echo "   Your microphone still works normally."
echo "   Transcription captures both you and others."
echo ""
echo "5. STOP TRANSCRIBING:"
echo "   Press Ctrl+C when meeting ends."
echo ""
echo "For automatic transcription (advanced), see:"
echo "  $SCRIPT_DIR/ZOOM_INTEGRATION.md"
echo ""
echo "For full documentation:"
echo "  $SCRIPT_DIR/ZOOM_INTEGRATION.md"
echo ""
