import os
import sys
from pathlib import Path

import click

from udown import downloader, version_formatter

class CliProgressHook:
    def __init__(self):
        self.pbar = None
        self.current_video_id = None

    def __call__(self, d):
        if d['status'] == 'downloading':
            video_id = d['info_dict']['id']
            if self.current_video_id != video_id:
                self.current_video_id = video_id
                if self.pbar:
                    self.pbar.finish()
                
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                video_title = d['info_dict']['title']
                self.pbar = click.progressbar(length=total_bytes, label=f"-> Downloading '{video_title}'")
                self.pbar.update(0)

            if self.pbar:
                self.pbar.pos = d['downloaded_bytes']
                self.pbar.render_progress()

        elif d['status'] == 'finished':
            if self.pbar:
                self.pbar.finish()
            click.echo(f"\n -> Download finished: {d['info_dict']['_filename']}")
    
    def close(self):
        if self.pbar:
            self.pbar.finish()

@click.group()
def cli():
    """udown: A command-line tool and web UI to download video playlists."""
    pass

@cli.command()
@click.argument('playlist_urls', nargs=-1)
@click.option('--input-file', '-i', type=click.Path(exists=True, dir_okay=False), help="File containing playlist URLs, one per line.")
@click.option('--output-dir', '-o', default='./downloads', show_default=True, help='Directory to save downloads.', type=click.Path())
@click.option('--quality', '-q', default='best', help='Desired video quality (e.g., "1080p", "720p", "best").')
@click.option('--audio', is_flag=True, default=False, help='Download best audio format (e.g., webm, m4a).')
@click.option('--to-mp3', is_flag=True, default=False, help='Download audio and convert to MP3 (requires ffmpeg).')
@click.option('--name-template', '-t', default='{playlist_index:02d} - {title}.{ext}', help='Custom filename template (ignored if --simple-serial is used).')
@click.option('--simple-serial', is_flag=True, default=False, help='Use simple serial naming (e.g., "01.mp4").')
@click.option('--cookies-file', '-c', help='The path to a cookies file for authentication.', type=click.Path(exists=True))
@click.option('--log-level', '-l', default='info', help='The log level (e.g., debug, info, warning, error).')
@click.option('--save-metadata', '-m', is_flag=True, help='Save playlist and video metadata to a JSON file.')
def download(playlist_urls, input_file, output_dir, quality, audio, to_mp3, name_template, simple_serial, cookies_file, log_level, save_metadata):
    """
    Downloads videos from one or more YouTube playlists.

    PLAYLIST_URLS: One or more YouTube playlist URLs.
    """
    urls = list(playlist_urls)
    if input_file:
        with open(input_file, "r", encoding="utf-8") as f:
            urls.extend(line.strip() for line in f if line.strip())
    if not sys.stdin.isatty():
        urls.extend(line.strip() for line in sys.stdin if line.strip())
    urls = [u.strip() for u in urls if u and u.strip()]
    # De-duplicate while preserving order
    seen = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]

    if not urls:
        click.echo("No playlist URLs provided.")
        return

    base_output_path = Path(output_dir)
    base_output_path.mkdir(parents=True, exist_ok=True)
    
    final_quality = quality
    audio_format = None
    if to_mp3:
        final_quality = 'audio-only'
        audio_format = 'mp3'
    elif audio:
        final_quality = 'audio-only'

    final_template = '{playlist_index:02d}.{ext}' if simple_serial else name_template

    cli_logger = downloader.YtdlpLogger(
        warning_fn=lambda msg: click.secho(f"WARNING: {msg}", fg="yellow"),
        error_fn=lambda msg: click.secho(f"ERROR: {msg}", fg="red")
    )

    for i, url in enumerate(urls, 1):
        click.secho(f"\nProcessing playlist {i}/{len(urls)}: {url}", fg="cyan")
        progress_hook = CliProgressHook()
        try:
            playlist_info = downloader.download_playlist(
                playlist_url=url,
                output_dir=base_output_path,
                quality=final_quality,
                name_template=final_template,
                cookies_file=cookies_file,
                log_level=log_level,
                save_metadata=save_metadata,
                progress_hook=progress_hook,
                logger=cli_logger,
                audio_format=audio_format
            )
            click.secho(f"Successfully downloaded playlist: '{playlist_info['title']}'", fg='green')
        except (ValueError, RuntimeError) as e:
            click.secho(str(e), fg='red')
        finally:
            progress_hook.close()

@cli.command()
@click.option('--host', default=None, help='Host to bind (defaults to $UDOWN_HOST or 127.0.0.1)')
@click.option('--port', default=None, type=int, help='Port to bind (defaults to $UDOWN_PORT or 5000)')
@click.option('--debug/--no-debug', default=None, help='Enable debug mode (defaults to $UDOWN_DEBUG)')
def web(host, port, debug):
    """Starts the udown web interface."""
    from udown.web import main as web_main
    resolved_host = host or os.environ.get("UDOWN_HOST", "127.0.0.1")
    resolved_port = port or int(os.environ.get("UDOWN_PORT", "5000"))
    click.echo("Starting the udown web interface...")
    click.echo(f"Navigate to http://{resolved_host}:{resolved_port} in your browser.")
    web_main(host=host, port=port, debug=debug)


@cli.command()
@click.option('--source-root', default='downloads/quran_Serailler', show_default=True, type=click.Path())
@click.option('--target-root', default='downloads/quran_Serailler_serialized', show_default=True, type=click.Path())
@click.option('--start-version', default=1, show_default=True, type=int)
@click.option('--end-version', default=7, show_default=True, type=int)
@click.option('--include-ext', multiple=True, default=('mp3',), show_default=True, help='Allowed extensions (repeatable), e.g. --include-ext mp3 --include-ext m4a')
def format_versions(source_root, target_root, start_version, end_version, include_ext):
    """Serially copy Version_1..N into one numbered folder for USB players."""
    allowed_suffixes = tuple(f".{ext.lower().lstrip('.')}" for ext in include_ext) if include_ext else ()
    total = version_formatter.format_versions(
        source_root=source_root,
        target_root=target_root,
        start_version=start_version,
        end_version=end_version,
        allowed_suffixes=allowed_suffixes,
    )
    click.echo(f"Formatted {total} files into {target_root}")

if __name__ == '__main__':
    cli()
