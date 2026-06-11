from paper_ai_reader.config import Settings, load_settings, save_settings_xml


def test_save_and_load_settings_xml_round_trip(tmp_path) -> None:
    config_path = tmp_path / "settings.xml"
    settings = Settings(
        notion_token="notion",
        notion_database_id="database",
        ai_api_key="api-key",
        ai_model="model",
        ai_base_url="https://api.example.com/v1",
        paper_text_limit=12345,
        ui_language="en",
        theme_mode="dark",
        prompt_language="ja",
        profile="gui",
        ai_model_explicit=True,
    )

    save_settings_xml(settings, config_path=config_path, profile="gui")
    loaded = load_settings(config_path=config_path, validate_required=True, profile="gui")

    assert loaded.notion_token == "notion"
    assert loaded.notion_database_id == "database"
    assert loaded.ai_api_key == "api-key"
    assert loaded.ai_model == "model"
    assert loaded.ai_base_url == "https://api.example.com/v1"
    assert loaded.paper_text_limit == 12345
    assert loaded.ui_language == "en"
    assert loaded.theme_mode == "dark"
    assert loaded.prompt_language == "ja"
    assert loaded.ai_model_explicit is True
