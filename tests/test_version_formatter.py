from pathlib import Path

from udown.version_formatter import format_versions


def test_format_versions_orders_and_numbers(tmp_path: Path) -> None:
    source_root = tmp_path / "quran_Serailler"
    (source_root / "Version_1").mkdir(parents=True)
    (source_root / "Version_2").mkdir(parents=True)

    (source_root / "Version_1" / "b.mp3").write_bytes(b"b")
    (source_root / "Version_1" / "a.mp3").write_bytes(b"a")
    (source_root / "Version_1" / ".hidden.mp3").write_bytes(b"x")
    (source_root / "Version_1" / "c.m4a").write_bytes(b"c")
    (source_root / "Version_2" / "d.mp3").write_bytes(b"d")

    target_root = tmp_path / "serialized"
    total = format_versions(source_root=source_root, target_root=target_root, start_version=1, end_version=2)
    assert total == 3

    out = sorted(p.name for p in target_root.iterdir())
    assert out == [
        "001 - a.mp3",
        "002 - b.mp3",
        "003 - d.mp3",
    ]


def test_format_versions_ascii_safe_fallback(tmp_path: Path) -> None:
    source_root = tmp_path / "quran_Serailler"
    (source_root / "Version_1").mkdir(parents=True)
    (source_root / "Version_1" / "سورة.mp3").write_bytes(b"x")

    target_root = tmp_path / "serialized"
    total = format_versions(source_root=source_root, target_root=target_root, start_version=1, end_version=1)
    assert total == 1

    out = [p.name for p in target_root.iterdir()]
    assert out == ["001 - track.mp3"]

