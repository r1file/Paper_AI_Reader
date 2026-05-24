from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from notion_client import Client as NotionClient
from notion_client.errors import APIResponseError, RequestTimeoutError
from openai import APIConnectionError, AuthenticationError, OpenAI

from paper_ai_reader.config import Settings


PREFERRED_MODEL_KEYWORDS = ("chat", "turbo", "mini", "instruct")

CONNECTIVITY_TEXT = {
    "zh": {
        "notion_token_empty": "Notion Token 为空",
        "notion_database_empty": "Notion Database ID 为空",
        "notion_ok": "Notion API 正常",
        "notion_token_invalid": "无效的 Notion Token",
        "notion_database_invalid": "无效的 Notion Database ID",
        "notion_error": "Notion API 异常，请查看 Dashboard 运行日志",
        "notion_timeout": "Notion API 连接超时",
        "ai_key_empty": "AI API Key 为空",
        "ai_model_empty": "AI Model 为空",
        "ai_ok": "AI 服务商 API 正常",
        "ai_key_invalid": "无效的 AI API Key",
        "ai_base_invalid": "无效服务商链接或网络不可达",
        "ai_error": "AI 服务商异常，请查看 Dashboard 运行日志",
        "model_key_empty": "AI API Key 为空",
        "model_empty": "服务商没有返回可用模型",
    },
    "ja": {
        "notion_token_empty": "Notion Token が空です",
        "notion_database_empty": "Notion Database ID が空です",
        "notion_ok": "Notion API は正常です",
        "notion_token_invalid": "Notion Token が無効です",
        "notion_database_invalid": "Notion Database ID が無効です",
        "notion_error": "Notion API エラーです。Dashboard ログを確認してください",
        "notion_timeout": "Notion API がタイムアウトしました",
        "ai_key_empty": "AI API Key が空です",
        "ai_model_empty": "AI Model が空です",
        "ai_ok": "AI Provider API は正常です",
        "ai_key_invalid": "AI API Key が無効です",
        "ai_base_invalid": "Provider URL が無効、またはネットワーク到達不能です",
        "ai_error": "AI Provider エラーです。Dashboard ログを確認してください",
        "model_key_empty": "AI API Key が空です",
        "model_empty": "Provider から利用可能なモデルが返されませんでした",
    },
    "en": {
        "notion_token_empty": "Notion Token is empty",
        "notion_database_empty": "Notion Database ID is empty",
        "notion_ok": "Notion API is OK",
        "notion_token_invalid": "Invalid Notion Token",
        "notion_database_invalid": "Invalid Notion Database ID",
        "notion_error": "Notion API error. Check Dashboard logs",
        "notion_timeout": "Notion API timed out",
        "ai_key_empty": "AI API Key is empty",
        "ai_model_empty": "AI Model is empty",
        "ai_ok": "AI provider API is OK",
        "ai_key_invalid": "Invalid AI API Key",
        "ai_base_invalid": "Invalid provider URL or network unreachable",
        "ai_error": "AI provider error. Check Dashboard logs",
        "model_key_empty": "AI API Key is empty",
        "model_empty": "Provider returned no available models",
    },
}


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
        self.language = settings.ui_language if settings.ui_language in CONNECTIVITY_TEXT else "en"

    def _t(self, key: str) -> str:
        return CONNECTIVITY_TEXT.get(self.language, CONNECTIVITY_TEXT["en"])[key]

    def check_all(self) -> ConnectivityReport:
        return ConnectivityReport(notion=self.check_notion(), ai=self.check_ai())

    def check_notion(self) -> CheckResult:
        if not self.settings.notion_token:
            return CheckResult("notion", CheckStatus.ERROR, self._t("notion_token_empty"))
        if not self.settings.notion_database_id:
            return CheckResult("notion", CheckStatus.ERROR, self._t("notion_database_empty"))

        try:
            notion = NotionClient(
                options={"auth": self.settings.notion_token, "timeout_ms": 20_000}
            )
            notion.databases.retrieve(database_id=self.settings.notion_database_id)
            return CheckResult("notion", CheckStatus.OK, self._t("notion_ok"))
        except APIResponseError as exc:
            code = str(getattr(exc, "code", "") or "")
            status = int(getattr(exc, "status", 0) or 0)
            body = str(exc)
            if status == 401 or "unauthorized" in code or "Invalid token" in body:
                return CheckResult("notion", CheckStatus.ERROR, self._t("notion_token_invalid"), body)
            if status == 404 or "object_not_found" in code:
                return CheckResult("notion", CheckStatus.ERROR, self._t("notion_database_invalid"), body)
            return CheckResult("notion", CheckStatus.ERROR, self._t("notion_error"), body)
        except RequestTimeoutError as exc:
            return CheckResult("notion", CheckStatus.ERROR, self._t("notion_timeout"), str(exc))
        except Exception as exc:
            return CheckResult("notion", CheckStatus.ERROR, self._t("notion_error"), str(exc))

    def check_ai(self) -> CheckResult:
        if not self.settings.ai_api_key:
            return CheckResult("ai", CheckStatus.ERROR, self._t("ai_key_empty"))
        if not self.settings.ai_model:
            return CheckResult("ai", CheckStatus.ERROR, self._t("ai_model_empty"))

        try:
            client_args = {"api_key": self.settings.ai_api_key, "timeout": 20.0}
            if self.settings.ai_base_url:
                client_args["base_url"] = self.settings.ai_base_url
            client = OpenAI(**client_args)
            client.models.list()
            return CheckResult("ai", CheckStatus.OK, self._t("ai_ok"))
        except AuthenticationError as exc:
            return CheckResult("ai", CheckStatus.ERROR, self._t("ai_key_invalid"), str(exc))
        except APIConnectionError as exc:
            return CheckResult("ai", CheckStatus.ERROR, self._t("ai_base_invalid"), str(exc))
        except Exception as exc:
            text = str(exc)
            lowered = text.lower()
            if "unauthorized" in lowered or "incorrect api key" in lowered:
                return CheckResult("ai", CheckStatus.ERROR, self._t("ai_key_invalid"), text)
            if "connection" in lowered or "name resolution" in lowered or "nodename" in lowered:
                return CheckResult("ai", CheckStatus.ERROR, self._t("ai_base_invalid"), text)
            return CheckResult("ai", CheckStatus.ERROR, self._t("ai_error"), text)

    def list_ai_models(self) -> list[str]:
        if not self.settings.ai_api_key:
            raise ValueError(self._t("model_key_empty"))

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
            raise RuntimeError(self._t("model_empty"))
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
