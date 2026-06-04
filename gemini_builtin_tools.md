# Gemini / Vertex AI 組み込みツール（Built-in Tools）仕様まとめ

Gemini API および Vertex AI で利用可能な代表的な組み込みツール（Google検索グラウンディング、コード実行）の仕様と、Python SDK での指定方法を以下にまとめます。

---

## 1. Google Search Grounding（Google検索グラウンディング）
最新のGoogle検索結果をモデルの回答に統合し、情報の正確性を高める機能です。回答には参照元のソースリンク（グラウンディングメタデータ）が含まれます。

### Gemini Developer API (`google-genai` SDK) での指定方法
`google-genai` SDKでは、`GenerateContentConfig` の `tools` パラメータに `{"google_search": {}}` を指定することで有効化できます。

```python
from google import genai
from google.genai import types

client = genai.Client()
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='今日の奈良県大和郡山市の天気は？',
    config=types.GenerateContentConfig(
        tools=[{"google_search": {}}] # 組み込みのGoogle検索を有効化
    )
)
```

### Vertex AI（エンタープライズ版）での指定方法
Vertex AI APIを使用する場合、グラウンディング機能は「Vertex AI Search」のデータストアや、Google検索をソースとする「Google Search Retrieval」として提供されます。

```python
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, Tool

# Google検索グラウンディングツールの定義
google_search_tool = Tool.from_google_search_retrieval(
    google_search_retrieval=aiplatform.gapic.GoogleSearchRetrieval()
)

model = GenerativeModel("gemini-1.5-pro")
response = model.generate_content(
    "今日の奈良県大和郡山市の天気は？",
    tools=[google_search_tool]
)
```

---

## 2. Code Execution（コード実行環境）
モデルがPythonコードを生成し、それを安全なサンドボックス環境で自動実行して計算やデータ処理を行う機能です。複雑な数学の問題やデータ解析に威力を発揮します。

### SDKでの指定方法
`tools=[{"code_execution": {}}]` を指定することで有効化できます。

```python
from google import genai
from google.genai import types

client = genai.Client()
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='1から100までの素数を求めてください。',
    config=types.GenerateContentConfig(
        tools=[{"code_execution": {}}] # 組み込みのコード実行環境を有効化
    )
)
```
