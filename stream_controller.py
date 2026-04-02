#!/usr/bin/env python3
"""
RTSP Video Stream Controller with Interactive Playback Controls

Streams a video file to MediaMTX via RTSP, with keyboard controls
for seeking forward/backward.

Controls (on the preview window):
    a  - Rewind 1 seconds
    d  - Fast-forward 1 seconds
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

# ── Configuration ──────────────────────────────────────────────
VIDEO_PATH = "/home/ozzaann/rtsp_stream_vid/gauge/vid_test1.mp4"

RTSP_URL = "rtsp://admin:nppnpg123@localhost:8554/ISAPI/Streaming/channels/1/picture"
RTSP_USER = "admin"
RTSP_PASS = "nppnpg123"
RTSP_PATH = "ISAPI/Streaming/channels/1/picture"
RTSP_PORT = 8554

SEEK_SECONDS = 1        # seconds to seek on a/d keypress
PREVIEW_WINDOW = True   # show local preview window


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


# ── Globals ────────────────────────────────────────────────────
ffmpeg_process = None


def cleanup(*args):
    """Graceful shutdown."""
    global ffmpeg_process
    print("\n[INFO] Shutting down...")
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
    cv2.destroyAllWindows()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


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


def main():
    global ffmpeg_process

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
    print("  RTSP Video Stream Controller")
    print("=" * 60)
    print(f"  Video    : {os.path.basename(VIDEO_PATH)}")
    print(f"  Size     : {width}x{height} @ {fps:.1f} FPS")
    print(f"  Duration : {duration:.1f} seconds ({total_frames} frames)")
    print("-" * 60)
    print(f"  ▶ RTSP Address (gunakan ini untuk streaming):")
    print(f"    {rtsp_address}")
    print("-" * 60)
    print("  Controls:")
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
    print("[INFO] Press [S] to play/pause, [A]/[D] to seek, [Q] to quit.\n")

    frame_delay = 1.0 / fps

    # ── Read first frame (paused state) ───────────────────────
    ret, frame = cap.read()
    if not ret:
        print("[ERROR] Cannot read first frame.")
        sys.exit(1)

    # Seek back to frame 0 so position stays at 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    current_pos = 0

    # ── Create resizable preview window ───────────────────────
    if PREVIEW_WINDOW:
        cv2.namedWindow("RTSP Stream Controller", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("RTSP Stream Controller", 960, 540)

    playing = False  # start paused

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
                    print("[INFO] Video looped back to start.")
                else:
                    current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                if ret:
                    frame = new_frame_data

            # ── Send current (static) frame to FFmpeg ─────────
            try:
                ffmpeg_process.stdin.write(frame.tobytes())
            except BrokenPipeError:
                stderr = ffmpeg_process.stderr.read().decode()
                print(f"[ERROR] FFmpeg pipe broken:\n{stderr[-500:]}")
                break

            # ── Show preview ──────────────────────────────────
            if PREVIEW_WINDOW:
                current_time = current_pos / fps

                # Draw overlay info
                display = frame.copy()
                state_text = "PLAYING" if playing else "PAUSED"
                info_text = f"Time:{current_time:.1f}s/{duration:.1f}s [{state_text}]"
                cv2.putText(
                    display, info_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2,
                )

                cv2.imshow("RTSP Stream Controller", display)

            # ── Handle keyboard ───────────────────────────────
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                print("[INFO] Quit requested.")
                break

            elif key == ord("s"):
                # Toggle play/pause
                playing = not playing
                if playing:
                    print("[PLAY] ▶ Video playing")
                else:
                    print("[PAUSE] ⏸ Video paused")

            elif key == ord("a"):
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
                print(f"[SEEK] ◀◀ Rewind to {new_time:.1f}s")

            elif key == ord("d"):
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
