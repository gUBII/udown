import yt_dlp
from pathlib import Path
import json
import certifi

class YtdlpLogger:
    def __init__(self, debug_fn=None, warning_fn=None, error_fn=None):
        self._debug = debug_fn or (lambda msg: None)
        self._warning = warning_fn or (lambda msg: None)
        self._error = error_fn or (lambda msg: None)

    def debug(self, msg):
        self._debug(msg)

    def warning(self, msg):
        self._warning(msg)

    def error(self, msg):
        self._error(msg)

def get_format_selection(quality: str) -> str:
    """Returns the yt-dlp format selection string based on the quality."""
    if quality == 'audio-only':
        return 'bestaudio/best'
    if quality == 'best':
        return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    if quality.endswith('p'):
        height = quality[:-1]
        return f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best'
    return quality

def sanitize_filename(name):
    """Sanitize a string to be a valid filename."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '.', '_')).rstrip()

def _get_common_opts(progress_hook, cookies_file, log_level, logger):
    opts = {
        'quiet': True,
        'progress_hooks': [progress_hook],
        'continuedl': True,
        'ignoreerrors': True,
        'logger': logger,
        'http_headers': {'User-Agent': 'Mozilla/5.0'},
        'nocheckcertificate': False,
        'ca_file': certifi.where(),
    }
    if cookies_file:
        opts['cookiefile'] = cookies_file
    if log_level == 'debug':
        opts['quiet'] = False
    return opts

def download_playlist(playlist_url: str, output_dir: Path, quality: str, name_template: str, 
                      cookies_file: str, log_level: str, save_metadata: bool, progress_hook, logger, audio_format: str = None):
    """Downloads a single YouTube playlist."""
    
    common_opts = _get_common_opts(progress_hook, cookies_file, log_level, logger)
    
    # First, extract all video information from the playlist
    info_opts = {**common_opts, 'extract_flat': False, 'force_generic_extractor': False}
    
    try:
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(f"Fatal error fetching playlist info: {e}")

    if not playlist_info or 'title' not in playlist_info:
        raise ValueError(f"Could not retrieve playlist information for {playlist_url}. Check the URL or cookies.")
        
    playlist_title = sanitize_filename(playlist_info['title'])
    playlist_output_path = output_dir / playlist_title
    playlist_output_path.mkdir(parents=True, exist_ok=True)

    if save_metadata:
        (playlist_output_path / "playlist_metadata.json").write_text(json.dumps(playlist_info, indent=4))

    if not playlist_info.get('entries'):
        logger.warning(f"Playlist '{playlist_title}' appears to be empty. Nothing to download.")
        return playlist_info

    # Loop through entries and create a new downloader instance for each video.
    # This is more robust than reusing an instance.
    for entry in playlist_info.get('entries', []):
        if not entry:
            logger.warning("Skipping an empty entry in the playlist.")
            continue

        playlist_index = entry.get('playlist_index')
        if playlist_index is None:
            logger.warning(f"Could not find a playlist index for video '{entry.get('title', entry.get('id'))}'. Skipping.")
            continue
        
        download_opts = {
            **common_opts,
            'format': get_format_selection(quality),
            'outtmpl': str(playlist_output_path / name_template),
            'playlist_items': str(playlist_index),
        }

        if audio_format == 'mp3':
            logger.warning("MP3 conversion requires FFmpeg to be installed on your system.")
            download_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        try:
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                ydl.download([playlist_url])
        except Exception as e:
            logger.error(f"Failed to download video #{playlist_index}: {e}")

    return playlist_info
