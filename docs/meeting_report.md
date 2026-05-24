# Paper AI Reader Meeting Report

## English

### Project Overview

Paper AI Reader is a small research workflow tool that converts papers saved in Notion into structured AI-generated reading notes.

The goal is not to build a full paper management platform. Instead, it connects an existing Notion paper collection workflow with AI-assisted initial paper screening.

### Motivation

The project was created for two reasons:

- Screening ROS2 and HRI-related papers takes time, especially before deciding which papers deserve close reading.
- It is also an experiment in AI-assisted coding, where an AI agent helps implement features while the human developer controls requirements, architecture, validation, and trust boundaries.

### System Design

The system uses a Notion database as the paper source. Papers are added manually or through Notion Web Clipper, so the user still controls which papers enter the pipeline.

The backend is written in Python and can run from the CLI. The desktop GUI is built with PySide6 and is designed for macOS, Windows, and Linux. UI and reading output languages support Chinese, Japanese, and English.

The AI provider is not fixed to one service. The project uses the OpenAI SDK and supports OpenAI-compatible providers through `base_url`.

### Workflow

1. Configure Notion token, database ID, AI API key, model, and prompt XML.
2. Start the CLI or GUI.
3. The app validates XML files and checks Notion and AI connectivity.
4. The pipeline processes pages whose `Status` is `TBD` or `AI Reading`.
5. Paper text is fetched from a webpage or PDF URL.
6. If fetching fails, existing Notion page text is used as fallback.
7. The AI model returns structured JSON.
8. The app updates the Notion title, writes keywords, replaces old blocks with notes, and marks the page as `AI Read Done`.

### Value and Future Work

The main value is faster paper screening and consistent note formatting inside an existing Notion workflow.

Future improvements may include better PDF/web extraction, more modular prompts for different research themes, and clearer batch-processing error reports.

## 中文

### 项目简介

Paper AI Reader 是一个小型研究工作流工具，用来把 Notion 中保存的论文转换成结构化 AI 阅读笔记。

它的目标不是做一个完整论文管理平台，而是把已有的 Notion 论文收集流程和 AI 初筛能力连接起来。

### 开发动机

这个项目主要有两个动机：

- ROS2 和 HRI 相关论文初筛成本较高，需要快速判断论文内容、相关性、代码可用性和精读价值。
- 实践 AI-assisted coding：AI agent 辅助实现功能，但人仍然控制需求、架构、验证和可信边界。

### 系统设计

系统使用 Notion database 作为论文数据源。论文可以通过 Notion Web Clipper 或手动方式加入，因此用户仍然控制进入流水线的论文范围。

后端使用 Python 编写，可以从 CLI 运行。桌面 GUI 使用 PySide6 构建，目标支持 macOS、Windows、Linux。UI 和阅读输出都支持中文、日文、英文。

AI 服务不绑定单一 provider。项目使用 OpenAI SDK，并通过 `base_url` 支持 OpenAI 兼容 provider。

### 运行流程

1. 配置 Notion token、database ID、AI API key、模型和 prompt XML。
2. 启动 CLI 或 GUI。
3. 程序校验 XML 文件，并检查 Notion 和 AI 连通性。
4. 流水线处理 `Status` 为 `TBD` 或 `AI Reading` 的页面。
5. 从网页或 PDF URL 抓取论文文本。
6. 抓取失败时，回退使用 Notion 页面已有正文。
7. AI 模型返回结构化 JSON。
8. 程序更新 Notion 标题、写入关键词、替换旧 blocks，并将页面标记为 `AI Read Done`。

### 价值与后续改进

这个工具的核心价值是提高论文初筛速度，并在已有 Notion 工作流中统一笔记格式。

后续可以改进 PDF/网页正文抽取、面向不同研究主题的模块化 prompt，以及批处理时的错误报告。

## 日本語

### プロジェクト概要

Paper AI Reader は、Notion に保存した論文を構造化された AI 読書ノートへ変換する小さな研究ワークフローツールです。

目的は大規模な論文管理システムを作ることではなく、既存の Notion 論文管理フローと AI による初期スクリーニングを接続することです。

### 開発動機

主な動機は二つあります：

- ROS2 と HRI 関連論文の初期調査には時間がかかるため、内容、研究との関連性、コード公開状況、精読価値を早く判断したい。
- AI-assisted coding を実践し、AI agent に実装を支援させつつ、人間が要件、設計、検証、信頼境界を管理する方法を試したい。

### システム設計

システムは Notion database を論文データソースとして使います。論文は Notion Web Clipper または手動入力で追加するため、ユーザーが処理対象を制御できます。

バックエンドは Python で実装され、CLI から実行できます。デスクトップ GUI は PySide6 で構築され、macOS、Windows、Linux を想定しています。UI と読書ノート出力は中国語、日本語、英語に対応しています。

AI provider は一つに固定していません。OpenAI SDK を使い、`base_url` によって OpenAI 互換 provider に対応しています。

### 処理フロー

1. Notion token、database ID、AI API key、モデル、prompt XML を設定します。
2. CLI または GUI を起動します。
3. アプリは XML ファイルを検証し、Notion と AI provider の接続を確認します。
4. `Status` が `TBD` または `AI Reading` のページを処理します。
5. Web ページまたは PDF URL から論文本文を取得します。
6. 取得に失敗した場合、既存の Notion ページ本文を fallback として使用します。
7. AI モデルが構造化 JSON を返します。
8. アプリは Notion タイトルを更新し、キーワードを書き込み、古い blocks をノートで置き換え、ページを `AI Read Done` に更新します。

### 価値と今後の改善

このツールの価値は、論文の初期スクリーニングを速くし、既存の Notion ワークフロー内でノート形式を統一できることです。

今後は、PDF/Web 本文抽出の改善、研究テーマごとの modular prompt、バッチ処理時のエラーレポート改善が考えられます。
