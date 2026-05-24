# Paper AI Reader 日本語ドキュメント

**Language:** [English](README.md) | [中文](README.zh.md) | [日本語](README.ja.md)

Paper AI Reader は、Notion データベースに保存した論文を、AI による構造化された研究ノートへ変換する Python ツールです。

Notion から処理対象の論文を読み込み、Web ページまたは PDF から本文を抽出し、OpenAI 互換の AI provider で分析します。その後、正式な論文タイトル、研究キーワード、構造化ノートを Notion ページへ書き戻します。

## 主な特徴

- CLI パイプラインと PySide6 デスクトップ GUI
- UI は中国語、日本語、英語に対応
- 読書ノートの出力も中国語、日本語、英語に対応
- 実行設定は XML のみ
- `base_url` による OpenAI 互換 provider 対応
- Notion の新しい `data_sources` クエリに対応
- Web ページと PDF の本文抽出
- Web 取得に失敗した場合、既存の Notion ページ本文を fallback として利用
- 正式な論文タイトルを識別し、Notion の `Title` を更新
- キーワードを抽出し、Notion の `Keywords` に書き込み
- 既存ページ blocks は、本文取得と AI 分析が成功した後でのみ削除

## GUI

デスクトップ GUI を起動します：

```bash
python gui.py
```

GUI には三つのページがあります：

- `Dashboard`：読書パイプラインの開始・停止、ログ、モデルへの入力と応答の確認。
- `Prompt`：ノート出力言語の選択と prompt XML のプレビュー。
- `Setting`：Notion、AI provider、モデル、base URL、本文長上限の設定。

接続確認、モデル更新、読書パイプラインが実行中の場合、GUI は Prompt、Setting、言語設定を一時的にロックし、実行中の設定変更を防ぎます。Setting ページでは、未保存の変更を破棄する前に確認ダイアログを表示します。

## CLI

CLI パイプラインを実行します：

```bash
python main.py
```

CLI は Notion と AI provider の接続確認を行ってから処理を開始します。

## Notion データベース

Notion データベースには次のプロパティを用意してください：

| Property | Type | Required | Description |
| --- | --- | --- | --- |
| `Title` | Title | Yes | ページタイトル。正式な論文タイトルで更新できます。 |
| `Website` | URL | Yes | 論文ページまたは PDF の URL。 |
| `Status` | Status または Select | Yes | 処理状態。 |
| `Keywords` | Multi-select、Select、Rich text | Recommended | AI が抽出したキーワード。 |

処理対象の status：

- `TBD`
- `AI Reading`

スキップされる status：

- `AI Read Done`
- `Human Reading`
- `DONE`

アプリが書き込む status は次の二つだけです：

- `AI Reading`
- `AI Read Done`

## インストール

仮想環境を作成します：

```bash
python3 -m venv venv
source venv/bin/activate
```

依存関係をインストールします：

```bash
pip install -r requirements.txt
```

## 設定

設定は XML ベースです。CLI と GUI は同じ settings ファイルを使います。まず example をコピーします：

```bash
cp config/settings.example.xml config/settings.xml
```

次に `config/settings.xml` を編集します。

重要な設定項目：

- `notion_token`
- `notion_database_id`
- `ai_api_key`
- `ai_model`
- `ai_base_url`
- `paper_text_limit`
- `ui_language`
- `theme_mode`
- `prompt_language`

OpenAI の既定 API を使う場合、`ai_base_url` は空欄にします。互換 provider を使う場合は、その provider の `/v1` base URL を設定します。

Prompt XML ファイル：

- `prompts/zh.xml`
- `prompts/ja.xml`
- `prompts/en.xml`

各 prompt XML には `system_prompt` と `user_prompt_template` が含まれます。テンプレートでは `{title}`、`{website}`、`{paper_text}` を使用できます。

## 処理フロー

1. Notion データベースを照会します。
2. `Status` が `TBD` または `AI Reading` のページを選択します。
3. ページを `AI Reading` に更新します。
4. `Website` から論文本文を取得します。
5. 取得に失敗した場合、既存の Notion ページ本文を試します。
6. 設定された AI provider で論文を分析します。
7. モデル応答の構造化 JSON を解析します。
8. `paper_title` で Notion ページタイトルを更新します。
9. `Keywords` プロパティがあればキーワードを書き込みます。
10. 既存ページ blocks を削除します。
11. 構造化ノートを書き込みます。
12. ページを `AI Read Done` に更新します。

## 生成 JSON

モデル応答は次の形式に正規化されます：

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

## プロジェクト構成

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

## ローカル検証

外部 API を呼ばずにコンパイル確認を行います：

```bash
python -m compileall main.py gui.py paper_ai_reader test_blocks.py test_notion.py
```

example XML を検証します：

```bash
python - <<'PY'
from paper_ai_reader.config import validate_runtime_files
print(validate_runtime_files("cli", "config/settings.example.xml"))
print(validate_runtime_files("gui", "config/settings.example.xml"))
PY
```

空リストが返れば XML は有効です。

## 注意

- 実行用 XML には secret が含まれるため、コミットしないでください。
- 現在の実行ロジックは `.env` を読みません。
- `test_notion.py` と `test_blocks.py` は手動デバッグ用で、Notion API を直接呼び出します。
- PDF 抽出には `pypdf` を使用しています。複雑なレイアウトでは完全に抽出できない場合があります。

## Release ビルド

現在のプラットフォーム用アプリと source zip を作成します：

```bash
python scripts/build_release.py --version v0.1.0
```

成果物は `release/` に出力されます。Python デスクトップアプリは対象 OS 上で
ビルドする必要があるため、macOS、Linux、Windows 用を作成するには
`.github/workflows/release.yml` の手動 GitHub Actions workflow を実行するか、
各 OS でこのスクリプトを実行してください。GitHub Release が published になった
場合も workflow が実行され、生成された zip が release asset としてアップロード
されます。

パッケージ化されたデスクトップアプリは、初回起動時に `settings.example.xml` と
prompt XML をユーザー設定ディレクトリへコピーします。source 実行ではリポジトリ内の
`config/settings.xml` と `prompts/*.xml` を使います。
