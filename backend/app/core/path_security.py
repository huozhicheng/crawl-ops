"""受控目录中的安全路径解析工具。"""

from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


class UnsafePathError(ValueError):
    """路径不是指定根目录下的安全相对路径。"""


def resolve_within_directory(
    root: PathLike, relative_path: PathLike, *, allow_root: bool = True
) -> Path:
    """规范化路径，并确保结果始终在 ``root`` 目录内。"""
    root_path = Path(root).resolve()
    supplied_path = str(relative_path or ".")

    # 拒绝跨平台路径分隔符、空字节和绝对路径，避免不同运行环境中的绕过。
    if "\x00" in supplied_path or "\\" in supplied_path:
        raise UnsafePathError("路径格式无效")

    candidate = Path(supplied_path)
    if candidate.is_absolute():
        raise UnsafePathError("不允许使用绝对路径")

    target_path = (root_path / candidate).resolve()
    if target_path != root_path and root_path not in target_path.parents:
        raise UnsafePathError("路径超出允许的目录")
    if not allow_root and target_path == root_path:
        raise UnsafePathError("不允许使用根目录")

    return target_path
