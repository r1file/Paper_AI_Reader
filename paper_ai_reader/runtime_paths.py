from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_NAME = "Paper AI Reader"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path.cwd()


def user_data_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "paper-ai-reader"


def config_dir() -> Path:
    if is_frozen():
        return user_data_root() / "config"
    return Path("config")


def prompt_dir() -> Path:
    if is_frozen():
        return user_data_root() / "prompts"
    return Path("prompts")


def bundled_config_dir() -> Path:
    return resource_root() / "config"


def bundled_prompt_dir() -> Path:
    return resource_root() / "prompts"


def ensure_runtime_files() -> None:
    if not is_frozen():
        return

    config_dir().mkdir(parents=True, exist_ok=True)
    prompt_dir().mkdir(parents=True, exist_ok=True)

    bundled_example = bundled_config_dir() / "settings.example.xml"
    user_example = config_dir() / "settings.example.xml"
    user_settings = config_dir() / "settings.xml"
    if bundled_example.exists():
        if not user_example.exists():
            shutil.copy2(bundled_example, user_example)
        if not user_settings.exists():
            shutil.copy2(bundled_example, user_settings)

    for bundled_prompt in bundled_prompt_dir().glob("*.xml"):
        target = prompt_dir() / bundled_prompt.name
        if not target.exists():
            shutil.copy2(bundled_prompt, target)
