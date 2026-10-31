"""Shared user-level Shunt settings loaded only from a private JSON file."""
import json
import os
from functools import lru_cache
from pathlib import Path
import stat


class ConfigError(Exception):
    pass


CONFIG_PATH = Path.home() / ".config" / "codex-shunt" / "config.json"
FIELDS = {
    "api_base": str,
    "model": str,
    "api_key": str,
    "context_tokens": int,
    "reply_tokens": int,
    "max_payload_bytes": int,
    "timeout_seconds": (int, float),
    "min_lines": int,
}


@lru_cache(maxsize=1)
def load_config():
    try:
        details = CONFIG_PATH.lstat()
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {CONFIG_PATH}; copy config.example.json there and chmod 600") from exc
    except OSError as exc:
        raise ConfigError(f"cannot access {CONFIG_PATH}: {exc}") from exc
    if not stat.S_ISREG(details.st_mode):
        raise ConfigError(f"config must be a regular file (not a symlink): {CONFIG_PATH}")
    if os.name != "nt" and details.st_mode & 0o077:
        raise ConfigError(f"config file is accessible by others; run chmod 600 {CONFIG_PATH}")
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ConfigError(f"cannot read valid JSON config at {CONFIG_PATH}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("config must be a JSON object")
    for name, value in data.items():
        if name not in FIELDS:
            raise ConfigError(f"unknown config field: {name}")
        if isinstance(value, bool) or not isinstance(value, FIELDS[name]):
            raise ConfigError(f"invalid config type for {name}")
    return data


def setting(name, default=""):
    return load_config().get(name, default)
