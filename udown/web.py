from flask import Flask, render_template, request, Response
from pathlib import Path
import json
import queue
import threading
from udown import downloader
from udown import version_formatter

app = Flask(__name__)
# In-memory queue to hold progress messages
progress_queue = queue.Queue()

class WebProgressHook:
    def __init__(self, queue):
        self.queue = queue
        self.current_video_id = None

    def __call__(self, d):
        if d['status'] == 'downloading':
            video_id = d['info_dict']['id']
            if self.current_video_id != video_id:
                self.current_video_id = video_id
                video_title = d['info_dict']['title']
                self.queue.put(f"event: new_video\ndata: {video_title}\n\n")

            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            progress = (downloaded_bytes / total_bytes) * 100 if total_bytes > 0 else 0
            
            progress_data = {
                "video_id": video_id,
                "progress": f"{progress:.1f}",
                "speed": d.get('_speed_str', 'N/A'),
                "eta": d.get('_eta_str', 'N/A')
            }
            self.queue.put(f"event: progress\ndata: {json.dumps(progress_data)}\n\n")

        elif d['status'] == 'finished':
            self.queue.put(f"event: message\ndata: Download finished: {d['info_dict']['_filename']}\n\n")
    
    def close(self):
        pass


def download_task(playlist_url, options, progress_hook, logger):
    try:
        progress_queue.put("event: message\ndata: Starting download...\n\n")
        playlist_info = downloader.download_playlist(
            playlist_url=playlist_url,
            output_dir=Path(options['output_dir']),
            quality=options['quality'],
            name_template=options['name_template'],
            cookies_file=options.get('cookies_file'),
            log_level='info',
            save_metadata=options.get('save_metadata', False),
            progress_hook=progress_hook,
            logger=logger,
            audio_format=options.get('audio_format')
        )
        progress_queue.put(f"event: message\ndata: Successfully downloaded playlist: '{playlist_info['title']}'\n\n")
    except (ValueError, RuntimeError, Exception) as e:
        progress_queue.put(f"event: error\ndata: {str(e)}\n\n")
    finally:
        progress_queue.put("event: finished\ndata: close\n\n")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/format')
def format_page():
    return render_template('version_formatter.html')

@app.route('/download', methods=['POST'])
def start_download():
    playlist_url = request.form['playlist_url']
    if not playlist_url:
        return {"error": "Playlist URL is required."}, 400

    quality = request.form.get('quality', 'best')
    audio_format = None
    if 'to_mp3' in request.form:
        quality = 'audio-only'
        audio_format = 'mp3'
    elif 'audio_only' in request.form:
        quality = 'audio-only'

    use_simple_serial = 'simple_serial' in request.form
    name_template = '{playlist_index:02d}.{ext}' if use_simple_serial else request.form.get('name_template', '{playlist_index:02d} - {title}.{ext}')

    options = {
        'output_dir': request.form.get('output_dir', './downloads'),
        'quality': quality,
        'name_template': name_template,
        'save_metadata': 'save_metadata' in request.form,
        'audio_format': audio_format,
    }

    progress_hook = WebProgressHook(progress_queue)
    
    web_logger = downloader.YtdlpLogger(
        warning_fn=lambda msg: progress_queue.put(f"event: message\ndata: ⚠️ WARN: {msg}\n\n"),
        error_fn=lambda msg: progress_queue.put(f"event: message\ndata: ❌ ERROR: {msg}\n\n")
    )

    thread = threading.Thread(target=download_task, args=(playlist_url, options, progress_hook, web_logger))
    thread.start()

    return {"message": "Download started."}


@app.route('/format_versions', methods=['POST'])
def format_versions():
    source_root = Path(request.form.get('source_root', './downloads/quran_Serailler'))
    target_root = Path(request.form.get('target_root', './downloads/quran_Serailler_serialized'))
    start_version = int(request.form.get('start_version', 1))
    end_version = int(request.form.get('end_version', 7))

    try:
        total = version_formatter.format_versions(
            source_root=source_root,
            target_root=target_root,
            start_version=start_version,
            end_version=end_version,
        )
        return {"message": f"Formatted {total} files into {target_root}"}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            # Wait for a message and send it
            message = progress_queue.get()
            yield message
            if "event: finished" in message:
                break
    return Response(event_stream(), mimetype='text/event-stream')

def main():
    app.run(debug=True)

if __name__ == '__main__':
    main()
