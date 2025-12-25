import yt_dlp
from pathlib import Path
import json
import certifi
import shutil

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
    js_runtime_map = {}
    # Prefer local runtimes to silence yt-dlp warnings and unlock more formats.
    # yt-dlp expects a dict: {runtime_name: {config}}; empty config uses PATH.
    for runtime in ('node', 'deno'):
        runtime_path = shutil.which(runtime)
        if runtime_path:
            js_runtime_map[runtime] = {'path': runtime_path}

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
    if js_runtime_map:
        opts['js_runtimes'] = js_runtime_map
        # Enable EJS solver from GitHub to satisfy YouTube's JS challenges
        opts['remote_components'] = ['ejs:github']
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

    entries = list(playlist_info.get('entries') or [])
    if not entries:
        logger.warning(f"Playlist '{playlist_title}' appears to be empty. Nothing to download.")
        return playlist_info

    # Build filenames ourselves to avoid relying on yt-dlp playlist context,
    # then let yt-dlp fill in the final extension based on the selected format.
    for pos, entry in enumerate(entries, start=1):
        if not entry:
            logger.warning("Skipping an empty entry in the playlist.")
            continue

        p_index = entry.get('playlist_index') or pos
        title = sanitize_filename(entry.get('title') or entry.get('id') or f"video_{p_index}")

        filename = name_template
        filename = filename.replace('{playlist_index:02d}', f'{p_index:02d}')
        filename = filename.replace('{playlist_index}', str(p_index))
        filename = filename.replace('{title}', title)

        # Keep extension dynamic so yt-dlp can decide based on the actual format
        if '{ext}' in filename:
            filename = filename.replace('{ext}', '%(ext)s')
        elif '%(ext)s' not in filename:
            filename = f"{filename}.%(ext)s"

        final_outtmpl = str(playlist_output_path / filename)

        download_opts = {
            **common_opts,
            'format': get_format_selection(quality),
            'outtmpl': {'default': final_outtmpl},
            'overwrites': False,  # avoid clobbering if anything goes wrong with naming
        }

        postprocessors = []
        ffmpeg_present = bool(shutil.which('ffmpeg'))
        if audio_format == 'mp3':
            if not ffmpeg_present:
                logger.warning("MP3 conversion requires FFmpeg to be installed on your system.")
            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            })
        else:
            # Remux to mp4 locally to normalize extension/container when formats differ
            if ffmpeg_present:
                postprocessors.append({
                    'key': 'FFmpegVideoRemuxer',
                    'preferredformat': 'mp4',
                })
                download_opts['merge_output_format'] = 'mp4'

        if postprocessors:
            download_opts['postprocessors'] = postprocessors

        video_url = entry.get('webpage_url') or entry.get('url') or (f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get('id') else None)
        if not video_url:
            logger.error(f"Failed to determine URL for playlist item at position {p_index}.")
            continue

        try:
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                ydl.download([video_url])
        except Exception as e:
            logger.error(f"Failed to download video '{entry.get('title') or entry.get('id') or p_index}': {e}")

    return playlist_info
