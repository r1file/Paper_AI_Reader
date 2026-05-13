from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from paper_ai_reader.analyzer import AnalysisError, ConversationCallback, PaperAnalyzer
from paper_ai_reader.config import Settings
from paper_ai_reader.fetcher import FetchError, fetch_paper_text
from paper_ai_reader.notion_service import NotionPaperService


LogCallback = Callable[[str], None]
StatusCallback = Callable[[str], None]


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

    def run(self) -> PipelineResult:
        result = PipelineResult()
        self._status("Initializing")
        notion = NotionPaperService(
            notion_token=self.settings.notion_token,
            database_id=self.settings.notion_database_id,
        )
        analyzer = PaperAnalyzer(
            api_key=self.settings.ai_api_key,
            model=self.settings.ai_model,
            base_url=self.settings.ai_base_url,
            system_prompt=self.settings.prompt,
            conversation_callback=self.conversation_callback,
        )

        self._log("Querying Notion database...")
        self._status("Querying Notion database")
        for paper in notion.iter_pending_pages():
            if self.should_stop():
                self._log("Stop requested. Pipeline stopped before next paper.")
                self._status("Stopped")
                break

            self._log(f"\nProcessing: {paper.title}")
            self._log(f"Page ID: {paper.page_id}")

            if not paper.website:
                result.skipped += 1
                self._log("Skipped: missing Website URL.")
                continue

            try:
                self._status(f"Marking AI Reading: {paper.title}")
                self._log("Updating Status to AI Reading...")
                notion.mark_reading(paper.page_id)

                self._status(f"Fetching paper: {paper.title}")
                self._log(f"Fetching paper content: {paper.website}")
                paper_text = fetch_paper_text(paper.website, self.settings.paper_text_limit)

                self._status(f"Analyzing paper: {paper.title}")
                self._log("Analyzing paper with AI model...")
                analysis = analyzer.analyze(
                    title=paper.title,
                    website=paper.website,
                    paper_text=paper_text,
                )

                paper_title = analysis.get("paper_title")
                if paper_title:
                    self._status(f"Updating Notion title: {paper_title}")
                    self._log(f"Updating page title: {paper_title}")
                    notion.update_title(paper.page_id, paper_title)

                self._status(f"Deleting old page blocks: {paper.title}")
                self._log("Deleting existing page blocks...")
                notion.delete_all_blocks(paper.page_id)

                self._status(f"Writing notes: {paper.title}")
                self._log("Writing structured notes to Notion...")
                notion.write_analysis(paper.page_id, analysis)

                self._status(f"Marking AI Read Done: {paper.title}")
                self._log("Updating Status to AI Read Done...")
                notion.mark_done(paper.page_id)

                result.processed += 1
                self._log("Done.")
            except (FetchError, AnalysisError, Exception) as exc:
                result.failed += 1
                self._log(f"Failed: {exc}")
                self._log("Status was not updated to AI Read Done.")

        self._status("Finished")
        self._log("\nFinished.")
        self._log(f"Processed: {result.processed}")
        self._log(f"Skipped: {result.skipped}")
        self._log(f"Failed: {result.failed}")
        return result

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def _status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)
