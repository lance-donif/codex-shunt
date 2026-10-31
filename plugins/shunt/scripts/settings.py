"""Shared private JSON settings and atomic cross-process failover state."""
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
import stat
import tempfile


class ConfigError(Exception):
    pass


CONFIG_PATH = Path.home() / ".codex" / "shunt" / "config.json"
FIELDS = {
    "api_base": str, "model": str, "api_key": str,
    "context_tokens": int, "input_tokens": int, "reply_tokens": int,
    "max_payload_bytes": int, "timeout_seconds": (int, float), "min_lines": int,
    "models": list, "current_model": int,
    "first_failure_at": (str, type(None)), "second_failure_at": (str, type(None)),
}
MODEL_FIELDS = {
    "name": str, "api_base": str, "model": str, "api_key": str,
    "reasoning_effort": str, "token_field": str,
    "context_tokens": int, "input_tokens": int, "reply_tokens": int,
    "timeout_seconds": (int, float),
}


@lru_cache(maxsize=1)
def load_config():
    try:
        details = CONFIG_PATH.lstat()
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {CONFIG_PATH}; create it and chmod 600") from exc
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
    if "models" in data:
        if not data["models"]:
            raise ConfigError("models must contain at least one model")
        names = set()
        for model in data["models"]:
            if not isinstance(model, dict):
                raise ConfigError("each model must be an object")
            for key, value in model.items():
                if key not in MODEL_FIELDS or isinstance(value, bool) or not isinstance(value, MODEL_FIELDS[key]):
                    raise ConfigError(f"invalid model field: {key}")
            for required in ("name", "api_base", "model"):
                if not model.get(required):
                    raise ConfigError(f"model is missing {required}")
            if model["name"] in names:
                raise ConfigError(f"duplicate model name: {model['name']}")
            names.add(model["name"])
            if model.get("token_field", "max_tokens") not in ("max_tokens", "max_completion_tokens"):
                raise ConfigError("token_field must be max_tokens or max_completion_tokens")
    for name in ("first_failure_at", "second_failure_at"):
        if data.get(name) is not None:
            try:
                parsed = datetime.fromisoformat(data[name])
                if parsed.tzinfo is None:
                    raise ValueError
            except ValueError as exc:
                raise ConfigError(f"{name} must be an ISO 8601 timestamp with timezone or null") from exc
    index = data.get("current_model", 0)
    if index < 0 or index >= len(data.get("models", [None])):
        raise ConfigError("current_model is outside the configured models")
    return data


def setting(name, default=""):
    return load_config().get(name, default)


def profiles():
    config = load_config()
    if "models" in config:
        return config["models"]
    return [{"name": "default", **{k: v for k, v in config.items() if k in MODEL_FIELDS}}]


def paused(config):
    if config.get("second_failure_at") is not None:
        return True
    first = config.get("first_failure_at")
    return bool(first and datetime.now(timezone.utc) <
                datetime.fromisoformat(first) + timedelta(minutes=30))


@contextmanager
def config_lock():
    # Keep the lock for a complete failover cycle; never race on the pointer or timestamps.
    lock_path = CONFIG_PATH.with_suffix(".lock")
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError as exc:
        raise ConfigError(f"cannot lock config at {lock_path}: {exc}") from exc
    try:
        if os.name == "nt":
            import msvcrt
            os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def update_state(**changes):
    """Update only managed fields, keeping credentials and all other user options intact."""
    load_config.cache_clear()
    data = dict(load_config())
    data.update(changes)
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=CONFIG_PATH.parent,
                                         prefix=".shunt-", delete=False) as output:
            temp = Path(output.name)
            os.chmod(temp, 0o600)
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, CONFIG_PATH)
    except OSError as exc:
        raise ConfigError(f"cannot save Shunt state to {CONFIG_PATH}: {exc}") from exc
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
        load_config.cache_clear()
