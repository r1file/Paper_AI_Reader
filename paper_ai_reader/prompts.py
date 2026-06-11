from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from paper_ai_reader.runtime_paths import ensure_runtime_files, prompt_dir


DEFAULT_PROMPT_LANGUAGE = "zh"
PROMPT_LANGUAGE_LABELS = {
    "zh": "中文",
    "ja": "日本語",
    "en": "English",
}


def default_prompt_path(language: str) -> Path:
    ensure_runtime_files()
    return prompt_dir() / f"{normalized_language(language)}.xml"


def prompt_path(language: str) -> Path:
    return default_prompt_path(language)


def get_prompt(language: str) -> str:
    return read_system_prompt_xml(default_prompt_path(language))


def get_default_prompt(language: str) -> str:
    return read_system_prompt_xml(default_prompt_path(language))


def get_user_prompt_template(language: str) -> str:
    return get_default_user_prompt_template(language)


def get_default_user_prompt_template(language: str) -> str:
    return read_user_prompt_template_xml(default_prompt_path(language))


def ensure_prompt_xml(language: str) -> Path:
    path = prompt_path(language)
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt XML: {path}")
    return path


def read_prompt_xml(path: str | Path) -> str:
    return read_system_prompt_xml(path)


def read_system_prompt_xml(path: str | Path) -> str:
    xml_path = Path(path)
    if not xml_path.exists():
        return ""
    root = ET.parse(xml_path).getroot()
    content = root.findtext("system_prompt") or root.findtext("content")
    return content.strip() if content else ""


def read_user_prompt_template_xml(path: str | Path) -> str:
    xml_path = Path(path)
    if not xml_path.exists():
        return ""
    root = ET.parse(xml_path).getroot()
    content = root.findtext("user_prompt_template")
    return content.strip() if content else ""


def write_prompt_xml(
    path: str | Path,
    language: str,
    content: str,
    user_prompt_template: str | None = None,
) -> None:
    xml_path = Path(path)
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalized_language(language)
    if user_prompt_template is None:
        user_prompt_template = (
            read_user_prompt_template_xml(xml_path)
            or get_default_user_prompt_template(normalized)
        )
    root = ET.Element(
        "paper_ai_reader_prompt",
        {
            "profile": "shared",
            "language": normalized,
        },
    )
    ET.SubElement(root, "system_prompt").text = content.strip()
    ET.SubElement(root, "user_prompt_template").text = user_prompt_template.strip()
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def normalized_language(language: str) -> str:
    return language if language in PROMPT_LANGUAGE_LABELS else DEFAULT_PROMPT_LANGUAGE
