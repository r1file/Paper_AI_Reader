from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any, Iterable

from notion_client import Client
from notion_client.errors import RequestTimeoutError


TBD_STATUS = "TBD"
READING_STATUS = "AI Reading"
DONE_STATUS = "AI Read Done"
HUMAN_READING_STATUS = "Human Reading"
MANUAL_DONE_STATUS = "DONE"
PROCESSABLE_STATUSES = {TBD_STATUS, READING_STATUS}
TITLE_PROPERTY = "Title"
WEBSITE_PROPERTY = "Website"
STATUS_PROPERTY = "Status"
KEYWORDS_PROPERTY = "Keywords"
RICH_TEXT_LIMIT = 2000
MAX_APPEND_CHILDREN = 100
NOTION_TIMEOUT_MS = 120_000
NOTION_MIN_INTERVAL_SECONDS = 0.35
DELETE_RETRIES = 3
MAX_KEYWORDS = 6
KEYWORD_TEXT_LIMIT = 80


@dataclass(frozen=True)
class PaperPage:
    page_id: str
    title: str
    website: str | None
    status: str | None


class NotionPaperService:
    def __init__(self, notion_token: str, database_id: str) -> None:
        self.notion = Client(options={"auth": notion_token, "timeout_ms": NOTION_TIMEOUT_MS})
        self.database_id = database_id
        self.data_source_id: str | None = None
        self.status_property_type = "status"
        self.keywords_property_type: str | None = None
        self._last_request_at = 0.0
        self._load_database_metadata()

    def _load_database_metadata(self) -> None:
        database = self._notion_call(self.notion.databases.retrieve, database_id=self.database_id)
        data_sources = database.get("data_sources", [])
        if data_sources:
            self.data_source_id = data_sources[0]["id"]
            metadata = self._notion_call(
                self.notion.data_sources.retrieve,
                data_source_id=self.data_source_id,
            )
        else:
            metadata = database

        status_property = metadata.get("properties", {}).get(STATUS_PROPERTY, {})
        property_type = status_property.get("type")
        if property_type in {"status", "select"}:
            self.status_property_type = property_type

        keywords_property = metadata.get("properties", {}).get(KEYWORDS_PROPERTY, {})
        keywords_property_type = keywords_property.get("type")
        if keywords_property_type in {"multi_select", "select", "rich_text"}:
            self.keywords_property_type = keywords_property_type

    def iter_pages(self) -> Iterable[PaperPage]:
        start_cursor = None
        while True:
            query_args: dict[str, Any] = {
                "page_size": 100,
            }
            if start_cursor:
                query_args["start_cursor"] = start_cursor

            if self.data_source_id:
                response = self._notion_call(
                    self.notion.data_sources.query,
                    data_source_id=self.data_source_id,
                    **query_args,
                )
            else:
                response = self._notion_call(
                    self.notion.databases.query,
                    database_id=self.database_id,
                    **query_args,
                )

            for page in response.get("results", []):
                yield self._parse_page(page)

            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")

    def iter_pending_pages(self) -> Iterable[PaperPage]:
        for paper_page in self.iter_pages():
            if paper_page.status in PROCESSABLE_STATUSES:
                yield paper_page

    def _parse_page(self, page: dict[str, Any]) -> PaperPage:
        properties = page.get("properties", {})
        title_items = properties.get(TITLE_PROPERTY, {}).get("title", [])
        title = title_items[0]["plain_text"] if title_items else "(No title)"

        website = properties.get(WEBSITE_PROPERTY, {}).get("url")

        status_property = properties.get(STATUS_PROPERTY, {})
        status_value = status_property.get("select") or status_property.get("status")
        status = status_value.get("name") if status_value else None

        return PaperPage(
            page_id=page["id"],
            title=title,
            website=website,
            status=status,
        )

    def delete_all_blocks(self, page_id: str) -> None:
        for block_id in self._list_child_block_ids(page_id):
            self._delete_block_with_retries(block_id)

    def read_page_text(self, page_id: str) -> str:
        lines: list[str] = []
        self._collect_block_text(page_id, lines)
        return "\n".join(line for line in lines if line.strip())

    def _collect_block_text(self, block_id: str, lines: list[str]) -> None:
        start_cursor = None

        while True:
            args: dict[str, Any] = {"block_id": block_id, "page_size": 100}
            if start_cursor:
                args["start_cursor"] = start_cursor

            response = self._notion_call(self.notion.blocks.children.list, **args)
            for block in response.get("results", []):
                text = extract_block_plain_text(block)
                if text:
                    lines.append(text)
                if block.get("has_children"):
                    self._collect_block_text(block["id"], lines)

            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")

    def _delete_block_with_retries(self, block_id: str) -> None:
        for attempt in range(1, DELETE_RETRIES + 1):
            try:
                self._notion_call(self.notion.blocks.delete, block_id=block_id)
                return
            except RequestTimeoutError:
                if attempt == DELETE_RETRIES:
                    raise
                sleep(attempt)

    def _list_child_block_ids(self, block_id: str) -> list[str]:
        block_ids: list[str] = []
        start_cursor = None

        while True:
            args: dict[str, Any] = {"block_id": block_id, "page_size": 100}
            if start_cursor:
                args["start_cursor"] = start_cursor

            response = self._notion_call(self.notion.blocks.children.list, **args)
            block_ids.extend(block["id"] for block in response.get("results", []))

            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")

        return block_ids

    def write_analysis(self, page_id: str, analysis: dict[str, Any], language: str = "zh") -> None:
        blocks = build_analysis_blocks(analysis, language)
        for batch in chunked(blocks, MAX_APPEND_CHILDREN):
            self._notion_call(
                self.notion.blocks.children.append,
                block_id=page_id,
                children=batch,
            )

    def update_keywords(self, page_id: str, keywords: list[str]) -> None:
        if not self.keywords_property_type:
            return

        clean_keywords = normalize_keywords_for_notion(keywords)
        if self.keywords_property_type == "multi_select":
            value: dict[str, Any] = {
                "multi_select": [{"name": keyword} for keyword in clean_keywords],
            }
        elif self.keywords_property_type == "select":
            value = {"select": {"name": clean_keywords[0]} if clean_keywords else None}
        elif self.keywords_property_type == "rich_text":
            value = {
                "rich_text": (
                    [
                        {
                            "type": "text",
                            "text": {"content": ", ".join(clean_keywords)[:RICH_TEXT_LIMIT]},
                        }
                    ]
                    if clean_keywords
                    else []
                )
            }
        else:
            return

        self._notion_call(
            self.notion.pages.update,
            page_id=page_id,
            properties={KEYWORDS_PROPERTY: value},
        )

    def update_title(self, page_id: str, title: str) -> None:
        clean_title = title.strip()
        if not clean_title:
            return
        self._notion_call(
            self.notion.pages.update,
            page_id=page_id,
            properties={
                TITLE_PROPERTY: {
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": clean_title[:RICH_TEXT_LIMIT]},
                        }
                    ]
                }
            },
        )

    def mark_reading(self, page_id: str) -> None:
        self.update_status(page_id, READING_STATUS)

    def mark_done(self, page_id: str) -> None:
        self.update_status(page_id, DONE_STATUS)

    def update_status(self, page_id: str, status_name: str) -> None:
        self._notion_call(
            self.notion.pages.update,
            page_id=page_id,
            properties={STATUS_PROPERTY: {self.status_property_type: {"name": status_name}}},
        )

    def _notion_call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        self._throttle()
        try:
            return func(*args, **kwargs)
        finally:
            self._last_request_at = monotonic()

    def _throttle(self) -> None:
        elapsed = monotonic() - self._last_request_at
        remaining = NOTION_MIN_INTERVAL_SECONDS - elapsed
        if remaining > 0:
            sleep(remaining)


BLOCK_TEXT = {
    "zh": {
        "summary": "🔍 总结",
        "idea": "💡 对我的研究的启发",
        "related": "⭐ 与我的研究相关性",
        "code": "🧪 代码可用性",
        "yes": "是",
        "no": "否",
        "code_url": "GitHub：{url}",
        "notes": "🧠 我的笔记",
        "manual_notes": "（自己写）",
    },
    "ja": {
        "summary": "🔍 要約",
        "idea": "💡 自分の研究へのアイデア",
        "related": "⭐ 自分の研究との関連性",
        "code": "🧪 コード公開状況",
        "yes": "はい",
        "no": "いいえ",
        "code_url": "コードURL：{url}",
        "notes": "🧠 自分のメモ",
        "manual_notes": "（自分で書く）",
    },
    "en": {
        "summary": "🔍 Summary",
        "idea": "💡 Idea for My Research",
        "related": "⭐ Related to My Research",
        "code": "🧪 Code Availability",
        "yes": "Yes",
        "no": "No",
        "code_url": "Code URL: {url}",
        "notes": "🧠 My Notes",
        "manual_notes": "(Write myself)",
    },
}


def note_language(language: str) -> str:
    return language if language in BLOCK_TEXT else "zh"


def normalize_keywords_for_notion(keywords: list[str]) -> list[str]:
    clean_keywords: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        clean_keyword = str(keyword or "").replace(",", " ").strip()
        clean_keyword = " ".join(clean_keyword.split())[:KEYWORD_TEXT_LIMIT]
        if not clean_keyword:
            continue
        dedupe_key = clean_keyword.casefold()
        if dedupe_key in seen:
            continue
        clean_keywords.append(clean_keyword)
        seen.add(dedupe_key)
        if len(clean_keywords) >= MAX_KEYWORDS:
            break
    return clean_keywords


def build_analysis_blocks(analysis: dict[str, Any], language: str = "zh") -> list[dict[str, Any]]:
    text = BLOCK_TEXT[note_language(language)]
    rating = int(analysis.get("rating") or 1)
    rating = min(5, max(1, rating))
    stars = "★" * rating + "☆" * (5 - rating)
    code_available = bool(analysis.get("code_available"))
    code_url = str(analysis.get("code_url") or "").strip()

    blocks: list[dict[str, Any]] = []
    blocks.append(heading_2(text["summary"]))
    blocks.extend(paragraphs(str(analysis.get("summary") or "")))
    blocks.append(heading_2(text["idea"]))
    blocks.extend(paragraphs(str(analysis.get("idea") or "")))
    blocks.append(heading_2(text["related"]))
    blocks.extend(paragraphs(f"{stars}\n{analysis.get('reason') or ''}"))
    blocks.append(heading_2(text["code"]))
    code_lines = [text["yes"] if code_available else text["no"]]
    if code_url:
        code_lines.append(text["code_url"].format(url=code_url))
    blocks.extend(paragraphs("\n".join(code_lines)))
    blocks.append(heading_2(text["notes"]))
    blocks.extend(paragraphs(text["manual_notes"]))
    return blocks


def heading_2(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [rich_text(text)]},
    }


def paragraphs(text: str) -> list[dict[str, Any]]:
    parts = split_rich_text(text.strip() or " ")
    return [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [rich_text(part)]},
        }
        for part in parts
    ]


def rich_text(text: str) -> dict[str, Any]:
    return {"type": "text", "text": {"content": text[:RICH_TEXT_LIMIT]}}


def split_rich_text(text: str) -> list[str]:
    chunks: list[str] = []
    remaining = text

    while len(remaining) > RICH_TEXT_LIMIT:
        split_at = remaining.rfind("\n", 0, RICH_TEXT_LIMIT)
        if split_at < RICH_TEXT_LIMIT // 2:
            split_at = remaining.rfind(" ", 0, RICH_TEXT_LIMIT)
        if split_at < RICH_TEXT_LIMIT // 2:
            split_at = RICH_TEXT_LIMIT

        chunks.append(remaining[:split_at].strip() or " ")
        remaining = remaining[split_at:].strip()

    chunks.append(remaining or " ")
    return chunks


def extract_block_plain_text(block: dict[str, Any]) -> str:
    block_type = block.get("type")
    if not block_type:
        return ""

    data = block.get(block_type, {})
    rich_text_items = data.get("rich_text") or data.get("caption") or []
    parts = [item.get("plain_text", "") for item in rich_text_items]

    if block_type == "code":
        parts.append(data.get("language", ""))
    elif block_type == "equation":
        parts.append(data.get("expression", ""))
    elif block_type in {"pdf", "file", "image", "video", "bookmark", "embed", "link_preview"}:
        parts.append(data.get("url", ""))

    return " ".join(part.strip() for part in parts if part and part.strip())


def chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
