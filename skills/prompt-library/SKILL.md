---
name: prompt-library
version: 1.0.0
description: |
  uag 同梱の「プロンプトテンプレート集」を Agent Skills 形式で提供するスキル。

  - 本スキルはツール実行スキルではなく、テンプレ文章（Markdown）を参照するための“ライブラリ”です。
  - 旧 src/uagent/prompts 配下のテンプレートを移設しています。

inputs:
  - name: template_id
    description: |
      参照したいテンプレートID。
      一覧は references/index.yaml を参照。
    required: false

outputs:
  - name: template_markdown
    description: |
      テンプレ本文（Markdown）。
      {{placeholder}} が含まれる場合、手動で埋めてから利用してください。
    required: false
---

# Prompt Library

## 目的

`skills/prompt-library/references/` にあるテンプレートを参照し、要件定義・設計・実装・レビュー等の作業を進めるための叩き台にします。

## 使い方（推奨）

1. テンプレ一覧（カタログ）を読む
   - `skills/prompt-library/references/index.yaml`

2. テンプレ本文を読む
   - `skills/prompt-library/references/templates/<template>.md`

3. `{{placeholder}}` をあなたの状況に合わせて埋めて使う
   - このスキル自体は placeholder 埋め（context適用）を自動では行いません。

## テンプレ一覧

テンプレIDと対応ファイルは `references/index.yaml` を正とします。

## 備考

- 旧 `prompt_get` ツールで行っていた「テンプレ検索・context埋め込み」は、本スキル（Agent Skills）には含めていません。
- 必要なら、テンプレ本文をベースに新しい Agent Skill（実行手順・成果物定義を含む）へ再整理することを推奨します。
