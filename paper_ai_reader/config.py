from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from paper_ai_reader.prompts import (
    DEFAULT_PROMPT_LANGUAGE,
    get_prompt,
    get_user_prompt_template,
    normalized_language,
)


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEXT_LIMIT = 50_000
CONFIG_DIR = Path("config")
CLI_CONFIG_PATH = CONFIG_DIR / "cli_config.xml"
GUI_CONFIG_PATH = CONFIG_DIR / "gui_config.xml"
GUI_STATE_PATH = CONFIG_DIR / ".gui_state.xml"
REQUIRED_CONFIG_KEYS = {
    "notion_token",
    "notion_database_id",
    "ai_api_key",
    "ai_model",
    "ai_base_url",
    "paper_text_limit",
    "ui_language",
    "theme_mode",
    "prompt_language",
}


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
    user_prompt_template: str = ""
    profile: str = "cli"
    ai_model_explicit: bool = False


@dataclass
class AppState:
    ui_language: str = ""
    prompt_language: str = ""
    theme_mode: str = "system"
    last_config_path: str = ""
    last_prompt_path: str = ""

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
    normalized_profile = normalize_profile(profile)
    path = Path(config_path) if config_path else default_config_path(normalized_profile)
    config = load_xml_config(path)

    prompt_language = normalized_language(
        str(config.get("prompt_language") or DEFAULT_PROMPT_LANGUAGE)
    )
    ui_language = normalized_language(
        str(config.get("ui_language") or prompt_language)
    )
    theme_mode = str(config.get("theme_mode") or "system")
    prompt = get_prompt(normalized_profile, prompt_language)
    user_prompt_template = get_user_prompt_template(normalized_profile, prompt_language)

    notion_token = str(config.get("notion_token") or "")
    notion_database_id = str(config.get("notion_database_id") or "")
    ai_api_key = str(config.get("ai_api_key") or "")
    configured_ai_model = str(config.get("ai_model") or "").strip()
    ai_model = configured_ai_model or (DEFAULT_MODEL if normalized_profile == "cli" else "")
    ai_base_url = config.get("ai_base_url") or None
    paper_text_limit = int(
        config.get("paper_text_limit")
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
        user_prompt_template=user_prompt_template,
        profile=normalized_profile,
        ai_model_explicit=bool(configured_ai_model),
    )


def save_settings_xml(
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


def load_app_state(path: str | Path = GUI_STATE_PATH) -> AppState:
    xml_path = Path(path)
    if not xml_path.exists():
        return AppState()
    try:
        values = load_xml_config(xml_path)
    except ET.ParseError:
        return AppState()
    return AppState(
        ui_language=normalized_language(values.get("ui_language", "")),
        prompt_language=normalized_language(values.get("prompt_language", "")),
        theme_mode=values.get("theme_mode", "system") or "system",
        last_config_path=values.get("last_config_path", ""),
        last_prompt_path=values.get("last_prompt_path", ""),
    )


def save_app_state(state: AppState, path: str | Path = GUI_STATE_PATH) -> None:
    xml_path = Path(path)
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("paper_ai_reader_gui_state")
    for key, value in {
        "ui_language": state.ui_language,
        "prompt_language": state.prompt_language,
        "theme_mode": state.theme_mode,
        "last_config_path": state.last_config_path,
        "last_prompt_path": state.last_prompt_path,
    }.items():
        ET.SubElement(root, key).text = value
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def validate_runtime_files(profile: str = "gui", config_path: str | Path | None = None) -> list[str]:
    errors: list[str] = []
    normalized_profile = normalize_profile(profile)
    config_path = Path(config_path) if config_path else default_config_path(normalized_profile)
    if not config_path.exists():
        errors.append(f"Missing config XML: {config_path}")
    else:
        try:
            config_values = load_xml_config(config_path)
            missing_keys = sorted(REQUIRED_CONFIG_KEYS - set(config_values))
            if missing_keys:
                errors.append(f"Config XML missing keys: {', '.join(missing_keys)}")
            missing_values = [
                key for key in ("notion_token", "notion_database_id", "ai_api_key")
                if not config_values.get(key)
            ]
            if missing_values:
                errors.append(f"Config XML has empty required values: {', '.join(missing_values)}")
        except ET.ParseError as exc:
            errors.append(f"Invalid config XML: {exc}")

    for language in ("zh", "ja", "en"):
        prompt_file = default_config_path("gui").parent.parent / "prompts" / "default" / f"{language}.xml"
        if not prompt_file.exists():
            errors.append(f"Missing default prompt XML: {prompt_file}")
            continue
        try:
            root = ET.parse(prompt_file).getroot()
            if not root.findtext("system_prompt") and not root.findtext("content"):
                errors.append(f"Prompt XML missing system_prompt: {prompt_file}")
            if not root.findtext("user_prompt_template"):
                errors.append(f"Prompt XML missing user_prompt_template: {prompt_file}")
        except ET.ParseError as exc:
            errors.append(f"Invalid prompt XML {prompt_file}: {exc}")
    return errors


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
