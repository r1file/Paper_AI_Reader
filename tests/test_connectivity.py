from paper_ai_reader.connectivity import choose_default_model


def test_choose_default_model_prefers_openai_default_without_base_url() -> None:
    assert choose_default_model(["random-chat-model", "gpt-4o-mini"]) == "gpt-4o-mini"


def test_choose_default_model_prefers_provider_specific_model() -> None:
    assert choose_default_model(["base", "deepseek-chat"], "https://api.deepseek.com/v1") == "deepseek-chat"


def test_choose_default_model_falls_back_to_first_clean_model() -> None:
    assert choose_default_model(["", "embedding-only", "another"]) == "embedding-only"
