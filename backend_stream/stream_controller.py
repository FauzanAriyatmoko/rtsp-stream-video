#!/usr/bin/env python3
"""
RTSP Video Stream Controller (Headless / No GUI)
=================================================
Streams a video file to MediaMTX via RTSP, with keyboard controls
for seeking forward/backward. Runs entirely in terminal — no display needed.

Controls (terminal keyboard):
    s  - Play / Pause toggle
    a  - Rewind 1 second
    d  - Fast-forward 1 second
    q  - Quit

RTSP URL: rtsp://admin:nppnpg123@localhost:8554/ISAPI/Streaming/channels/1/picture
"""

import cv2
import subprocess
import sys
import time
import signal
import socket
import os
import select
import termios
import tty
import shutil
import yaml

# ── Resolve paths relative to this script ─────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

MEDIAMTX_BIN = os.path.join(SCRIPT_DIR, "mediamtx")
MEDIAMTX_CONF = os.path.join(SCRIPT_DIR, "mediamtx.yml")

# ── Load Configuration from YAML ──────────────────────────────
CONFIG_PATH = os.path.join(PROJECT_DIR, "config", "stream_config.yaml")


def load_config(config_path):
    """Load configuration from YAML file."""
    if not os.path.isfile(config_path):
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg


_cfg = load_config(CONFIG_PATH)

VIDEO_PATH = _cfg["video"]["path"]

RTSP_URL = _cfg["rtsp"]["url"]
RTSP_USER = _cfg["rtsp"]["user"]
RTSP_PASS = _cfg["rtsp"]["password"]
RTSP_PATH = _cfg["rtsp"]["path"]
RTSP_PORT = _cfg["rtsp"]["port"]

SEEK_SECONDS = _cfg["controls"]["seek_seconds"]
STATUS_INTERVAL = _cfg["controls"]["status_interval"]


def get_local_ip():
    """Get the local IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ── Pre-flight checks ─────────────────────────────────────────
def preflight_checks():
    """Verify that required dependencies are available."""
    errors = []
    if not os.path.isfile(MEDIAMTX_BIN):
        errors.append(
            f"MediaMTX binary not found at: {MEDIAMTX_BIN}\n"
            f"       Run: bash setup_mediamtx.sh"
        )
    if not shutil.which("ffmpeg"):
        errors.append(
            "ffmpeg not found. Install with: sudo apt install ffmpeg -y"
        )
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        sys.exit(1)


def start_mediamtx():
    """Start the MediaMTX server as a background process and return the Popen."""
    print("[INFO] Starting MediaMTX server...")
    proc = subprocess.Popen(
        [MEDIAMTX_BIN, MEDIAMTX_CONF],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    # Give it a moment to initialise
    time.sleep(2)
    if proc.poll() is not None:
        stderr = proc.stderr.read().decode(errors="replace")
        print(f"[ERROR] MediaMTX failed to start:\n{stderr}")
        sys.exit(1)
    print(f"[OK]   MediaMTX running (PID: {proc.pid})")
    return proc


# ── Globals ────────────────────────────────────────────────────
mediamtx_process = None
ffmpeg_process = None
original_term_settings = None


def restore_terminal():
    """Restore original terminal settings."""
    global original_term_settings
    if original_term_settings is not None:
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN,
                              original_term_settings)
        except Exception:
            pass


def cleanup(*args):
    """Graceful shutdown — stop FFmpeg and MediaMTX."""
    global ffmpeg_process, mediamtx_process
    restore_terminal()
    print("\n[INFO] Shutting down...")
    # Stop FFmpeg
    if ffmpeg_process and ffmpeg_process.poll() is None:
        try:
            ffmpeg_process.stdin.close()
        except Exception:
            pass
        try:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=3)
        except Exception:
            ffmpeg_process.kill()
        print("[OK]   FFmpeg stopped.")
    # Stop MediaMTX
    if mediamtx_process and mediamtx_process.poll() is None:
        try:
            mediamtx_process.terminate()
            mediamtx_process.wait(timeout=3)
        except Exception:
            mediamtx_process.kill()
        print("[OK]   MediaMTX stopped.")
    print("[DONE] All services stopped.")
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def setup_terminal_raw():
    """Set terminal to raw mode for single-keypress reading."""
    global original_term_settings
    try:
        original_term_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
    except Exception:
        # If stdin is not a terminal (e.g. piped), skip raw mode
        original_term_settings = None


def read_key():
    """Non-blocking read a single key from terminal. Returns None if no key."""
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read(1)
    return None


def start_ffmpeg(width, height, fps):
    """Start FFmpeg subprocess to push frames to MediaMTX via RTSP."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",                    # read from stdin
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", str(int(fps * 2)),      # keyframe every 2 seconds
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        RTSP_URL,
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    return proc


def print_status(current_pos, total_frames, fps, duration, playing):
    """Print status line in terminal (in-place update using \\r)."""
    current_time = current_pos / fps
    state = "▶ PLAYING" if playing else "⏸ PAUSED "
    bar_width = 30
    progress = current_pos / total_frames if total_frames > 0 else 0
    filled = int(bar_width * progress)
    bar = "█" * filled + "░" * (bar_width - filled)

    status = (
        f"\r  [{state}] "
        f"{current_time:6.1f}s / {duration:.1f}s "
        f"|{bar}| "
        f"Frame {current_pos}/{total_frames}  "
    )
    sys.stdout.write(status)
    sys.stdout.flush()


def main():
    global ffmpeg_process, mediamtx_process

    # ── Pre-flight checks ─────────────────────────────────────
    preflight_checks()

    # ── Start MediaMTX ────────────────────────────────────────
    mediamtx_process = start_mediamtx()
    print()

    # ── Open video ─────────────────────────────────────────────
    if not os.path.isfile(VIDEO_PATH):
        print(f"[ERROR] Video file not found: {VIDEO_PATH}")
        sys.exit(1)

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {VIDEO_PATH}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    local_ip = get_local_ip()
    rtsp_address = f"rtsp://{RTSP_USER}:{RTSP_PASS}@{local_ip}:{RTSP_PORT}/{RTSP_PATH}"

    print("=" * 60)
    print("  RTSP Video Stream Controller (Headless)")
    print("=" * 60)
    print(f"  Video    : {os.path.basename(VIDEO_PATH)}")
    print(f"  Size     : {width}x{height} @ {fps:.1f} FPS")
    print(f"  Duration : {duration:.1f} seconds ({total_frames} frames)")
    print("-" * 60)
    print(f"  ▶ RTSP Stream URL (gunakan ini untuk streaming):")
    print(f"    {rtsp_address}")
    print("-" * 60)
    print("  Controls (ketik langsung, tanpa Enter):")
    print(f"    [s] Play / Pause")
    print(f"    [a] Rewind {SEEK_SECONDS} second(s)")
    print(f"    [d] Fast-forward {SEEK_SECONDS} second(s)")
    print("    [q] Quit")
    print("=" * 60)

    # ── Start FFmpeg ───────────────────────────────────────────
    print("\n[INFO] Starting FFmpeg encoder → MediaMTX...")
    ffmpeg_process = start_ffmpeg(width, height, fps)
    time.sleep(1)

    # Check if FFmpeg started successfully
    if ffmpeg_process.poll() is not None:
        stderr = ffmpeg_process.stderr.read().decode()
        print(f"[ERROR] FFmpeg failed to start:\n{stderr}")
        sys.exit(1)

    print("[INFO] Streaming started! Video is PAUSED.")
    print("[INFO] Tekan [s] untuk play/pause, [a]/[d] untuk seek, [q] untuk quit.\n")

    frame_delay = 1.0 / fps

    # ── Read first frame (paused state) ───────────────────────
    ret, frame = cap.read()
    if not ret:
        print("[ERROR] Cannot read first frame.")
        sys.exit(1)

    # Seek back to frame 0 so position stays at 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    current_pos = 0

    playing = False  # start paused

    # ── Setup terminal raw mode ───────────────────────────────
    setup_terminal_raw()

    last_status_time = 0

    # ── Main loop ─────────────────────────────────────────────
    try:
        while True:
            loop_start = time.time()

            # ── Auto-advance if playing ───────────────────────
            if playing:
                ret, new_frame_data = cap.read()
                if not ret:
                    # Reached end, loop back
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, new_frame_data = cap.read()
                    current_pos = 0
                    sys.stdout.write("\n")
                    print("[INFO] Video looped back to start.")
                else:
                    current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                if ret:
                    frame = new_frame_data

            # ── Send current frame to FFmpeg ──────────────────
            try:
                ffmpeg_process.stdin.write(frame.tobytes())
            except BrokenPipeError:
                stderr = ffmpeg_process.stderr.read().decode()
                sys.stdout.write("\n")
                print(f"[ERROR] FFmpeg pipe broken:\n{stderr[-500:]}")
                break

            # ── Print status periodically ─────────────────────
            now = time.time()
            if now - last_status_time >= STATUS_INTERVAL:
                print_status(current_pos, total_frames, fps, duration, playing)
                last_status_time = now

            # ── Handle keyboard (non-blocking) ────────────────
            key = read_key()

            if key == "q":
                sys.stdout.write("\n")
                print("[INFO] Quit requested.")
                break

            elif key == "s":
                # Toggle play/pause
                playing = not playing
                sys.stdout.write("\n")
                if playing:
                    print("[PLAY] ▶ Video playing")
                else:
                    print("[PAUSE] ⏸ Video paused")

            elif key == "a":
                # Rewind
                playing = False  # pause when seeking
                seek_frames = int(SEEK_SECONDS * fps)
                new_frame = max(0, current_pos - seek_frames)
                cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    new_frame = 0
                current_pos = new_frame
                new_time = current_pos / fps
                sys.stdout.write("\n")
                print(f"[SEEK] ◀◀ Rewind to {new_time:.1f}s")

            elif key == "d":
                # Fast-forward
                playing = False  # pause when seeking
                seek_frames = int(SEEK_SECONDS * fps)
                new_frame = min(total_frames - 1, current_pos + seek_frames)
                cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 2)
                    ret, frame = cap.read()
                    new_frame = total_frames - 2
                current_pos = new_frame
                new_time = current_pos / fps
                sys.stdout.write("\n")
                print(f"[SEEK] ▶▶ Forward to {new_time:.1f}s")

            # ── Frame rate control ────────────────────────────
            elapsed = time.time() - loop_start
            sleep_time = frame_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
