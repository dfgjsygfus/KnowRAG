#!/usr/bin/env python3
"""一键停止本地 Milvus 服务。

用法：
    python scripts/stop_milvus.py

PyCharm 中可直接右键运行此脚本。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_DIR = PROJECT_ROOT / "infra" / "milvus"


def run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=COMPOSE_DIR)


def main() -> int:
    if not shutil.which("docker"):
        print("错误：未找到 docker。", file=sys.stderr)
        return 1

    print("正在停止 Milvus...")
    rc = run(["docker", "compose", "down"])
    if rc != 0:
        print("停止失败。", file=sys.stderr)
        return rc

    print("\nMilvus 已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
