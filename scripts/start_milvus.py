#!/usr/bin/env python3
"""一键启动本地 Milvus 服务（通过 Docker Compose）。

用法：
    python scripts/start_milvus.py

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
        print("错误：未找到 docker，请先安装并启动 Docker Desktop。", file=sys.stderr)
        return 1

    if not (COMPOSE_DIR / "docker-compose.yml").exists():
        print(f"错误：未找到 {COMPOSE_DIR / 'docker-compose.yml'}", file=sys.stderr)
        return 1

    print("正在启动 Milvus（后台运行）...")
    rc = run(["docker", "compose", "up", "-d"])
    if rc != 0:
        print("启动失败。", file=sys.stderr)
        return rc

    print("\nMilvus 已尝试启动。可用以下命令查看状态：")
    print("  docker compose -f infra/milvus/docker-compose.yml ps")
    print("  docker logs -f knowrag-milvus-standalone")
    print("\n连接地址：")
    print("  http://localhost:19530")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
