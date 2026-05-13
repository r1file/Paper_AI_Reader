from __future__ import annotations

from paper_ai_reader.config import load_settings
from paper_ai_reader.pipeline import PipelineRunner


def main() -> None:
    settings = load_settings(profile="cli")
    PipelineRunner(settings).run()


if __name__ == "__main__":
    main()
