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


def _iter_audio_files(folder: Path, allowed_suffixes: tuple[str, ...]) -> list[Path]:
    allowed = tuple(s.lower() for s in allowed_suffixes) if allowed_suffixes else ()
    files = []
    for p in folder.iterdir():
        if not p.is_file() or p.name.startswith("."):
            continue
        if allowed and p.suffix.lower() not in allowed:
            continue
        files.append(p)
    return sorted(files, key=lambda p: p.name)


def format_versions(
    source_root: Path,
    target_root: Path,
    start_version: int = 1,
    end_version: int = 7,
    allowed_suffixes: tuple[str, ...] = (".mp3",),
) -> int:
    """
    Copy and rename all Version_X folders into one serially numbered folder.

    Files are sorted by name inside each Version_X, then globally numbered 001, 002, ...
    The target directory is cleared of files before writing.
    """
    source_root = Path(source_root)
    target_root = Path(target_root)
    if start_version < 1 or end_version < 1 or start_version > end_version:
        raise ValueError("Invalid version range")
    target_root.mkdir(parents=True, exist_ok=True)

    # Clear existing files in target to avoid stale leftovers
    for existing in target_root.iterdir():
        if existing.is_file():
            existing.unlink()

    all_files: list[Path] = []
    for version in range(start_version, end_version + 1):
        v_dir = source_root / f"Version_{version}"
        if not v_dir.exists():
            continue
        all_files.extend(_iter_audio_files(v_dir, allowed_suffixes))

    total_files = len(all_files)
    if total_files == 0:
        return 0

    width = max(3, len(str(total_files)))
    counter = 1
    for version in range(start_version, end_version + 1):
        v_dir = source_root / f"Version_{version}"
        if not v_dir.exists():
            continue
        for file_path in _iter_audio_files(v_dir, allowed_suffixes):
            stem = _ascii_safe(file_path.stem)
            suffix = file_path.suffix.lower()
            new_name = f"{counter:0{width}d} - {stem}{suffix}"
            dest = target_root / new_name
            shutil.copy2(file_path, dest)
            counter += 1

    return counter - 1
