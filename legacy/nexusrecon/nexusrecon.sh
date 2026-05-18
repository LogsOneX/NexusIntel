#!/bin/bash
# NexusRecon - Quick Start Script

echo "╔════════════════════════════════════════╗"
echo "║   NexusRecon - Advanced OSINT Tool    ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check if username is provided
if [ -z "$1" ]; then
    echo "Usage: ./nexusrecon.sh <username> [options]"
    echo ""
    echo "Examples:"
    echo "  ./nexusrecon.sh john_doe"
    echo "  ./nexusrecon.sh john_doe --save"
    echo "  ./nexusrecon.sh john_doe --timeout 5 --workers 30 --save"
    exit 1
fi

# Install dependencies if needed
if ! python3 -c "import aiohttp" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install aiohttp --quiet
fi

# Run the scanner
python3 main.py "$@"
