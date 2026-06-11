from paper_ai_reader.notion_service import (
    RICH_TEXT_LIMIT,
    build_analysis_blocks,
    normalize_keywords_for_notion,
    split_rich_text,
)


def test_normalize_keywords_for_notion_limits_and_dedupes() -> None:
    keywords = normalize_keywords_for_notion(
        [" LLM ", "llm", "ROS,2", "", "HRI", "A" * 100, "extra", "overflow"]
    )

    assert keywords == ["LLM", "ROS 2", "HRI", "A" * 80, "extra", "overflow"]


def test_split_rich_text_keeps_chunks_within_notion_limit() -> None:
    chunks = split_rich_text(("word " * 900).strip())

    assert chunks
    assert all(0 < len(chunk) <= RICH_TEXT_LIMIT for chunk in chunks)
    assert " ".join(chunks).replace("  ", " ") == ("word " * 900).strip()


def test_build_analysis_blocks_contains_expected_sections() -> None:
    blocks = build_analysis_blocks(
        {
            "summary": "Summary",
            "idea": "Idea",
            "rating": 4,
            "reason": "Relevant",
            "code_available": True,
            "code_url": "https://github.com/example/repo",
        },
        "en",
    )

    block_text = [
        block[block["type"]]["rich_text"][0]["text"]["content"]
        for block in blocks
    ]

    assert any("Summary" in text for text in block_text)
    assert any("Idea for My Research" in text for text in block_text)
    assert any("★★★★☆" in text for text in block_text)
    assert any("https://github.com/example/repo" in text for text in block_text)
