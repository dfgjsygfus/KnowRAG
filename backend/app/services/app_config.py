from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
def get_config_value(name: str, default: str = "") -> str:
    """优先读系统环境变量；没有时再读项目 `.env` 文件。"""

    value = os.getenv(name)
    if value is not None and value.strip():
        return value.strip()

    for env_file in _candidate_env_files():
        dotenv_value = _read_dotenv_value(env_file, name)
        if dotenv_value:
            return dotenv_value

    return default


def get_config_int(name: str, default: int) -> int:
    """读取整数配置，空值或不存在时使用默认值。"""

    value = get_config_value(name)
    return int(value) if value else default


def get_optional_config_int(name: str) -> int | None:
    """读取可选整数配置，空值时返回 None。"""

    value = get_config_value(name)
    return int(value) if value else None


def _candidate_env_files() -> list[Path]:
    """同时兼容从项目根目录或其他工作目录启动服务的情况。"""

    project_root = Path(__file__).resolve().parents[3]
    candidates = [Path.cwd() / ".env", project_root / ".env"]
    unique: list[Path] = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    return unique


def _read_dotenv_value(env_file: Path, name: str) -> str:
    if not env_file.exists():
        return ""

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        if key.strip() != name:
            continue

        return _strip_quotes(value.strip())

    return ""


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
