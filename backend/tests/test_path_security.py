from pathlib import Path

import pytest

from app.core.path_security import UnsafePathError, resolve_within_directory


def test_resolve_within_directory_allows_nested_file(tmp_path: Path):
    assert (
        resolve_within_directory(tmp_path, "scripts/collector.py")
        == tmp_path / "scripts/collector.py"
    )


@pytest.mark.parametrize("candidate", ["../outside.txt", "/tmp/outside.txt", r"..\\outside.txt"])
def test_resolve_within_directory_rejects_path_traversal(tmp_path: Path, candidate: str):
    with pytest.raises(UnsafePathError):
        resolve_within_directory(tmp_path, candidate)


def test_resolve_within_directory_can_reject_the_root(tmp_path: Path):
    with pytest.raises(UnsafePathError):
        resolve_within_directory(tmp_path, ".", allow_root=False)
