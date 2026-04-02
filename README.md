# RTSP Video Streaming with MediaMTX (Headless)

Stream video file via RTSP menggunakan MediaMTX server, dengan kontrol interaktif maju/mundur.
**Berjalan sepenuhnya di terminal** — tidak membutuhkan GUI/display (in server).

Video **tidak auto-play** — diam di frame pertama sampai ditekan tombol `s` untuk play.

## Struktur File

```
rtsp_stream_vid/
├── mediamtx.yml           # Konfigurasi MediaMTX (auth + path)
├── stream_controller.py   # Python script: streaming + kontrol (headless)
├── start.sh               # Launcher (MediaMTX + controller)
├── mediamtx               # MediaMTX binary (auto-download)
├── .stream/               # Python virtual environment
└── gauge/
    └── vid_test1.mp4
```

## Setup

### 1. Download MediaMTX

```bash
bash setup_mediamtx.sh
```

### 2. Install Dependencies

```bash
source .stream/bin/activate
pip install opencv-python
```

### 3. FFmpeg

```bash
sudo apt install ffmpeg -y
```

## Cara Menjalankan

```bash
bash start.sh
```

Script akan:
1. Start MediaMTX server di background
2. Menampilkan **RTSP URL** yang bisa digunakan untuk computer vision
3. Video **diam di frame pertama** sampai ditekan `s`
4. Semua kontrol melalui **terminal** (tanpa GUI)

## Kontrol

Tekan tombol langsung di **terminal** (perlu Enter):

| Tombol | Fungsi                        |
|--------|-------------------------------|
| `s`    | Play / Pause toggle           |
| `a`    | Mundur 1 detik                |
| `d`    | Maju 1 detik                  |
| `q`    | Keluar / Stop streaming       |

> **Note:** Saat seek (`a`/`d`), video otomatis pause. Tekan `s` untuk melanjutkan play.

## RTSP URL

URL akan otomatis ditampilkan saat menjalankan `start.sh`, formatnya:

```
rtsp://admin:nppnpg123@<IP_ADDRESS>:8554/ISAPI/Streaming/channels/1/picture
```

### Menggunakan untuk Computer Vision (Python)

```python
import cv2
cap = cv2.VideoCapture("rtsp://admin:nppnpg123@<IP>:8554/ISAPI/Streaming/channels/1/picture")
while True:
    ret, frame = cap.read()
    if not ret:
        break
```

### Menonton Stream

**VLC:**
```
Media → Open Network Stream → masukkan RTSP URL
```

**ffplay:**
```bash
ffplay rtsp://admin:nppnpg123@<IP>:8554/ISAPI/Streaming/channels/1/picture
```

## Catatan

- Video asli di-re-encode ke **H.264** secara real-time oleh FFmpeg
- Authentication: `admin` / `nppnpg123`
- Program berjalan **headless** — tidak membutuhkan X11/Wayland/display
- Cocok untuk dijalankan di **server** atau melalui **SSH**
