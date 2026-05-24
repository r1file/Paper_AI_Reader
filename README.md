# Paper AI Reader

**Language:** [English](README.md) | [中文](README.zh.md) | [日本語](README.ja.md)

Paper AI Reader is a Python tool that turns papers saved in a Notion database into structured AI-generated research notes.

It reads pending papers from Notion, extracts text from webpages or PDFs, analyzes the paper with an OpenAI-compatible AI provider, updates the Notion page title with the real paper title, writes research keywords, and replaces the page body with structured notes.

## Highlights

- CLI pipeline and PySide6 desktop GUI
- Chinese, Japanese, and English UI
- Chinese, Japanese, and English prompt output
- XML-only runtime configuration
- OpenAI-compatible provider support through `base_url`
- Notion `data_sources` query support
- Webpage and PDF text extraction
- Fallback to existing Notion page text when website fetching fails
- Real paper title detection and Notion title update
- Keyword extraction into the Notion `Keywords` property
- Existing Notion page blocks are deleted only after fetching and AI analysis succeed

## GUI

Start the desktop GUI:

```bash
python gui.py
```

The GUI contains:

- `Dashboard`: start or stop the reading pipeline, inspect logs, and view model request/response text.
- `Prompt`: choose the note output language and preview prompt XML.
- `Setting`: configure Notion, AI provider, model, base URL, and text limit.

While a connectivity check, model refresh, or reading pipeline is running, the GUI temporarily locks Prompt, Setting, and language controls to prevent mid-run configuration drift. The Setting page also warns before discarding unsaved changes.

## CLI

Run the CLI pipeline:

```bash
python main.py
```

The CLI validates Notion and AI connectivity before starting the pipeline.

## Notion Database

The Notion database should contain:

| Property | Type | Required | Description |
| --- | --- | --- | --- |
| `Title` | Title | Yes | Page title. The app can replace it with the real paper title. |
| `Website` | URL | Yes | Paper webpage or PDF URL. |
| `Status` | Status or Select | Yes | Workflow status. |
| `Keywords` | Multi-select, Select, or Rich text | Recommended | AI-extracted keywords. |

Processable statuses:

- `TBD`
- `AI Reading`

Skipped statuses:

- `AI Read Done`
- `Human Reading`
- `DONE`

The app writes only:

- `AI Reading`
- `AI Read Done`

## Installation

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Configuration is XML-based. CLI and GUI read the same settings file. Copy the example:

```bash
cp config/settings.example.xml config/settings.xml
```

Then edit `config/settings.xml`.

Important config fields:

- `notion_token`
- `notion_database_id`
- `ai_api_key`
- `ai_model`
- `ai_base_url`
- `paper_text_limit`
- `ui_language`
- `theme_mode`
- `prompt_language`

Leave `ai_base_url` empty for the default OpenAI API. For compatible providers, use their `/v1` base URL.

Prompt XML files live in:

- `prompts/zh.xml`
- `prompts/ja.xml`
- `prompts/en.xml`

Each prompt XML contains both `system_prompt` and `user_prompt_template`. The template supports `{title}`, `{website}`, and `{paper_text}`.

## Pipeline

1. Query the Notion database.
2. Select pages whose status is `TBD` or `AI Reading`.
3. Mark the page as `AI Reading`.
4. Fetch text from the `Website` URL.
5. If fetching fails, try existing Notion page text.
6. Analyze the paper with the configured AI provider.
7. Parse structured JSON from the model response.
8. Update the Notion page title with `paper_title`.
9. Update the `Keywords` property when available.
10. Delete existing page blocks.
11. Write structured notes.
12. Mark the page as `AI Read Done`.

## Generated JSON

The AI response is normalized to this shape:

```json
{
  "paper_title": "Real paper title",
  "summary": "...",
  "idea": "...",
  "rating": 5,
  "reason": "...",
  "keywords": ["HRI", "ROS2", "emotion-aware interaction"],
  "code_available": true,
  "code_url": "https://github.com/example/project"
}
```

## Project Structure

```text
.
├── main.py
├── gui.py
├── requirements.txt
├── config
│   └── settings.example.xml
├── prompts
│   ├── zh.xml
│   ├── ja.xml
│   └── en.xml
├── paper_ai_reader
│   ├── analyzer.py
│   ├── backend.py
│   ├── config.py
│   ├── connectivity.py
│   ├── fetcher.py
│   ├── notion_service.py
│   ├── pipeline.py
│   ├── prompts.py
│   └── gui
│       ├── app.py
│       └── i18n.py
├── test_notion.py
└── test_blocks.py
```

## Validation

Compile-check the project without calling external APIs:

```bash
python -m compileall main.py gui.py paper_ai_reader test_blocks.py test_notion.py
```

Validate example XML files:

```bash
python - <<'PY'
from paper_ai_reader.config import validate_runtime_files
print(validate_runtime_files("cli", "config/settings.example.xml"))
print(validate_runtime_files("gui", "config/settings.example.xml"))
PY
```

An empty list means the XML files are valid.

## Notes

- Runtime XML files can contain secrets and should not be committed.
- `.env` is not used by the current runtime.
- `test_notion.py` and `test_blocks.py` are manual debugging scripts and call the Notion API directly.
- PDF extraction uses `pypdf`; complex PDF layouts may not extract perfectly.
