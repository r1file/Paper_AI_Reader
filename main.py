from __future__ import annotations

from paper_ai_reader.analyzer import AnalysisError, PaperAnalyzer
from paper_ai_reader.config import load_settings
from paper_ai_reader.fetcher import FetchError, fetch_paper_text
from paper_ai_reader.notion_service import NotionPaperService


def main() -> None:
    settings = load_settings()
    notion = NotionPaperService(
        notion_token=settings.notion_token,
        database_id=settings.notion_database_id,
    )
    analyzer = PaperAnalyzer(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )

    processed = 0
    skipped = 0
    failed = 0

    print("Querying Notion database...")
    for paper in notion.iter_pending_pages():
        print(f"\nProcessing: {paper.title}")
        print(f"Page ID: {paper.page_id}")

        if not paper.website:
            skipped += 1
            print("Skipped: missing Website URL.")
            continue

        try:
            print("Updating Status to AI Reading...")
            notion.mark_reading(paper.page_id)

            print(f"Fetching paper content: {paper.website}")
            paper_text = fetch_paper_text(paper.website, settings.paper_text_limit)

            print("Analyzing paper with OpenAI...")
            analysis = analyzer.analyze(
                title=paper.title,
                website=paper.website,
                paper_text=paper_text,
            )

            paper_title = analysis.get("paper_title")
            if paper_title:
                print(f"Updating page title: {paper_title}")
                notion.update_title(paper.page_id, paper_title)

            print("Deleting existing page blocks...")
            notion.delete_all_blocks(paper.page_id)

            print("Writing structured notes to Notion...")
            notion.write_analysis(paper.page_id, analysis)

            print("Updating Status to AI Read Done...")
            notion.mark_done(paper.page_id)

            processed += 1
            print("Done.")
        except (FetchError, AnalysisError, Exception) as exc:
            failed += 1
            print(f"Failed: {exc}")
            print("Status was not updated.")

    print("\nFinished.")
    print(f"Processed: {processed}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
