./src/uagent/tools/TOOL_I18N_GUIDE.mdを参照

# ルール

TOOL_SPEC定義が存在する /src/uagent/tools/*.pyと
en.tool.descriptionが存在する
/src/uagent/tools/*.json
を修正する

# pythonに対する修正

- pythonのメッセージは全て英語がルール
- x_search_termがある場合、そのツールに関する(名詞、動詞、形容詞）単語のみにする
- x_search_termがない場合、そのツールに関する(名詞、動詞、形容詞）単語のみを追加
- 必要であれば\_\_init\_\_.pyで x_search_term の扱いを調べて
- 10個以上はできるだけ追加する
- 同じ単語がかぶらないように
- x_search_termsが完成したらI18N対応を外したx_search_terms_enを追加する
- 完成後、ruff/blackで修正する

# pythonの後、jsonに対する修正

- まず、enのx_search_termsをpythonに合わせる
- 30言語のx_search_termsを翻訳する
- もし単語に違和感があれば修正する
