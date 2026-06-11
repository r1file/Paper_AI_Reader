# Paper AI Reader 中文文档

**语言:** [English](README.md) | [中文](README.zh.md) | [日本語](README.ja.md)

Paper AI Reader 是一个 Python 工具，用来把 Notion 数据库里保存的论文转换成结构化 AI 阅读笔记。

它会从 Notion 读取待处理论文，抓取网页或 PDF 正文，调用 OpenAI 兼容 AI provider 分析论文，识别真实论文标题，写入研究关键词，并把结构化笔记写回原 Notion 页面。

## 主要特点

- 支持 CLI 流水线和 PySide6 桌面 GUI
- UI 支持中文、日文、英文
- 论文阅读输出支持中文、日文、英文
- 运行配置完全使用 XML
- 通过 `base_url` 支持 OpenAI 兼容 provider
- 支持 Notion 新版 `data_sources` 查询
- 支持网页和 PDF 文本抽取
- 网页抓取失败时可回退使用 Notion 页面已有正文
- 自动识别真实论文标题并更新 Notion `Title`
- 提取关键词并写入 Notion `Keywords`
- 只有在抓取和 AI 分析成功后才删除旧页面 blocks

## GUI

启动桌面 GUI：

```bash
python gui.py
```

GUI 包含三个页面：

- `Dashboard`：启动或停止阅读流水线，查看日志和模型请求/回复。
- `Prompt`：选择笔记输出语言，并预览 prompt XML。
- `Setting`：配置 Notion、AI provider、模型、base URL 和文本长度限制。

当连通性检查、模型刷新或阅读流水线正在运行时，GUI 会暂时锁定 Prompt、Setting 和语言设置，避免运行过程中配置漂移。Setting 页面也会在丢弃未保存修改前提示确认。

## CLI

运行 CLI：

```bash
python main.py
```

CLI 会先检查 Notion 和 AI provider 连通性，然后再启动处理流程。

## Notion 数据库

Notion 数据库建议包含：

| 属性 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `Title` | Title | 是 | 页面标题，程序可用真实论文标题重写。 |
| `Website` | URL | 是 | 论文网页或 PDF 地址。 |
| `Status` | Status 或 Select | 是 | 阅读流程状态。 |
| `Keywords` | Multi-select、Select 或 Rich text | 建议 | AI 提取的关键词。 |

会被处理的状态：

- `TBD`
- `AI Reading`

会被跳过的状态：

- `AI Read Done`
- `Human Reading`
- `DONE`

程序自己只写入：

- `AI Reading`
- `AI Read Done`

## 安装

创建虚拟环境：

```bash
python3 -m venv venv
source venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 配置

配置使用 XML。CLI 和 GUI 共用同一个 settings 文件。先复制示例：

```bash
cp config/settings.example.xml config/settings.xml
```

然后编辑 `config/settings.xml`。

重要字段：

- `notion_token`
- `notion_database_id`
- `ai_api_key`
- `ai_model`
- `ai_base_url`
- `paper_text_limit`
- `ui_language`
- `theme_mode`
- `prompt_language`

使用 OpenAI 默认 API 时，`ai_base_url` 留空。使用兼容 provider 时，填写对应 `/v1` base URL。

Prompt XML 文件位置：

- `prompts/zh.xml`
- `prompts/ja.xml`
- `prompts/en.xml`

每个 prompt XML 都包含 `system_prompt` 和 `user_prompt_template`。模板支持 `{title}`、`{website}`、`{paper_text}`。
默认 `system_prompt` 包含示例研究方向（如 LLM、ROS2、HRI）。请根据自己的研究领域直接编辑对应语言的 prompt XML。

## 处理流程

1. 查询 Notion 数据库。
2. 选择 `Status` 为 `TBD` 或 `AI Reading` 的页面。
3. 将页面标记为 `AI Reading`。
4. 从 `Website` 抓取论文文本。
5. 抓取失败时尝试使用 Notion 页面已有正文。
6. 使用配置的 AI provider 分析论文。
7. 解析模型返回的结构化 JSON。
8. 使用 `paper_title` 更新 Notion 页面标题。
9. 如果存在 `Keywords` 属性，则写入关键词。
10. 删除旧页面 blocks。
11. 写入结构化笔记。
12. 将页面标记为 `AI Read Done`。

## 生成 JSON

模型回复会被标准化为：

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

## 项目结构

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
│       ├── style.qss
│       └── i18n.py
├── tests
│   ├── test_analyzer.py
│   ├── test_config.py
│   ├── test_connectivity.py
│   ├── test_fetcher.py
│   └── test_notion_service.py
├── test_notion.py
└── test_blocks.py
```

## 本地验证

不访问外部 API 的编译检查：

```bash
python -m compileall main.py gui.py paper_ai_reader test_blocks.py test_notion.py
```

运行自动化测试：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

验证示例 XML：

```bash
python - <<'PY'
from paper_ai_reader.config import validate_runtime_files
print(validate_runtime_files("cli", "config/settings.example.xml"))
print(validate_runtime_files("gui", "config/settings.example.xml"))
PY
```

返回空列表表示 XML 有效。

## Release 打包

构建当前平台应用和源码 zip：

```bash
python scripts/build_release.py --version v0.1.0
```

产物会写入 `release/`。Python 桌面应用需要在目标平台打包，因此要生成
macOS、Linux、Windows 三端应用，可以运行 `.github/workflows/release.yml`
中的手动 GitHub Actions 工作流，或分别在三种系统上执行该脚本。
当 GitHub Release 发布时，该 workflow 也会自动运行，并把生成的 zip 文件上传到
对应 release。

打包后的桌面应用会在首次启动时把 `settings.example.xml` 和 prompt XML 复制到用户
配置目录。源码运行时仍使用仓库内的 `config/settings.xml` 和 `prompts/*.xml`。

## 注意事项

- 运行用 XML 可能包含密钥，不要提交。
- 当前运行逻辑不读取 `.env`。
- `test_notion.py` 和 `test_blocks.py` 是手动调试脚本，会直接调用 Notion API。
- PDF 文本抽取使用 `pypdf`，复杂多栏论文、公式、图表标题可能抽取不完整；遇到质量问题时建议提供可读网页、手动整理正文，或接入更专业的学术 PDF/OCR 工具。
