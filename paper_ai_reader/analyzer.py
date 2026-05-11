from __future__ import annotations

import json
from typing import Any

from openai import OpenAI


SYSTEM_PROMPT = """你是一个帮助机器人方向研究者阅读论文的中文科研助手。

研究方向：
- LLM
- ROS2
- TurtleBot3
- Human-Robot Interaction (HRI)
- 情绪感知交互
- 从人的情感输入生成机器人行为/控制指令

请重点分析论文如何启发、支持或迁移到上述研究方向。
除 GitHub/code URL 外，所有字段内容必须使用中文。
只返回符合 schema 的有效 JSON。
"""


ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
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
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def analyze(self, title: str, website: str, paper_text: str) -> dict[str, Any]:
        prompt = f"""请分析这篇论文，并生成结构化 JSON。

标题：{title}
网址：{website}

论文文本：
{paper_text}
"""
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
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
            return normalize_analysis(json.loads(response.output_text))
        except Exception as responses_error:
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
                {"role": "system", "content": SYSTEM_PROMPT},
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
        return normalize_analysis(json.loads(content))


def normalize_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    rating = analysis.get("rating", 1)
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 1

    return {
        "summary": str(analysis.get("summary") or "").strip(),
        "idea": str(analysis.get("idea") or "").strip(),
        "rating": min(5, max(1, rating)),
        "reason": str(analysis.get("reason") or "").strip(),
        "code_available": bool(analysis.get("code_available")),
        "code_url": str(analysis.get("code_url") or "").strip(),
    }
