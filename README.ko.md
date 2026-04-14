# uag (uagent)

uag는 로컬 환경에서 실행되는 범용 도구 실행 에이전트입니다. 명령줄 인터페이스(CLI)를 통해 사용자와 상호 작용하며 지침에 따라 파일 작업, 웹 검색, Python 스크립트 실행 등 다양한 작업을 수행합니다.

## 주요 기능

- **로컬 파일 작업**: 파일 읽기, 쓰기, 편집 및 검색.
- **정보 검색**: DuckDuckGo를 이용한 웹 검색 및 웹 페이지 콘텐츠 추출.
- **코드 실행**: Python 스크립트 및 PowerShell 명령의 안전한 실행.
- **멀티미디어 처리**: 이미지 생성, PDF/PPTX 파일 읽기, 스크린샷 캡처.
- **다국어 지원**: 한국어, 일본어, 영어를 포함한 여러 언어를 지원합니다.
- **MCP (Model Context Protocol) 지원**: 외부 MCP 서버에 연결하여 기능을 확장할 수 있습니다.

## 설치 방법

PyPI에서 pip를 사용하여 설치할 수 있습니다.

```bash
pip install uag
```

처음 실행하면 설정 마법사가 자동으로 시작됩니다.

## 빠른 시작

설치 후 다음 명령을 입력하여 시작하십시오.

```bash
uag
```

시작 후 에이전트에게 다음과 같은 요청을 할 수 있습니다.
- "현재 디렉터리의 README를 읽고 내용을 요약해줘."
- "웹에서 최신 AI 뉴스를 검색하고 요약을 만들어줘."
- "images 폴더의 모든 PNG 파일을 ZIP으로 압축해줘."

## 설정 (환경 변수)

uag의 동작은 환경 변수를 통해 설정할 수 있습니다. 자세한 내용은 다음을 참조하십시오.
- [ENVIRONMENT.md (English)](ENVIRONMENT.md)

## 문서

- [README.md (English)](README.md)
- [README.ja.md (Japanese)](README.ja.md)

## 라이선스

Apache License 2.0에 따라 라이선스가 부여됩니다.
