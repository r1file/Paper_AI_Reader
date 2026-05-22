# Paper AI Reader

Paper AI Reader is a Python automation tool for turning papers saved in a Notion database into structured AI-generated research notes.

It reads papers from Notion, extracts text from webpages or PDFs, asks the configured AI API to analyze the paper in the selected output language, rewrites incorrect Notion page titles with the real paper title, and writes structured notes back to the original Notion page.

## Desktop GUI

Paper AI Reader includes a modern cross-platform desktop GUI built with PySide6. It works on macOS, Linux, and Windows.

Start the GUI:

```bash
python gui.py
```

The GUI has three main pages:

- `Dashboard`: start/stop the paper-reading pipeline, view current operation, runtime logs, and the AI conversation/status stream.
- `Prompt`: choose the reading output language and edit the paper-reading prompt.
- `Setting`: edit Notion API settings, compatible AI provider settings, model name, and paper text limit.

The UI supports:

- Chinese
- Japanese
- English

The Dashboard conversation panel shows the system prompt, user request, model JSON response, and runtime status. It does not display hidden model reasoning chains.

The Setting page includes manual connectivity checks for Notion and the configured AI provider. Results are shown beside the buttons with natural-language messages such as `Notion API 正常`, `无效的 Notion Token`, or `无效服务商链接或网络不可达`. If a connectivity problem is detected, the Dashboard status dot turns red and detailed diagnostics are written to the Dashboard log.

The AI Model field on the Setting page is an editable dropdown. On startup, the GUI asks the configured provider for available models and selects a provider-appropriate default. If `ai_model` is set in the XML config, that explicit value has priority. You can also click `刷新模型` / `Refresh Models` after changing the API key or Base URL.

Some compatible providers, including certain DeepSeek API modes, may not support OpenAI Responses API or structured `response_format`. Paper AI Reader automatically falls back from Responses API to Chat Completions JSON schema, JSON object, and finally plain Chat Completions with strict JSON parsing.

The CLI and GUI both call the shared `paper_ai_reader.backend.PaperAIReaderBackend` facade, keeping UI concerns separate from Notion, AI-provider, connectivity, and paper-processing logic.

The Prompt and Setting pages can open these files in your default external editor, such as Notepad, VS Code, or another OS-associated editor:

- `config/gui_config.xml`
- `prompts/<language>.xml`

For compatible AI API providers, set:

- `AI API Key`
- `AI Model`
- `Compatible API Base URL`

Leave `Compatible API Base URL` empty to use OpenAI's default API endpoint. For OpenAI-compatible providers, use their `/v1` base URL.

## Features

- Batch-read paper entries from a Notion database
- Process only papers whose `Status` is `TBD` or `AI Reading`
- Skip papers marked `AI Read Done`, `Human Reading`, or `DONE`
- Extract readable text from webpages and PDF URLs
- Identify the real paper title from the fetched paper content
- Rewrite the Notion page `Title` with the real paper title
- Generate structured research notes with the configured AI API
- Delete existing Notion page blocks only after AI analysis succeeds
- Write generated notes back to Notion
- Update each paper's reading status automatically
- GUI Dashboard, Prompt, and Setting pages
- UI localization for Chinese, Japanese, and English
- Prompt presets for Chinese, Japanese, and English reading outputs
- Compatible AI provider configuration through `base_url`
- Support Notion's newer `data_sources` query flow

## Notion Database Requirements

Your Notion database must contain these exact properties:

| Property | Type | Description |
| --- | --- | --- |
| `Title` | Title | Notion page title. The script can rewrite it with the real paper title. |
| `Website` | URL | Paper webpage or PDF URL. |
| `Status` | Status | Reading workflow status. |

The `Status` property should use these English status options:

| Status | Meaning | Script Behavior |
| --- | --- | --- |
| `TBD` | Nothing has been done yet. | The script processes this page. |
| `AI Reading` | The script is currently processing, or a previous run stopped midway. | The script can process/resume this page. |
| `AI Read Done` | AI reading is complete. | The script skips this page. |
| `Human Reading` | Reserved for manual reading. | The script skips this page. |
| `DONE` | Manually completed. | The script skips this page. |

The script only writes these status values itself:

- `AI Reading`
- `AI Read Done`

It does not create or write any Chinese status labels.

## Pipeline

Running `python main.py` does the following:

1. Query the Notion database.
2. Find pages whose `Status` is `TBD` or `AI Reading`.
3. Skip pages whose `Status` is `AI Read Done`, `Human Reading`, or `DONE`.
4. Read the page ID, current `Title`, and `Website`.
5. Update `Status` to `AI Reading`.
6. Fetch paper text from `Website`.
7. Analyze the paper with the OpenAI API.
8. Extract the real paper title from the paper content.
9. Rewrite the Notion page `Title` with the real paper title.
10. Delete all existing page blocks, including Notion Clipper content.
11. Write structured AI-generated notes back to the Notion page.
12. Update `Status` to `AI Read Done`.

If fetching, analysis, deleting, writing, or status update fails, the script prints the error and continues with the next paper. Existing page blocks are not deleted until after AI analysis succeeds.

## Generated Notes

For each paper, the tool generates:

- Paper summary in the selected output language
- Research inspiration in the selected output language
- Relevance rating from 1 to 5 stars
- Rating explanation in the selected output language
- Code availability
- GitHub or code URL if found
- A personal notes section

The built-in research focus is:

- LLM
- ROS2
- TurtleBot3
- Human-Robot Interaction
- Emotion-aware interaction
- Generating robot behavior or control commands from human emotional input

## Output Format

The Notion page content is rewritten in this format:

```markdown
## 🔍 总结

<AI 生成的中文论文总结>

## 💡 对我的研究的启发

<论文与个人研究方向的联系>

## ⭐ 与我的研究相关性

★★★★☆
<评分理由>

## 🧪 代码可用性

是 / 否
GitHub：<代码链接>

## 🧠 我的笔记

（自己写）
```

The OpenAI response is requested as structured JSON with this shape:

```json
{
  "paper_title": "Real paper title from the paper content",
  "summary": "...",
  "idea": "...",
  "rating": 1,
  "reason": "...",
  "code_available": true,
  "code_url": ""
}
```

## Project Structure

```text
.
├── main.py
├── requirements.txt
├── config
│   ├── cli_config.example.xml
│   └── gui_config.example.xml
├── prompts
│   └── default
│       ├── zh.xml
│       ├── ja.xml
│       └── en.xml
├── paper_ai_reader
│   ├── __init__.py
│   ├── analyzer.py
│   ├── backend.py
│   ├── config.py
│   ├── connectivity.py
│   ├── fetcher.py
│   ├── gui
│   │   ├── app.py
│   │   └── i18n.py
│   ├── notion_service.py
│   ├── pipeline.py
│   └── prompts.py
├── test_notion.py
└── test_blocks.py
```

## Installation

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Configuration is XML-only. The CLI and GUI use separate XML files:

- CLI: `config/cli_config.xml`
- GUI: `config/gui_config.xml`

Create them from the examples:

```bash
cp config/cli_config.example.xml config/cli_config.xml
cp config/gui_config.example.xml config/gui_config.xml
```

Then edit the XML values for Notion, AI provider, model, text limit, UI language, theme, and prompt language. The application does not read `.env`; XML files are the only runtime configuration source. In GUI config, leave `ai_model` empty to let the app select a default from the provider's model list at startup.

Prompt files are also XML-based and contain both the system prompt and the user prompt template. CLI and GUI use the same canonical files:

- `prompts/zh.xml`
- `prompts/ja.xml`
- `prompts/en.xml`

When you switch the prompt output language, the app reads the matching XML file directly. The `user_prompt_template` supports `{title}`, `{website}`, and `{paper_text}` placeholders.

## Usage

Run:

```bash
python main.py
```

Or start the GUI:

```bash
python gui.py
```

For local validation without calling Notion or OpenAI:

```bash
python -m compileall main.py paper_ai_reader test_blocks.py test_notion.py
```

## Notes

- XML config files under `config/cli_config.xml` and `config/gui_config.xml` contain secrets and should never be committed.
- Prompt XML files are canonical under `prompts/` and should contain both `system_prompt` and `user_prompt_template`.
- Notion page blocks are deleted only after paper text has been fetched and AI analysis has succeeded.
- `test_notion.py` and `test_blocks.py` are manual debugging scripts and call the Notion API directly.
- PDF text extraction uses `pypdf`; complex PDF layouts may not be extracted perfectly.

---

# Paper AI Reader 中文说明

Paper AI Reader 是一个用于自动阅读论文的 Python 工具。它会从 Notion 数据库中读取待处理论文，抓取网页或 PDF 内容，调用配置的 AI API 生成所选语言的结构化笔记，识别论文真实标题，并把标题和笔记写回对应的 Notion 页面。

## 桌面 GUI

项目现在包含一个基于 PySide6 的现代桌面 GUI，可在 macOS、Linux、Windows 上运行。

启动 GUI：

```bash
python gui.py
```

GUI 主要分为三个页面：

- `Dashboard`：启动/停止论文阅读流程，显示当前操作、运行日志、AI 对话和状态流。
- `Prompt`：选择阅读输出语言、预览 Prompt，并通过外部编辑器修改 XML。
- `Setting`：编辑 Notion API、兼容 AI provider 的 API、模型名和论文文本长度。

UI 支持三种语言：

- 中文
- 日本語
- English

Prompt 提供三套唯一 XML 语言文件：

- 中文输出
- 日本語输出
- English output

配置仅使用 XML：CLI 使用 `config/cli_config.xml`，GUI 使用 `config/gui_config.xml`，程序不会读取 `.env`。Prompt 也按 XML 文件读取，并且 CLI/GUI 共用唯一来源：`prompts/zh.xml`、`prompts/ja.xml`、`prompts/en.xml`。每个 Prompt XML 都必须包含 `system_prompt` 和 `user_prompt_template`；切换 Prompt 输出语言时会直接读取对应语言的 XML。`user_prompt_template` 支持 `{title}`、`{website}`、`{paper_text}` 占位符。

`Dashboard` 中的 AI 对话区域会显示系统 prompt、用户请求、模型 JSON 回复和运行状态。它不会显示模型隐藏推理链。

`Setting` 页面提供 Notion 和 AI 服务商的手动连通性测试。测试结果会显示在按钮旁边，例如 `Notion API 正常`、`无效的 Notion Token`、`无效服务商链接或网络不可达`。如果检测到基础连通性问题，Dashboard 状态灯会变成红色，并把详细诊断写入 Dashboard 日志。

`Setting` 页面中的 `AI Model` 是可编辑下拉框。GUI 启动时会自动问询当前服务商的模型列表并选择一个合适默认模型；如果 XML 中已经显式填写了 `ai_model`，则优先使用 XML 中的模型。修改 API Key 或 Base URL 后，也可以点击 `刷新模型` 手动重新读取。

部分兼容服务商（例如某些 DeepSeek API 模式）可能不支持 OpenAI Responses API 或结构化 `response_format`。程序会自动按顺序降级到 Chat Completions JSON schema、JSON object，最后使用普通 Chat Completions 并进行严格 JSON 解析。

`Prompt` 和 `Setting` 页面支持用系统默认第三方编辑器打开：

- `config/gui_config.xml`
- `prompts/<language>.xml`

如果要使用 OpenAI 兼容 API provider，在 Setting 页面中填写：

- `AI API Key`
- `AI Model`
- `Compatible API Base URL`

如果使用 OpenAI 默认 API，`Compatible API Base URL` 留空即可。兼容 provider 通常填写它们的 `/v1` base URL。

## 功能

- 从 Notion 数据库批量读取论文条目
- 只处理 `Status` 为 `TBD` 或 `AI Reading` 的页面
- 跳过 `AI Read Done`、`Human Reading`、`DONE`
- 支持抓取网页正文和 PDF 文本
- 从论文正文中识别真实论文标题
- 自动重写 Notion 页面 `Title`
- 使用配置的 AI API 生成论文分析
- AI 分析成功后才删除页面已有 blocks
- 将结构化笔记写回 Notion 页面
- 自动更新 Notion 页面阅读状态
- 提供 Dashboard / Prompt / Setting 三页桌面 GUI
- 支持中文、日文、英文 UI
- 提供中文、日文、英文三套内置阅读 Prompt
- 支持通过 `base_url` 配置 OpenAI 兼容 AI provider
- 支持 Notion 新版 `data_sources` 查询方式

## Notion 数据库要求

Notion 数据库需要包含以下属性：

| 属性名 | 类型 | 说明 |
| --- | --- | --- |
| `Title` | Title | 页面标题，程序会用识别出的真实论文标题重写它。 |
| `Website` | URL | 论文网页或 PDF 地址。 |
| `Status` | Status | 阅读流程状态。 |

`Status` 字段应使用以下英文选项：

| Status | 含义 | 程序行为 |
| --- | --- | --- |
| `TBD` | 尚未处理。 | 程序会处理。 |
| `AI Reading` | AI 正在处理，或上一次运行中断。 | 程序会处理/续跑。 |
| `AI Read Done` | AI 阅读完成。 | 程序会跳过。 |
| `Human Reading` | 人工阅读中。 | 程序会跳过。 |
| `DONE` | 手动完成。 | 程序会跳过。 |

程序自己只会写入这些状态：

- `AI Reading`
- `AI Read Done`

程序不会创建或写入中文状态标签。

## 运行流程

运行：

```bash
python main.py
```

流程：

1. 查询 Notion 数据库。
2. 找到 `Status` 为 `TBD` 或 `AI Reading` 的论文页面。
3. 读取页面 ID、当前 `Title` 和 `Website`。
4. 将 `Status` 更新为 `AI Reading`。
5. 抓取论文网页或 PDF 文本。
6. 调用 OpenAI 生成结构化分析。
7. 从论文正文中提取真实论文标题。
8. 用真实论文标题重写 Notion 页面 `Title`。
9. 删除页面中已有 blocks，包括 Notion Clipper 导入内容。
10. 将分析结果写回 Notion 页面。
11. 将 `Status` 更新为 `AI Read Done`。

如果抓取、分析、删除、写入或状态更新失败，程序会打印错误并继续下一篇。页面内容只会在 AI 分析成功后被删除。

## 输出格式

写回 Notion 的内容如下：

```markdown
## 🔍 总结

<AI 生成的中文论文总结>

## 💡 对我的研究的启发

<论文与个人研究方向的联系>

## ⭐ 与我的研究相关性

★★★★☆
<评分理由>

## 🧪 代码可用性

是 / 否
GitHub：<代码链接>

## 🧠 我的笔记

（自己写）
```
