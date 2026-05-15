# TODO: replace_in_file_tool.py の .po 対応改善

## 目的
`src/uagent/tools/replace_in_file_tool.py` の `.po` 取り扱いを改善し、従来の `.po` ファイルを壊さずに複数件・複数行をまとめて更新できるようにする。

## 予定作業
- [ ] 既存の `replace_po_entry` の仕様を確認する
- [ ] `.po` entry を単位として扱うロジックを整理する
- [ ] `msgid` / `msgstr` の複数行を安全に保持・再構成できるようにする
- [ ] 複数件を一度に処理できる新しいアクションを追加する
  - 例: `replace_po_entries`
- [ ] 従来の `.po` にあるコメントや空行をできるだけ保持する
- [ ] 必要なら `msgctxt` / `msgid_plural` / `msgstr[n]` の扱いを追加する
- [ ] 単体テストを追加する
  - [ ] 単一行 `msgstr`
  - [ ] 複数行 `msgstr`
  - [ ] 複数 entry の一括更新
  - [ ] 未一致時の診断
- [ ] 既存テストが壊れていないか確認する

## メモ
- 単純な `msgid` / `msgstr` 形式は維持する
- まずは安全性を優先し、必要最小限の拡張から始める
- 実装後は `.po` を再抽出・再ビルドする流れも検討する
