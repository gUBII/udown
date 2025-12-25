from unittest.mock import patch

import pytest
from click.testing import CliRunner

from udown.main import cli

@pytest.fixture
def runner():
    return CliRunner()

@patch("udown.main.downloader.download_playlist")
def test_download_calls_downloader(mock_download_playlist, runner):
    mock_download_playlist.return_value = {"title": "Test Playlist"}
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "download",
                "http://fake-playlist-url.com",
                "--output-dir",
                "out",
                "--simple-serial",
            ],
        )

    assert result.exit_code == 0
    assert "Processing playlist 1/1" in result.output
    assert "Successfully downloaded playlist: 'Test Playlist'" in result.output

    kwargs = mock_download_playlist.call_args.kwargs
    assert kwargs["playlist_url"] == "http://fake-playlist-url.com"
    assert kwargs["name_template"] == "{playlist_index:02d}.{ext}"
    assert str(kwargs["output_dir"]).endswith("out")


def test_no_url_provided(runner):
    """Test the command when no URL is provided."""
    result = runner.invoke(cli, ['download'])
    assert result.exit_code == 0
    assert "No playlist URLs provided" in result.output


@patch("udown.main.version_formatter.format_versions")
def test_format_versions_calls_formatter(mock_format_versions, runner):
    mock_format_versions.return_value = 3
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "format-versions",
                "--source-root",
                "downloads/quran_Serailler",
                "--target-root",
                "downloads/quran_Serailler_serialized",
            ],
        )

    assert result.exit_code == 0
    assert "Formatted 3 files into downloads/quran_Serailler_serialized" in result.output

    kwargs = mock_format_versions.call_args.kwargs
    assert kwargs["allowed_suffixes"] == (".mp3",)
