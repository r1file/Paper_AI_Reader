from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from notion_client import Client as NotionClient
from notion_client.errors import APIResponseError, RequestTimeoutError
from openai import APIConnectionError, AuthenticationError, OpenAI

from paper_ai_reader.config import Settings


PREFERRED_MODEL_KEYWORDS = ("chat", "turbo", "mini", "instruct")


class CheckStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == CheckStatus.OK


@dataclass(frozen=True)
class ConnectivityReport:
    notion: CheckResult
    ai: CheckResult

    @property
    def ok(self) -> bool:
        return self.notion.ok and self.ai.ok


class ConnectivityTester:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def check_all(self) -> ConnectivityReport:
        return ConnectivityReport(notion=self.check_notion(), ai=self.check_ai())

    def check_notion(self) -> CheckResult:
        if not self.settings.notion_token:
            return CheckResult("notion", CheckStatus.ERROR, "Notion Token 为空")
        if not self.settings.notion_database_id:
            return CheckResult("notion", CheckStatus.ERROR, "Notion Database ID 为空")

        try:
            notion = NotionClient(
                options={"auth": self.settings.notion_token, "timeout_ms": 20_000}
            )
            notion.databases.retrieve(database_id=self.settings.notion_database_id)
            return CheckResult("notion", CheckStatus.OK, "Notion API 正常")
        except APIResponseError as exc:
            code = str(getattr(exc, "code", "") or "")
            status = int(getattr(exc, "status", 0) or 0)
            body = str(exc)
            if status == 401 or "unauthorized" in code or "Invalid token" in body:
                return CheckResult("notion", CheckStatus.ERROR, "无效的 Notion Token", body)
            if status == 404 or "object_not_found" in code:
                return CheckResult("notion", CheckStatus.ERROR, "无效的 Notion Database ID", body)
            return CheckResult("notion", CheckStatus.ERROR, "Notion API 异常，请查看 Dashboard 运行日志", body)
        except RequestTimeoutError as exc:
            return CheckResult("notion", CheckStatus.ERROR, "Notion API 连接超时", str(exc))
        except Exception as exc:
            return CheckResult("notion", CheckStatus.ERROR, "Notion API 异常，请查看 Dashboard 运行日志", str(exc))

    def check_ai(self) -> CheckResult:
        if not self.settings.ai_api_key:
            return CheckResult("ai", CheckStatus.ERROR, "AI API Key 为空")
        if not self.settings.ai_model:
            return CheckResult("ai", CheckStatus.ERROR, "AI Model 为空")

        try:
            client_args = {"api_key": self.settings.ai_api_key, "timeout": 20.0}
            if self.settings.ai_base_url:
                client_args["base_url"] = self.settings.ai_base_url
            client = OpenAI(**client_args)
            client.models.list()
            return CheckResult("ai", CheckStatus.OK, "AI 服务商 API 正常")
        except AuthenticationError as exc:
            return CheckResult("ai", CheckStatus.ERROR, "无效的 AI API Key", str(exc))
        except APIConnectionError as exc:
            return CheckResult("ai", CheckStatus.ERROR, "无效服务商链接或网络不可达", str(exc))
        except Exception as exc:
            text = str(exc)
            lowered = text.lower()
            if "unauthorized" in lowered or "incorrect api key" in lowered:
                return CheckResult("ai", CheckStatus.ERROR, "无效的 AI API Key", text)
            if "connection" in lowered or "name resolution" in lowered or "nodename" in lowered:
                return CheckResult("ai", CheckStatus.ERROR, "无效服务商链接或网络不可达", text)
            return CheckResult("ai", CheckStatus.ERROR, "AI 服务商异常，请查看 Dashboard 运行日志", text)

    def list_ai_models(self) -> list[str]:
        if not self.settings.ai_api_key:
            raise ValueError("AI API Key 为空")

        client_args = {"api_key": self.settings.ai_api_key, "timeout": 20.0}
        if self.settings.ai_base_url:
            client_args["base_url"] = self.settings.ai_base_url
        client = OpenAI(**client_args)
        models = client.models.list()
        model_ids = sorted(
            {
                str(model.id).strip()
                for model in models.data
                if getattr(model, "id", None)
            }
        )
        if not model_ids:
            raise RuntimeError("服务商没有返回可用模型")
        return model_ids


def choose_default_model(models: list[str], base_url: str | None = None) -> str:
    if not models:
        return ""
    clean_models = [model.strip() for model in models if model.strip()]
    if not clean_models:
        return ""

    lowered_base_url = (base_url or "").lower()
    if "deepseek" in lowered_base_url:
        for preferred in ("deepseek-chat", "deepseek-reasoner"):
            if preferred in clean_models:
                return preferred

    for keyword in PREFERRED_MODEL_KEYWORDS:
        for model in clean_models:
            if keyword in model.lower():
                return model
    return clean_models[0]
