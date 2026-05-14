from __future__ import annotations

from paper_ai_reader.backend import PaperAIReaderBackend
from paper_ai_reader.config import load_settings


def main() -> None:
    settings = load_settings(profile="cli")
    backend = PaperAIReaderBackend(settings)
    report = backend.check_all()
    if not report.ok:
        print(report.notion.message)
        print(report.ai.message)
        raise SystemExit(1)
    backend.run_pipeline()


if __name__ == "__main__":
    main()
