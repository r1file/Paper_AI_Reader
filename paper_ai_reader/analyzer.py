from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from openai import OpenAI

from paper_ai_reader.prompts import get_default_prompt

ConversationCallback = Callable[[str, str], None]


ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "paper_title": {
            "type": "string",
            "description": "从论文正文中识别出的真实论文标题，保留原文标题，不要翻译。",
        },
        "summary": {
            "type": "string",
            "description": "中文论文总结，聚焦方法、贡献与发现。",
        },
        "idea": {
            "type": "string",
            "description": "中文说明如何将论文迁移或启发到用户的研究。",
        },
        "rating": {
            "type": "integer",
            "description": "与用户研究方向的相关性，1 到 5。",
        },
        "reason": {
            "type": "string",
            "description": "中文简短说明评分理由。",
        },
        "code_available": {
            "type": "boolean",
            "description": "论文文本是否显示代码可用。",
        },
        "code_url": {
            "type": "string",
            "description": "如果发现 GitHub 或代码 URL 则填写，否则为空字符串。",
        },
    },
    "required": [
        "paper_title",
        "summary",
        "idea",
        "rating",
        "reason",
        "code_available",
        "code_url",
    ],
    "additionalProperties": False,
}


class AnalysisError(RuntimeError):
    pass


class PaperAnalyzer:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        system_prompt: str | None = None,
        conversation_callback: ConversationCallback | None = None,
    ) -> None:
        client_args: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_args["base_url"] = base_url
        self.client = OpenAI(**client_args)
        self.model = model
        self.system_prompt = system_prompt or get_default_prompt("zh")
        self.conversation_callback = conversation_callback

    def analyze(self, title: str, website: str, paper_text: str) -> dict[str, Any]:
        prompt = f"""请分析这篇论文，并生成结构化 JSON。

标题：{title}
网址：{website}

论文文本：
{paper_text}
"""
        self._emit_conversation("system", self.system_prompt)
        self._emit_conversation("user", prompt)
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "paper_ai_reader_analysis",
                        "schema": ANALYSIS_SCHEMA,
                        "strict": True,
                    }
                },
            )
            self._emit_conversation("assistant", response.output_text)
            return normalize_analysis(json.loads(response.output_text))
        except Exception as responses_error:
            self._emit_conversation(
                "status",
                f"Responses API failed; trying Chat Completions fallback: {responses_error}",
            )
            try:
                return self._analyze_with_chat_completions(title, website, paper_text)
            except Exception as chat_error:
                raise AnalysisError(
                    f"OpenAI analysis failed. Responses error: {responses_error}; "
                    f"Chat Completions fallback error: {chat_error}"
                ) from chat_error

    def _analyze_with_chat_completions(
        self,
        title: str,
        website: str,
        paper_text: str,
    ) -> dict[str, Any]:
        prompt = f"""请分析这篇论文，并生成结构化 JSON。

标题：{title}
网址：{website}

论文文本：
{paper_text}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "paper_ai_reader_analysis",
                    "schema": ANALYSIS_SCHEMA,
                    "strict": True,
                },
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise AnalysisError("OpenAI returned an empty message.")
        self._emit_conversation("assistant", content)
        return normalize_analysis(json.loads(content))

    def _emit_conversation(self, role: str, content: str) -> None:
        if self.conversation_callback:
            self.conversation_callback(role, content)


def normalize_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    rating = analysis.get("rating", 1)
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 1

    return {
        "paper_title": str(analysis.get("paper_title") or "").strip(),
        "summary": str(analysis.get("summary") or "").strip(),
        "idea": str(analysis.get("idea") or "").strip(),
        "rating": min(5, max(1, rating)),
        "reason": str(analysis.get("reason") or "").strip(),
        "code_available": bool(analysis.get("code_available")),
        "code_url": str(analysis.get("code_url") or "").strip(),
    }
