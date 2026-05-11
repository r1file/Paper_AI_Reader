import os
from dataclasses import dataclass

from dotenv import load_dotenv


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEXT_LIMIT = 50_000


@dataclass(frozen=True)
class Settings:
    notion_token: str
    notion_database_id: str
    openai_api_key: str
    openai_model: str = DEFAULT_MODEL
    paper_text_limit: int = DEFAULT_TEXT_LIMIT


def load_settings() -> Settings:
    load_dotenv()

    notion_token = os.getenv("NOTION_TOKEN")
    notion_database_id = os.getenv("NOTION_DATABASE_ID")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    paper_text_limit = int(os.getenv("PAPER_TEXT_LIMIT", str(DEFAULT_TEXT_LIMIT)))

    missing = [
        name
        for name, value in {
            "NOTION_TOKEN": notion_token,
            "NOTION_DATABASE_ID": notion_database_id,
            "OPENAI_API_KEY": openai_api_key,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return Settings(
        notion_token=notion_token,
        notion_database_id=notion_database_id,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        paper_text_limit=paper_text_limit,
    )
