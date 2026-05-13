from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET


DEFAULT_PROMPT_LANGUAGE = "zh"
PROMPT_PROFILES = {"cli", "gui"}

PROMPT_LANGUAGE_LABELS = {
    "zh": "中文",
    "ja": "日本語",
    "en": "English",
}

DEFAULT_PROMPT_DIR = Path("prompts/default")
USER_PROMPT_ROOT = Path("prompts")


def default_prompt_path(language: str) -> Path:
    return DEFAULT_PROMPT_DIR / f"{normalized_language(language)}.xml"


def prompt_path(profile: str, language: str) -> Path:
    return USER_PROMPT_ROOT / normalized_profile(profile) / f"{normalized_language(language)}.xml"


def get_prompt(profile: str, language: str) -> str:
    user_path = prompt_path(profile, language)
    if user_path.exists():
        return read_prompt_xml(user_path)
    return read_prompt_xml(default_prompt_path(language))


def get_default_prompt(language: str) -> str:
    return read_prompt_xml(default_prompt_path(language))


def ensure_prompt_xml(profile: str, language: str) -> Path:
    path = prompt_path(profile, language)
    if not path.exists():
        write_prompt_xml(
            path=path,
            profile=profile,
            language=language,
            content=get_default_prompt(language),
        )
    return path


def read_prompt_xml(path: str | Path) -> str:
    xml_path = Path(path)
    if not xml_path.exists():
        return ""
    root = ET.parse(xml_path).getroot()
    content = root.findtext("content")
    return content.strip() if content else ""


def write_prompt_xml(path: str | Path, profile: str, language: str, content: str) -> None:
    xml_path = Path(path)
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element(
        "paper_ai_reader_prompt",
        {
            "profile": normalized_profile(profile),
            "language": normalized_language(language),
        },
    )
    ET.SubElement(root, "content").text = content.strip()
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def normalized_language(language: str) -> str:
    return language if language in PROMPT_LANGUAGE_LABELS else DEFAULT_PROMPT_LANGUAGE


def normalized_profile(profile: str) -> str:
    return profile if profile in PROMPT_PROFILES else "cli"
