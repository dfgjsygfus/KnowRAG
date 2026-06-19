"""Windows 下 Milvus Lite 3.0 兼容性补丁。

Milvus Lite 3.0 在 Windows 上保存 manifest 时使用了 ``os.rename(tmp, target)``，
但 Windows 的 ``os.rename`` 无法覆盖已存在的目标文件，会导致创建 collection 或索引时报
``FileExistsError: [WinError 183]``。

该补丁在 Windows 上将 ``os.rename`` 替换为：当目标文件已存在时使用 ``os.replace``，
否则保持原生行为。此补丁应在导入 ``pymilvus`` 或 ``milvus_lite`` 之前应用。
"""
from __future__ import annotations

import os
import sys


def _apply() -> None:
    if sys.platform != "win32":
        return

    _orig_rename = os.rename

    def _rename(src: str, dst: str, *, src_dir_fd: int | None = None, dst_dir_fd: int | None = None) -> None:  # noqa: ARG001
        # os.replace 是跨平台的原子替换；在 Windows 上可覆盖已存在文件。
        if os.path.exists(dst):
            os.replace(src, dst)
        else:
            _orig_rename(src, dst)

    os.rename = _rename  # type: ignore[assignment]


_apply()
