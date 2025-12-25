# udown

`udown` is a small Python app that downloads YouTube playlists (CLI + web UI) using `yt-dlp`, then helps you reshape those downloads into a USB-friendly, serially numbered folder for simple audio players.

## Backstory

I originally built this to archive multiple Qur’an playlist series for a client who needed a single USB stick that “just plays in order” in a living‑room audio system. The constraint was surprisingly strict: the device sorts tracks by filename, so every file had to be renamed and merged into one clean, sequential list—no gaps, no weird characters, no surprises.

## Features

- Download entire YouTube playlists into a dedicated folder per playlist
- CLI and web UI (Flask) for the same core workflow
- Quality selection (video or audio-only) via `yt-dlp`
- Optional MP3 conversion (FFmpeg required)
- Robust naming: avoids filename template failures and accidental overwrites
- “Version formatter”: merges `Version_1..Version_7` into one sequential, USB‑player‑friendly folder

## Requirements

- Python 3.10+ recommended
- `yt-dlp`
- For YouTube extraction reliability:
  - A JavaScript runtime (`node` recommended)
  - `yt-dlp` remote components for EJS challenges (the app enables `ejs:github` automatically when a JS runtime is detected)
- FFmpeg (required for MP3 conversion and optional remuxing)

## Install

From the repo root:

```bash
pip install -e .
```

## CLI Usage

### Download playlists

```bash
udown download "https://www.youtube.com/playlist?list=..." -o ./downloads --to-mp3
```

Useful options:

- `--quality best|1080p|720p`
- `--audio` (audio-only, keep original container)
- `--to-mp3` (audio-only + convert to mp3; requires FFmpeg)
- `--simple-serial` (forces simple numbering template)
- `--name-template "{playlist_index:02d} - {title}.{ext}"`

### Start the web UI

```bash
udown web --host 127.0.0.1 --port 5000
```

Environment variables:

- `UDOWN_HOST` (default `127.0.0.1`)
- `UDOWN_PORT` (default `5000`)
- `UDOWN_DEBUG` (`1/true/yes/on` enables debug)

### Format “Version_1..Version_7” for a USB player

By default, the formatter expects:

```
downloads/quran_Serailler/
  Version_1/
  Version_2/
  ...
  Version_7/
```

Run:

```bash
udown format-versions \
  --source-root downloads/quran_Serailler \
  --target-root downloads/quran_Serailler_serialized \
  --start-version 1 \
  --end-version 7
```

Result:

- A single folder containing `001 - ... .mp3`, `002 - ... .mp3`, etc.
- Names are ASCII-safe and length-limited to reduce issues on simple players.

If you need to include other audio containers:

```bash
udown format-versions --include-ext mp3 --include-ext m4a
```

## Web Usage

- Start: `udown web`
- Open: `http://127.0.0.1:5000/`
- Use the navbar to switch between:
  - **Downloader**
  - **Version formatter**

The web downloader streams progress via Server-Sent Events (SSE) and supports multiple downloads without mixing logs.

## Notes / Troubleshooting

- **“No supported JavaScript runtime could be found”**
  - Install Node (macOS: `brew install node`) and ensure `node` is on your PATH.
- **MP3 conversion warning**
  - Install FFmpeg (macOS: `brew install ffmpeg`).
- **Some formats may be missing**
  - YouTube frequently changes extraction requirements; keep `yt-dlp` updated.

## Disclaimer

Use this tool responsibly and comply with YouTube’s Terms of Service and local laws. This project is intended for personal archiving and offline playback of content you have the rights to download.

