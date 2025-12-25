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
        # yt-dlp sends a lot of debug info, we can filter it here if needed
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

def download_playlist(playlist_url: str, output_dir: Path, quality: str, name_template: str, 
                      cookies_file: str, log_level: str, save_metadata: bool, progress_hook, logger):
    """Downloads a single YouTube playlist."""
    
    common_opts = {
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
        common_opts['cookiefile'] = cookies_file
    if log_level == 'debug':
        common_opts['quiet'] = False

    ydl_opts_info = {
        **common_opts,
        'extract_flat': 'in_playlist',
        'force_generic_extractor': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
        try:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            if not playlist_info or 'title' not in playlist_info:
                raise ValueError(f"Could not retrieve playlist information for {playlist_url}. Check the URL.")
            playlist_title = sanitize_filename(playlist_info['title'])
        except yt_dlp.utils.DownloadError as e:
            raise RuntimeError(f"Error fetching playlist info for {playlist_url}: {e}")
            
    playlist_output_path = output_dir / playlist_title
    playlist_output_path.mkdir(parents=True, exist_ok=True)

    if save_metadata:
        metadata_path = playlist_output_path / "playlist_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(playlist_info, f, indent=4)

    ydl_opts_download = {
        **common_opts,
        'format': get_format_selection(quality),
        'outtmpl': str(playlist_output_path / name_template),
    }

    with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
        ydl.download([playlist_url])

    return playlist_info
