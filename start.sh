#!/bin/bash
# ================================================
#  RTSP Video Stream - Start Script
#  Starts MediaMTX + Python stream controller
# ================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MEDIAMTX_BIN="${SCRIPT_DIR}/mediamtx"
MEDIAMTX_CONF="${SCRIPT_DIR}/mediamtx.yml"
VENV_DIR="${SCRIPT_DIR}/.stream"
STREAM_SCRIPT="${SCRIPT_DIR}/stream_controller.py"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ── Pre-checks ────────────────────────────────────────────────
if [ ! -f "$MEDIAMTX_BIN" ]; then
    echo -e "${RED}[ERROR]${NC} MediaMTX binary not found."
    echo "       Run: bash setup_mediamtx.sh"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}[ERROR]${NC} Virtual environment not found at ${VENV_DIR}"
    exit 1
fi

if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} ffmpeg not found. Install with: sudo apt install ffmpeg -y"
    exit 1
fi

# ── Cleanup function ─────────────────────────────────────────
MEDIAMTX_PID=""

cleanup() {
    echo ""
    echo -e "${YELLOW}[INFO]${NC} Stopping services..."
    
    # Kill MediaMTX
    if [ -n "$MEDIAMTX_PID" ] && kill -0 "$MEDIAMTX_PID" 2>/dev/null; then
        kill "$MEDIAMTX_PID" 2>/dev/null
        wait "$MEDIAMTX_PID" 2>/dev/null
        echo -e "${GREEN}[OK]${NC} MediaMTX stopped."
    fi
    
    echo -e "${GREEN}[DONE]${NC} All services stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# ── Start MediaMTX ────────────────────────────────────────────
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  RTSP Video Streaming System${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

echo -e "${YELLOW}[1/2]${NC} Starting MediaMTX server..."
"$MEDIAMTX_BIN" "$MEDIAMTX_CONF" &
MEDIAMTX_PID=$!

# Wait for MediaMTX to be ready
sleep 2

if ! kill -0 "$MEDIAMTX_PID" 2>/dev/null; then
    echo -e "${RED}[ERROR]${NC} MediaMTX failed to start."
    exit 1
fi

echo -e "${GREEN}[OK]${NC} MediaMTX running (PID: $MEDIAMTX_PID)"
echo ""

# ── Get local IP ──────────────────────────────────────────────
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="localhost"
fi

echo -e "${GREEN}  RTSP Stream URL:${NC}"
echo -e "  ${YELLOW}rtsp://admin:nppnpg123@${LOCAL_IP}:8554/ISAPI/Streaming/channels/1/picture${NC}"
echo ""

# ── Start Python stream controller ───────────────────────────
echo -e "${YELLOW}[2/2]${NC} Starting stream controller..."
echo ""

source "${VENV_DIR}/bin/activate"
python3 "$STREAM_SCRIPT"
