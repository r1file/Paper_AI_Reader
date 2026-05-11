# Paper AI Reader

Paper AI Reader is a Python automation tool for turning papers saved in a Notion database into structured AI-generated research notes.

It reads pending papers from Notion, extracts text from webpages or PDFs, sends the content to the OpenAI API, and writes a structured Chinese analysis back to the original Notion page.

## Features

- Batch-read paper entries from a Notion database
- Skip papers that have already been processed
- Extract readable text from webpages and PDF URLs
- Generate structured research notes with the OpenAI API
- Write the generated notes back to Notion
- Update each paper's reading status automatically
- Support Notion's newer `data_sources` query flow

## What It Generates

For each paper, the tool generates:

- Paper summary
- Research inspiration for the user's topic
- Relevance rating
- Short rating explanation
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

## Project Structure

```text
.
├── main.py
├── requirements.txt
├── .env.example
├── paper_ai_reader
│   ├── __init__.py
│   ├── analyzer.py
│   ├── config.py
│   ├── fetcher.py
│   └── notion_service.py
├── test_notion.py
└── test_blocks.py
```

## Notion Database Requirements

Your Notion database must contain the following properties:

| Property | Type | Description |
| --- | --- | --- |
| `Title` | Title | Paper title |
| `Website` | URL | Paper webpage or PDF URL |
| `Status` | Select or Status | Reading status |

The tool skips pages whose `Status` is one of:

- `AI Read Done`
- `已完成`
- `Human Reading`

All other statuses are treated as pending papers.

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

Copy the example environment file:

```bash
cp .env.example .env
```

Then fill in the required values:

```bash
NOTION_TOKEN=secret_your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id
OPENAI_API_KEY=sk-your_openai_api_key
```

Optional settings:

```bash
OPENAI_MODEL=gpt-4o-mini
PAPER_TEXT_LIMIT=50000
```

Configuration notes:

- `NOTION_TOKEN`: your Notion integration token
- `NOTION_DATABASE_ID`: your Notion database ID
- `OPENAI_API_KEY`: your OpenAI API key
- `OPENAI_MODEL`: defaults to `gpt-4o-mini`
- `PAPER_TEXT_LIMIT`: maximum number of extracted paper characters sent to OpenAI

## Usage

Run:

```bash
python main.py
```

The pipeline:

1. Query the Notion database
2. Find pending paper pages
3. Update the page status to `AI Reading`
4. Delete existing page blocks
5. Fetch paper text from the webpage or PDF URL
6. Generate structured analysis with OpenAI
7. Write the analysis back to Notion
8. Update the page status to `AI Read Done`

If fetching, analysis, or writing fails, the script prints the error and continues with the next paper.

## Output Format

The Notion page will be rewritten in roughly this format:

```markdown
## 🔍 总结

<AI-generated Chinese summary>

## 💡 对我的研究的启发

<How this paper relates to the research topic>

## ⭐ 与我的研究相关性

★★★★☆
<Short reason>

## 🧪 代码可用性

是 / 否
GitHub：<code URL>

## 🧠 我的笔记

（自己写）
```

## Notes

- `.env` contains secrets and should never be committed.
- The current pipeline deletes existing Notion page blocks before fetching and analyzing the paper. Test on a sample page first.
- `test_notion.py` and `test_blocks.py` are manual debugging scripts and will call the Notion API directly.
- PDF text extraction uses `pypdf`; complex PDF layouts may not be extracted perfectly.

## Development

Check that the Python files compile:

```bash
python -m compileall main.py paper_ai_reader test_blocks.py test_notion.py
```

Dependencies are listed in:

```text
requirements.txt
```

---

# Paper AI Reader 中文说明

Paper AI Reader 是一个用于自动阅读论文的 Python 工具。它会从 Notion 数据库中读取待处理论文，抓取网页或 PDF 内容，调用 OpenAI API 生成中文结构化笔记，并把结果写回对应的 Notion 页面。

这个项目适合用来维护个人论文阅读库，尤其适合需要持续把论文内容和自己研究方向关联起来的场景。

## 功能

- 从 Notion 数据库批量读取论文条目
- 根据 `Status` 自动跳过已完成论文
- 支持抓取网页正文和 PDF 文本
- 使用 OpenAI API 生成中文论文分析
- 将结构化笔记写回 Notion 页面
- 自动更新 Notion 页面阅读状态
- 支持 Notion 新版 `data_sources` 查询方式

## 分析内容

每篇论文会生成以下内容：

- 论文总结
- 对个人研究方向的启发
- 与研究方向的相关性评分
- 评分理由
- 代码是否可用
- GitHub 或代码链接
- 个人补充笔记区域

当前内置研究方向包括：

- LLM
- ROS2
- TurtleBot3
- Human-Robot Interaction
- 情绪感知交互
- 从人的情感输入生成机器人行为或控制指令

## 项目结构

```text
.
├── main.py
├── requirements.txt
├── .env.example
├── paper_ai_reader
│   ├── __init__.py
│   ├── analyzer.py
│   ├── config.py
│   ├── fetcher.py
│   └── notion_service.py
├── test_notion.py
└── test_blocks.py
```

## Notion 数据库要求

Notion 数据库需要包含以下属性：

| 属性名 | 类型 | 说明 |
| --- | --- | --- |
| `Title` | Title | 论文标题 |
| `Website` | URL | 论文网页或 PDF 地址 |
| `Status` | Select 或 Status | 阅读状态 |

程序会跳过以下状态的页面：

- `AI Read Done`
- `已完成`
- `Human Reading`

其他状态的页面会被视为待处理论文。

## 安装

创建并激活虚拟环境：

```bash
python3 -m venv venv
source venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 配置

复制环境变量示例文件：

```bash
cp .env.example .env
```

然后在 `.env` 中填写：

```bash
NOTION_TOKEN=secret_your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id
OPENAI_API_KEY=sk-your_openai_api_key
```

可选配置：

```bash
OPENAI_MODEL=gpt-4o-mini
PAPER_TEXT_LIMIT=50000
```

说明：

- `NOTION_TOKEN` 是 Notion integration token
- `NOTION_DATABASE_ID` 是 Notion 数据库 ID
- `OPENAI_API_KEY` 是 OpenAI API key
- `OPENAI_MODEL` 默认使用 `gpt-4o-mini`
- `PAPER_TEXT_LIMIT` 用于限制发送给 OpenAI 的论文文本长度

## 使用

运行：

```bash
python main.py
```

运行流程：

1. 查询 Notion 数据库
2. 找到待处理论文页面
3. 将页面状态更新为 `AI Reading`
4. 删除页面中已有 blocks
5. 抓取论文网页或 PDF 文本
6. 调用 OpenAI 生成结构化分析
7. 将分析结果写回 Notion 页面
8. 将页面状态更新为 `AI Read Done`

如果抓取、分析或写入过程中失败，程序会打印错误信息并继续处理下一篇论文。

## 输出格式

写回 Notion 的内容大致如下：

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

## 注意事项

- `.env` 中包含密钥，不要提交到 GitHub。
- 当前程序会在抓取和分析前删除页面已有 blocks，建议先在测试页面中确认流程。
- `test_notion.py` 和 `test_blocks.py` 是手动调试脚本，会直接访问 Notion API。
- PDF 文本提取依赖 `pypdf`，复杂版式论文可能存在提取不完整的情况。

## 开发

检查 Python 文件是否能正常编译：

```bash
python -m compileall main.py paper_ai_reader test_blocks.py test_notion.py
```

依赖列表见：

```text
requirements.txt
```
