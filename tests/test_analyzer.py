import json

import pytest

from paper_ai_reader.analyzer import (
    AnalysisError,
    build_analysis_prompt,
    normalize_analysis,
    parse_analysis_json,
    strip_json_fence,
)


def test_strip_json_fence_handles_json_code_block() -> None:
    assert strip_json_fence('```json\n{"summary": "ok"}\n```') == '{"summary": "ok"}'


def test_parse_analysis_json_extracts_object_from_text() -> None:
    parsed = parse_analysis_json('result:\n{"rating": 4, "summary": "ok"}\nthanks')
    assert parsed == {"rating": 4, "summary": "ok"}


def test_parse_analysis_json_rejects_non_object() -> None:
    with pytest.raises(AnalysisError):
        parse_analysis_json(json.dumps(["not", "an", "object"]))


def test_normalize_analysis_clamps_rating_and_dedupes_keywords() -> None:
    normalized = normalize_analysis(
        {
            "paper_title": "  A Paper  ",
            "summary": " summary ",
            "idea": " idea ",
            "rating": "9",
            "reason": " reason ",
            "keywords": "LLM, llm; ROS2\n HRI ",
            "code_available": "yes",
            "code_url": " https://github.com/example/repo ",
        }
    )

    assert normalized["paper_title"] == "A Paper"
    assert normalized["rating"] == 5
    assert normalized["keywords"] == ["LLM", "ROS2", "HRI"]
    assert normalized["code_available"] is True
    assert normalized["code_url"] == "https://github.com/example/repo"


def test_build_analysis_prompt_reports_unknown_placeholder() -> None:
    with pytest.raises(AnalysisError, match="unknown placeholder"):
        build_analysis_prompt("title", "https://example.com", "body", "{missing}")
