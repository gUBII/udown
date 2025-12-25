import click
from pathlib import Path
import sys
from udown import downloader

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
@click.option('--output-dir', '-o', default='.', help='The directory to save the downloaded videos.', type=click.Path())
@click.option('--quality', '-q', default='best', help='Desired video quality (e.g., "1080p", "720p", "best").')
@click.option('--audio', is_flag=True, default=False, help='Download audio only, overrides --quality.')
@click.option('--name-template', '-t', default='{playlist_index:02d} - {title}.{ext}', help='Custom filename template (ignored if --simple-serial is used).')
@click.option('--simple-serial', is_flag=True, default=False, help='Use simple serial naming (e.g., "01.mp4").')
@click.option('--cookies-file', '-c', help='The path to a cookies file for authentication.', type=click.Path(exists=True))
@click.option('--log-level', '-l', default='info', help='The log level (e.g., debug, info, warning, error).')
@click.option('--save-metadata', '-m', is_flag=True, help='Save playlist and video metadata to a JSON file.')
def download(playlist_urls, input_file, output_dir, quality, audio, name_template, simple_serial, cookies_file, log_level, save_metadata):
    """
    Downloads videos from one or more YouTube playlists.

    PLAYLIST_URLS: One or more YouTube playlist URLs.
    """
    urls = list(playlist_urls)
    if input_file:
        with open(input_file, 'r') as f:
            urls.extend(line.strip() for line in f if line.strip())

    if not urls and not sys.stdin.isatty():
        urls.extend(line.strip() for line in sys.stdin if line.strip())

    if not urls:
        click.echo("No playlist URLs provided. Please provide URLs as arguments, via --input-file, or through stdin.")
        return

    base_output_path = Path(output_dir)
    base_output_path.mkdir(parents=True, exist_ok=True)
    
    final_quality = 'audio-only' if audio else quality
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
                logger=cli_logger
            )
            click.secho(f"Successfully downloaded playlist: '{playlist_info['title']}'", fg='green')
        except (ValueError, RuntimeError) as e:
            click.secho(str(e), fg='red')
        finally:
            progress_hook.close()

@cli.command()
def web():
    """Starts the udown web interface."""
    from udown import web
    click.echo("Starting the udown web interface...")
    click.echo("Navigate to http://127.0.0.1:5000 in your browser.")
    web.main()

if __name__ == '__main__':
    cli()

