from __future__ import annotations

import json
import re
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
        user_prompt_template: str | None = None,
        conversation_callback: ConversationCallback | None = None,
    ) -> None:
        client_args: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_args["base_url"] = base_url
        self.client = OpenAI(**client_args)
        self.model = model
        self.system_prompt = system_prompt or get_default_prompt("zh")
        self.user_prompt_template = user_prompt_template or ""
        self.conversation_callback = conversation_callback

    def analyze(self, title: str, website: str, paper_text: str) -> dict[str, Any]:
        prompt = build_analysis_prompt(title, website, paper_text, self.user_prompt_template)
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
            return normalize_analysis(parse_analysis_json(response.output_text))
        except Exception as responses_error:
            try:
                return self._analyze_with_chat_completions(title, website, paper_text)
            except Exception as schema_error:
                try:
                    return self._analyze_with_json_object(title, website, paper_text)
                except Exception as json_object_error:
                    try:
                        return self._analyze_with_plain_chat(title, website, paper_text)
                    except Exception as plain_error:
                        raise AnalysisError(
                            f"OpenAI-compatible analysis failed. Responses error: {responses_error}; "
                            f"Chat JSON schema error: {schema_error}; "
                            f"Chat JSON object error: {json_object_error}; "
                            f"Plain chat JSON error: {plain_error}"
                        ) from plain_error

    def _analyze_with_chat_completions(
        self,
        title: str,
        website: str,
        paper_text: str,
    ) -> dict[str, Any]:
        prompt = build_analysis_prompt(title, website, paper_text, self.user_prompt_template)
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
        return normalize_analysis(parse_analysis_json(content))

    def _analyze_with_json_object(
        self,
        title: str,
        website: str,
        paper_text: str,
    ) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": build_analysis_prompt(title, website, paper_text, self.user_prompt_template)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise AnalysisError("OpenAI-compatible provider returned an empty message.")
        self._emit_conversation("assistant", content)
        return normalize_analysis(parse_analysis_json(content))

    def _analyze_with_plain_chat(
        self,
        title: str,
        website: str,
        paper_text: str,
    ) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": build_analysis_prompt(title, website, paper_text, self.user_prompt_template)},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise AnalysisError("OpenAI-compatible provider returned an empty message.")
        self._emit_conversation("assistant", content)
        return normalize_analysis(parse_analysis_json(content))

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


def build_analysis_prompt(
    title: str,
    website: str,
    paper_text: str,
    template: str = "",
) -> str:
    if not template:
        raise AnalysisError("Missing user prompt template.")
    try:
        return template.format(
            title=title,
            website=website,
            paper_text=paper_text,
        )
    except KeyError as exc:
        raise AnalysisError(f"User prompt template has an unknown placeholder: {exc}") from exc


def parse_analysis_json(content: str) -> dict[str, Any]:
    cleaned = strip_json_fence(content).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise AnalysisError("AI response JSON must be an object.")
    return parsed


def strip_json_fence(content: str) -> str:
    text = content.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1)
    return text
