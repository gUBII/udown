from pathlib import Path
import shutil
import unicodedata

from udown.downloader import sanitize_filename


def _ascii_safe(text: str) -> str:
    """Convert text to ASCII-friendly string for USB audio players."""
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = sanitize_filename(ascii_text) or "track"
    return cleaned[:100]


def format_versions(
    source_root: Path,
    target_root: Path,
    start_version: int = 1,
    end_version: int = 7,
    allowed_suffixes: tuple = (".mp3", ".m4a", ".wav", ".aac"),
) -> int:
    """
    Copy and rename all Version_X folders into one serially numbered folder.

    Files are sorted by name inside each Version_X, then globally numbered 001, 002, ...
    The target directory is cleared of files before writing.
    """
    source_root = Path(source_root)
    target_root = Path(target_root)
    target_root.mkdir(parents=True, exist_ok=True)

    # Clear existing files in target to avoid stale leftovers
    for existing in target_root.iterdir():
        if existing.is_file():
            existing.unlink()

    counter = 1
    for version in range(start_version, end_version + 1):
        v_dir = source_root / f"Version_{version}"
        if not v_dir.exists():
            continue
        files = sorted(
            p for p in v_dir.iterdir()
            if p.is_file()
            and not p.name.startswith(".")
            and (p.suffix.lower() in allowed_suffixes if allowed_suffixes else True)
        )
        for file_path in files:
            stem = _ascii_safe(file_path.stem)
            new_name = f"{counter:03d} - {stem}{file_path.suffix}"
            dest = target_root / new_name
            shutil.copy2(file_path, dest)
            counter += 1

    return counter - 1
