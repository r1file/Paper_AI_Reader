from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from paper_ai_reader.analyzer import AnalysisError, ConversationCallback, PaperAnalyzer
from paper_ai_reader.config import Settings
from paper_ai_reader.fetcher import FetchError, clean_text, fetch_paper_text
from paper_ai_reader.notion_service import NotionPaperService, PaperPage, PROCESSABLE_STATUSES


LogCallback = Callable[[str], None]
StatusCallback = Callable[[str], None]

PIPELINE_TEXT = {
    "zh": {
        "initializing": "正在初始化",
        "querying": "正在查询 Notion 数据库…",
        "querying_status": "正在查询 Notion 数据库",
        "stop_requested": "已请求停止。将在下一篇论文前停止。",
        "stopped": "已停止",
        "processing": "\n正在处理：{title}",
        "page_id": "页面 ID：{page_id}",
        "skipped_status": "已跳过：Status 为 {status}。",
        "skipped_website": "已跳过：缺少 Website URL。",
        "mark_reading_status": "标记 AI Reading：{title}",
        "mark_reading": "正在更新 Status 为 AI Reading…",
        "fetch_status": "抓取论文：{title}",
        "fetch": "正在抓取论文内容：{website}",
        "fetch_fallback": "网站抓取失败，正在尝试使用 Notion 页面已有正文…",
        "fetch_fallback_ok": "已使用 Notion 页面已有正文继续分析。",
        "fetch_fallback_empty": "Notion 页面中也没有可读正文。",
        "analyze_status": "分析论文：{title}",
        "analyze": "正在使用 AI 模型分析论文…",
        "update_title_status": "更新 Notion 标题：{title}",
        "update_title": "正在更新页面标题：{title}",
        "delete_status": "删除旧页面块：{title}",
        "delete": "正在删除现有页面块…",
        "write_status": "写入笔记：{title}",
        "write": "正在写入结构化笔记到 Notion…",
        "done_status": "标记 AI Read Done：{title}",
        "done_update": "正在更新 Status 为 AI Read Done…",
        "done": "完成。",
        "failed": "失败：{error}",
        "not_done": "Status 未更新为 AI Read Done。",
        "finished_status": "已完成",
        "finished": "\n完成。",
        "processed": "已处理：{count}",
        "skipped": "已跳过：{count}",
        "failed_count": "失败：{count}",
    },
    "ja": {
        "initializing": "初期化中",
        "querying": "Notion データベースを照会中…",
        "querying_status": "Notion データベースを照会中",
        "stop_requested": "停止要求を受け付けました。次の論文の前に停止します。",
        "stopped": "停止しました",
        "processing": "\n処理中：{title}",
        "page_id": "ページ ID：{page_id}",
        "skipped_status": "スキップ：Status は {status} です。",
        "skipped_website": "スキップ：Website URL がありません。",
        "mark_reading_status": "AI Reading に設定：{title}",
        "mark_reading": "Status を AI Reading に更新中…",
        "fetch_status": "論文を取得中：{title}",
        "fetch": "論文内容を取得中：{website}",
        "fetch_fallback": "Web 取得に失敗しました。Notion ページ内の既存本文を試しています…",
        "fetch_fallback_ok": "Notion ページ内の既存本文を使って分析を続行します。",
        "fetch_fallback_empty": "Notion ページにも読み取れる本文がありません。",
        "analyze_status": "論文を分析中：{title}",
        "analyze": "AI モデルで論文を分析中…",
        "update_title_status": "Notion タイトルを更新：{title}",
        "update_title": "ページタイトルを更新中：{title}",
        "delete_status": "古いページブロックを削除：{title}",
        "delete": "既存ページブロックを削除中…",
        "write_status": "ノートを書き込み中：{title}",
        "write": "構造化ノートを Notion に書き込み中…",
        "done_status": "AI Read Done に設定：{title}",
        "done_update": "Status を AI Read Done に更新中…",
        "done": "完了。",
        "failed": "失敗：{error}",
        "not_done": "Status は AI Read Done に更新されませんでした。",
        "finished_status": "完了",
        "finished": "\n完了。",
        "processed": "処理済み：{count}",
        "skipped": "スキップ：{count}",
        "failed_count": "失敗：{count}",
    },
    "en": {},
}
PIPELINE_TEXT["en"] = {
    "initializing": "Initializing",
    "querying": "Querying Notion database...",
    "querying_status": "Querying Notion database",
    "stop_requested": "Stop requested. Pipeline stopped before next paper.",
    "stopped": "Stopped",
    "processing": "\nProcessing: {title}",
    "page_id": "Page ID: {page_id}",
    "skipped_status": "Skipped: Status is {status}.",
    "skipped_website": "Skipped: missing Website URL.",
    "mark_reading_status": "Marking AI Reading: {title}",
    "mark_reading": "Updating Status to AI Reading...",
    "fetch_status": "Fetching paper: {title}",
    "fetch": "Fetching paper content: {website}",
    "fetch_fallback": "Website fetch failed; trying existing Notion page content...",
    "fetch_fallback_ok": "Using existing Notion page content for analysis.",
    "fetch_fallback_empty": "No readable text found in existing Notion page content.",
    "analyze_status": "Analyzing paper: {title}",
    "analyze": "Analyzing paper with AI model...",
    "update_title_status": "Updating Notion title: {title}",
    "update_title": "Updating page title: {title}",
    "delete_status": "Deleting old page blocks: {title}",
    "delete": "Deleting existing page blocks...",
    "write_status": "Writing notes: {title}",
    "write": "Writing structured notes to Notion...",
    "done_status": "Marking AI Read Done: {title}",
    "done_update": "Updating Status to AI Read Done...",
    "done": "Done.",
    "failed": "Failed: {error}",
    "not_done": "Status was not updated to AI Read Done.",
    "finished_status": "Finished",
    "finished": "\nFinished.",
    "processed": "Processed: {count}",
    "skipped": "Skipped: {count}",
    "failed_count": "Failed: {count}",
}


@dataclass
class PipelineResult:
    processed: int = 0
    skipped: int = 0
    failed: int = 0


class PipelineRunner:
    def __init__(
        self,
        settings: Settings,
        log_callback: LogCallback | None = None,
        status_callback: StatusCallback | None = None,
        conversation_callback: ConversationCallback | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.settings = settings
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.conversation_callback = conversation_callback
        self.should_stop = should_stop or (lambda: False)
        self.language = settings.ui_language if settings.ui_language in PIPELINE_TEXT else "en"

    def run(self) -> PipelineResult:
        result = PipelineResult()
        self._status(self._t("initializing"))
        notion = NotionPaperService(
            notion_token=self.settings.notion_token,
            database_id=self.settings.notion_database_id,
        )
        analyzer = PaperAnalyzer(
            api_key=self.settings.ai_api_key,
            model=self.settings.ai_model,
            base_url=self.settings.ai_base_url,
            system_prompt=self.settings.prompt,
            user_prompt_template=self.settings.user_prompt_template,
            conversation_callback=self.conversation_callback,
        )

        self._log(self._t("querying"))
        self._status(self._t("querying_status"))
        for paper in notion.iter_pages():
            if self.should_stop():
                self._log(self._t("stop_requested"))
                self._status(self._t("stopped"))
                break

            self._log(self._t("processing", title=paper.title))
            self._log(self._t("page_id", page_id=paper.page_id))

            if paper.status not in PROCESSABLE_STATUSES:
                result.skipped += 1
                status_label = paper.status or "(empty)"
                self._log(self._t("skipped_status", status=status_label))
                continue

            if not paper.website:
                result.skipped += 1
                self._log(self._t("skipped_website"))
                continue

            try:
                self._status(self._t("mark_reading_status", title=paper.title))
                self._log(self._t("mark_reading"))
                notion.mark_reading(paper.page_id)

                self._status(self._t("fetch_status", title=paper.title))
                self._log(self._t("fetch", website=paper.website))
                paper_text = self._fetch_with_notion_fallback(notion, paper)

                self._status(self._t("analyze_status", title=paper.title))
                self._log(self._t("analyze"))
                analysis = analyzer.analyze(
                    title=paper.title,
                    website=paper.website,
                    paper_text=paper_text,
                )

                paper_title = analysis.get("paper_title")
                if paper_title:
                    self._status(self._t("update_title_status", title=paper_title))
                    self._log(self._t("update_title", title=paper_title))
                    notion.update_title(paper.page_id, paper_title)

                self._status(self._t("delete_status", title=paper.title))
                self._log(self._t("delete"))
                notion.delete_all_blocks(paper.page_id)

                self._status(self._t("write_status", title=paper.title))
                self._log(self._t("write"))
                notion.write_analysis(paper.page_id, analysis)

                self._status(self._t("done_status", title=paper.title))
                self._log(self._t("done_update"))
                notion.mark_done(paper.page_id)

                result.processed += 1
                self._log(self._t("done"))
            except (FetchError, AnalysisError, Exception) as exc:
                result.failed += 1
                self._log(self._t("failed", error=exc))
                self._log(self._t("not_done"))

        self._status(self._t("finished_status"))
        self._log(self._t("finished"))
        self._log(self._t("processed", count=result.processed))
        self._log(self._t("skipped", count=result.skipped))
        self._log(self._t("failed_count", count=result.failed))
        return result

    def _t(self, key: str, **kwargs: object) -> str:
        template = PIPELINE_TEXT.get(self.language, PIPELINE_TEXT["en"]).get(key, PIPELINE_TEXT["en"][key])
        return template.format(**kwargs)

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def _status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)

    def _fetch_with_notion_fallback(self, notion: NotionPaperService, paper: PaperPage) -> str:
        try:
            return fetch_paper_text(paper.website, self.settings.paper_text_limit)
        except FetchError as fetch_error:
            self._log(self._t("fetch_fallback"))
            page_text = clean_text(notion.read_page_text(paper.page_id))
            if page_text:
                self._log(self._t("fetch_fallback_ok"))
                return page_text[: self.settings.paper_text_limit]
            self._log(self._t("fetch_fallback_empty"))
            raise fetch_error
