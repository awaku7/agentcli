curl "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash:streamGenerateContent?key=%UAGENT_VERTEXAI_API_KEY%" ^
  -X POST ^
  -H "Content-Type: application/json" ^
  -d "{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"Explain how AI works in a few words\"}]}]}"
