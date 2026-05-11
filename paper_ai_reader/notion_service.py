from __future__ import annotations

from dataclasses import dataclass
from time import sleep
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
RICH_TEXT_LIMIT = 2000
MAX_APPEND_CHILDREN = 100
NOTION_TIMEOUT_MS = 120_000
DELETE_RETRIES = 3


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
        self._load_database_metadata()

    def _load_database_metadata(self) -> None:
        database = self.notion.databases.retrieve(database_id=self.database_id)
        data_sources = database.get("data_sources", [])
        if data_sources:
            self.data_source_id = data_sources[0]["id"]

        status_property = database.get("properties", {}).get(STATUS_PROPERTY, {})
        property_type = status_property.get("type")
        if property_type in {"status", "select"}:
            self.status_property_type = property_type

    def iter_pending_pages(self) -> Iterable[PaperPage]:
        start_cursor = None
        while True:
            query_args: dict[str, Any] = {
                "page_size": 100,
            }
            if start_cursor:
                query_args["start_cursor"] = start_cursor

            if self.data_source_id:
                response = self.notion.data_sources.query(
                    data_source_id=self.data_source_id,
                    **query_args,
                )
            else:
                response = self.notion.databases.query(
                    database_id=self.database_id,
                    **query_args,
                )

            for page in response.get("results", []):
                paper_page = self._parse_page(page)
                if paper_page.status in PROCESSABLE_STATUSES:
                    yield paper_page

            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")

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

    def _delete_block_with_retries(self, block_id: str) -> None:
        for attempt in range(1, DELETE_RETRIES + 1):
            try:
                self.notion.blocks.delete(block_id=block_id)
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

            response = self.notion.blocks.children.list(**args)
            block_ids.extend(block["id"] for block in response.get("results", []))

            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")

        return block_ids

    def write_analysis(self, page_id: str, analysis: dict[str, Any]) -> None:
        blocks = build_analysis_blocks(analysis)
        for batch in chunked(blocks, MAX_APPEND_CHILDREN):
            self.notion.blocks.children.append(block_id=page_id, children=batch)

    def update_title(self, page_id: str, title: str) -> None:
        clean_title = title.strip()
        if not clean_title:
            return
        self.notion.pages.update(
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
        self.notion.pages.update(
            page_id=page_id,
            properties={STATUS_PROPERTY: {self.status_property_type: {"name": status_name}}},
        )


def build_analysis_blocks(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    rating = int(analysis.get("rating") or 1)
    rating = min(5, max(1, rating))
    stars = "★" * rating + "☆" * (5 - rating)
    code_available = bool(analysis.get("code_available"))
    code_url = str(analysis.get("code_url") or "").strip()

    blocks: list[dict[str, Any]] = []
    blocks.append(heading_2("🔍 总结"))
    blocks.extend(paragraphs(str(analysis.get("summary") or "")))
    blocks.append(heading_2("💡 对我的研究的启发"))
    blocks.extend(paragraphs(str(analysis.get("idea") or "")))
    blocks.append(heading_2("⭐ 与我的研究相关性"))
    blocks.extend(paragraphs(f"{stars}\n{analysis.get('reason') or ''}"))
    blocks.append(heading_2("🧪 代码可用性"))
    code_lines = ["是" if code_available else "否"]
    if code_url:
        code_lines.append(f"GitHub：{code_url}")
    blocks.extend(paragraphs("\n".join(code_lines)))
    blocks.append(heading_2("🧠 我的笔记"))
    blocks.extend(paragraphs("（自己写）"))
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


def chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
