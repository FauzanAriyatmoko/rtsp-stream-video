# RTSP Video Streaming with MediaMTX

Stream video file via RTSP menggunakan MediaMTX server, dengan kontrol interaktif maju/mundur.

Video **tidak auto-play** — diam di frame pertama sampai ditekan tombol `a` atau `d`.

## Struktur File

```
rtsp_stream_vid/
├── setup_mediamtx.sh      # Download MediaMTX binary
├── mediamtx.yml           # Konfigurasi MediaMTX (auth + path)
├── stream_controller.py   # Python script: streaming + kontrol
├── start.sh               # Launcher (MediaMTX + controller)
├── mediamtx               # MediaMTX binary (auto-download)
├── .stream/               # Python virtual environment
└── video/
    └── 2026-02-19_12-45-47_VehicleID_1637.mp4
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
2. Menampilkan **RTSP URL** yang bisa digunakan
3. Membuka preview window (resizable, default 960x540)
4. Video **diam di frame pertama** sampai ditekan `a` atau `d`

## Kontrol

Tekan tombol di **preview window**:

| Tombol | Fungsi                        |
|--------|-------------------------------|
| `a`    | Mundur 1 detik                |
| `d`    | Maju 1 detik                  |
| `q`    | Keluar / Stop streaming       |

> **Note:** Video tidak berjalan otomatis. Setiap tekan `a`/`d` memindahkan posisi 1 detik, lalu berhenti lagi.

## RTSP URL

URL akan otomatis ditampilkan saat menjalankan `start.sh`, formatnya:

```
rtsp://admin:nppnpg123@<IP_ADDRESS>:8554/ISAPI/Streaming/channels/1/picture
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

**OpenCV (Python):**
```python
import cv2
cap = cv2.VideoCapture("rtsp://admin:nppnpg123@<IP>:8554/ISAPI/Streaming/channels/1/picture")
```

## Catatan

- Video asli menggunakan codec **MPEG-4 Part 2** → di-re-encode ke **H.264** secara real-time oleh FFmpeg
- Authentication: `admin` / `nppnpg123`
- Preview window bisa di-resize dengan drag
