from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

EXECUTOR_ENV_CONFIG_NAME = "executor-env.json"

DEFAULT_EXECUTOR_ENV_CONFIG: dict[str, object] = {
    "inherit": [
        "PATH",
        "HOME",
        "TMPDIR",
        "TEMP",
        "TMP",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "SHELL",
        "USER",
        "LOGNAME",
        "TERM",
        "SSH_AUTH_SOCK",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_ORG_ID",
        "OPENAI_PROJECT",
    ],
    "inherit_prefixes": [],
    "set": {},
    "unset": [],
}


def executor_env_config_path(state_root: Path) -> Path:
    return state_root / EXECUTOR_ENV_CONFIG_NAME


def ensure_executor_env_config(state_root: Path) -> Path:
    path = executor_env_config_path(state_root)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_EXECUTOR_ENV_CONFIG, ensure_ascii=False, indent=2) + "\n")
    return path


def copy_executor_env_config_if_exists(*, source_state_root: Path, target_state_root: Path) -> Path | None:
    source = executor_env_config_path(source_state_root)
    if not source.exists():
        return None
    target = executor_env_config_path(target_state_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text())
    return target


def build_executor_env(
    *,
    config_path: Path | None = None,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source_env = dict(os.environ if base_env is None else base_env)
    config = _load_executor_env_config(config_path)
    inherit = _string_list(config.get("inherit"), field="inherit")
    inherit_prefixes = _string_list(config.get("inherit_prefixes"), field="inherit_prefixes")
    set_values = _string_dict(config.get("set"), field="set")
    unset = set(_string_list(config.get("unset"), field="unset"))

    env: dict[str, str] = {}
    for name in inherit:
        if name == "*":
            env.update(source_env)
            continue
        if name in source_env:
            env[name] = source_env[name]
    for name, value in source_env.items():
        if any(name.startswith(prefix) for prefix in inherit_prefixes):
            env[name] = value
    env.update(set_values)
    for name in unset:
        env.pop(name, None)
    return env


def _load_executor_env_config(config_path: Path | None) -> dict[str, object]:
    if config_path is None or not config_path.exists():
        return dict(DEFAULT_EXECUTOR_ENV_CONFIG)
    try:
        payload = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid executor env config JSON: {config_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Executor env config must be a JSON object: {config_path}")
    return dict(payload)


def _string_list(value: object, *, field: str) -> list[str]:
    if value is None:
        default_value = DEFAULT_EXECUTOR_ENV_CONFIG.get(field, [])
        return list(default_value) if isinstance(default_value, list) else []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"executor env config field `{field}` must be a list of strings")
    return list(value)


def _string_dict(value: object, *, field: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(val, str) for key, val in value.items()):
        raise ValueError(f"executor env config field `{field}` must be an object with string values")
    return dict(value)
