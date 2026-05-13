from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from dotenv import load_dotenv

from paper_ai_reader.prompts import DEFAULT_PROMPT_LANGUAGE, get_prompt, normalized_language


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEXT_LIMIT = 50_000
CONFIG_DIR = Path("config")
CLI_CONFIG_PATH = CONFIG_DIR / "cli_config.xml"
GUI_CONFIG_PATH = CONFIG_DIR / "gui_config.xml"
LEGACY_JSON_CONFIG_PATH = Path("app_config.json")


@dataclass
class Settings:
    notion_token: str
    notion_database_id: str
    ai_api_key: str
    ai_model: str = DEFAULT_MODEL
    ai_base_url: str | None = None
    paper_text_limit: int = DEFAULT_TEXT_LIMIT
    ui_language: str = DEFAULT_PROMPT_LANGUAGE
    theme_mode: str = "system"
    prompt_language: str = DEFAULT_PROMPT_LANGUAGE
    prompt: str = ""
    profile: str = "cli"

    @property
    def openai_api_key(self) -> str:
        return self.ai_api_key

    @property
    def openai_model(self) -> str:
        return self.ai_model


def load_settings(
    config_path: str | Path | None = None,
    validate_required: bool = True,
    profile: str = "cli",
) -> Settings:
    load_dotenv()
    normalized_profile = normalize_profile(profile)
    path = Path(config_path) if config_path else default_config_path(normalized_profile)
    config = load_xml_config(path)

    if not config:
        config = load_legacy_config(normalized_profile)

    prompt_language = normalized_language(
        str(config.get("prompt_language") or os.getenv("PROMPT_LANGUAGE") or DEFAULT_PROMPT_LANGUAGE)
    )
    ui_language = normalized_language(
        str(config.get("ui_language") or os.getenv("UI_LANGUAGE") or prompt_language)
    )
    theme_mode = str(config.get("theme_mode") or os.getenv("THEME_MODE") or "system")
    prompt = get_prompt(normalized_profile, prompt_language)

    notion_token = str(config.get("notion_token") or os.getenv("NOTION_TOKEN") or "")
    notion_database_id = str(config.get("notion_database_id") or os.getenv("NOTION_DATABASE_ID") or "")
    ai_api_key = str(
        config.get("ai_api_key")
        or config.get("openai_api_key")
        or os.getenv("AI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    )
    ai_model = str(
        config.get("ai_model")
        or config.get("openai_model")
        or os.getenv("AI_MODEL")
        or os.getenv("OPENAI_MODEL")
        or DEFAULT_MODEL
    )
    ai_base_url = config.get("ai_base_url") or os.getenv("AI_BASE_URL") or None
    paper_text_limit = int(
        config.get("paper_text_limit")
        or os.getenv("PAPER_TEXT_LIMIT")
        or DEFAULT_TEXT_LIMIT
    )

    missing = [
        name
        for name, value in {
            "notion_token": notion_token,
            "notion_database_id": notion_database_id,
            "ai_api_key": ai_api_key,
        }.items()
        if not value
    ]
    if missing and validate_required:
        raise RuntimeError(
            f"Missing required XML config values in {path}: {', '.join(missing)}"
        )

    return Settings(
        notion_token=notion_token,
        notion_database_id=notion_database_id,
        ai_api_key=ai_api_key,
        ai_model=ai_model,
        ai_base_url=str(ai_base_url).strip() if ai_base_url else None,
        paper_text_limit=paper_text_limit,
        ui_language=ui_language,
        theme_mode=theme_mode,
        prompt_language=prompt_language,
        prompt=prompt,
        profile=normalized_profile,
    )


def save_app_config(
    settings: Settings,
    config_path: str | Path | None = None,
    profile: str | None = None,
) -> None:
    save_xml_config(settings, config_path=config_path, profile=profile)


def save_xml_config(
    settings: Settings,
    config_path: str | Path | None = None,
    profile: str | None = None,
) -> None:
    normalized_profile = normalize_profile(profile or settings.profile)
    path = Path(config_path) if config_path else default_config_path(normalized_profile)
    path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("paper_ai_reader_config", {"profile": normalized_profile})
    values = {
        "notion_token": settings.notion_token,
        "notion_database_id": settings.notion_database_id,
        "ai_api_key": settings.ai_api_key,
        "ai_model": settings.ai_model,
        "ai_base_url": settings.ai_base_url or "",
        "paper_text_limit": str(settings.paper_text_limit),
        "ui_language": settings.ui_language,
        "theme_mode": settings.theme_mode,
        "prompt_language": settings.prompt_language,
    }
    for key, value in values.items():
        ET.SubElement(root, key).text = value

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def load_xml_config(config_path: str | Path) -> dict[str, str]:
    path = Path(config_path)
    if not path.exists():
        return {}
    root = ET.parse(path).getroot()
    return {
        child.tag: child.text.strip() if child.text else ""
        for child in root
    }


def default_config_path(profile: str) -> Path:
    return GUI_CONFIG_PATH if normalize_profile(profile) == "gui" else CLI_CONFIG_PATH


def normalize_profile(profile: str) -> str:
    return profile if profile in {"cli", "gui"} else "cli"


def load_legacy_config(profile: str) -> dict[str, Any]:
    if profile != "gui" or not LEGACY_JSON_CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(LEGACY_JSON_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if data.get("prompt"):
        data.pop("prompt")
    return data
