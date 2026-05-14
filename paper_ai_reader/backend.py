from __future__ import annotations

from collections.abc import Callable

from paper_ai_reader.analyzer import ConversationCallback
from paper_ai_reader.config import Settings
from paper_ai_reader.connectivity import (
    CheckResult,
    ConnectivityReport,
    ConnectivityTester,
    choose_default_model,
)
from paper_ai_reader.pipeline import LogCallback, PipelineResult, PipelineRunner, StatusCallback


class PaperAIReaderBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def check_notion(self) -> CheckResult:
        return ConnectivityTester(self.settings).check_notion()

    def check_ai(self) -> CheckResult:
        return ConnectivityTester(self.settings).check_ai()

    def check_all(self) -> ConnectivityReport:
        return ConnectivityTester(self.settings).check_all()

    def list_ai_models(self) -> list[str]:
        return ConnectivityTester(self.settings).list_ai_models()

    def default_ai_model(self, models: list[str]) -> str:
        return choose_default_model(models, self.settings.ai_base_url)

    def run_pipeline(
        self,
        log_callback: LogCallback | None = None,
        status_callback: StatusCallback | None = None,
        conversation_callback: ConversationCallback | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> PipelineResult:
        return PipelineRunner(
            settings=self.settings,
            log_callback=log_callback,
            status_callback=status_callback,
            conversation_callback=conversation_callback,
            should_stop=should_stop,
        ).run()
