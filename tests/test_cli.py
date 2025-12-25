import pytest
from click.testing import CliRunner
from udown.main import cli
from unittest.mock import patch, MagicMock

@pytest.fixture
def runner():
    return CliRunner()

@patch('yt_dlp.YoutubeDL')
def test_download_command_success(mock_youtube_dl, runner):
    """Test the download command with a single URL."""
    
    # Mock the context manager
    mock_ydl_instance = MagicMock()
    mock_youtube_dl.return_value.__enter__.return_value = mock_ydl_instance

    # Mock playlist info
    mock_ydl_instance.extract_info.return_value = {
        'title': 'Test Playlist',
        'entries': [
            {'id': 'video1', 'title': 'Video 1'},
            {'id': 'video2', 'title': 'Video 2'},
        ]
    }

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['download', 'http://fake-playlist-url.com', '--output-dir', 'test_output'])

        assert result.exit_code == 0
        assert "Downloading playlist: 'Test Playlist'" in result.output
        assert "Output directory: test_output/Test Playlist" in result.output

        # Check that extract_info and download were called
        mock_ydl_instance.extract_info.assert_called_with('http://fake-playlist-url.com', download=False)
        mock_ydl_instance.download.assert_called_with(['http://fake-playlist-url.com'])


@patch('yt_dlp.YoutubeDL')
def test_download_with_metadata(mock_youtube_dl, runner):
    """Test the download command with --save-metadata."""
    
    mock_ydl_instance = MagicMock()
    mock_youtube_dl.return_value.__enter__.return_value = mock_ydl_instance

    playlist_info = {
        'title': 'Metadata Playlist',
        'entries': [{'id': 'v1', 'title': 'V1'}]
    }
    mock_ydl_instance.extract_info.return_value = playlist_info

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['download', 'http://fake-url.com', '--save-metadata'])

        assert result.exit_code == 0
        assert "Saved playlist metadata to Metadata Playlist/playlist_metadata.json" in result.output
        
        # Check if the file was created and contains the correct JSON
        with open('Metadata Playlist/playlist_metadata.json', 'r') as f:
            import json
            data = json.load(f)
            assert data['title'] == 'Metadata Playlist'

@patch('yt_dlp.YoutubeDL')
def test_download_invalid_url(mock_youtube_dl, runner):
    """Test how the app handles an invalid URL."""

    mock_ydl_instance = MagicMock()
    mock_youtube_dl.return_value.__enter__.return_value = mock_ydl_instance
    
    # Simulate an error during info extraction
    from yt_dlp.utils import DownloadError
    mock_ydl_instance.extract_info.side_effect = DownloadError("Invalid URL")

    result = runner.invoke(cli, ['download', 'http://invalid-url.com'])

    assert result.exit_code == 0 # The CLI should exit gracefully
    assert "Error fetching playlist info" in result.output


def test_no_url_provided(runner):
    """Test the command when no URL is provided."""
    result = runner.invoke(cli, ['download'])
    assert result.exit_code == 0
    assert "No playlist URLs provided" in result.output
