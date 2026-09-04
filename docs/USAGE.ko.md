# 사용법 (명령줄 옵션)

이 문서는 uag 엔트리 포인트에서 사용할 수 있는 명령줄 옵션에 대해 설명합니다.

______________________________________________________________________

## 진입점

| 명령어 | 파이썬 모듈 | 인터페이스 |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin 루프) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | 웹 서버 (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP 서버 |

______________________________________________________________________

## CLI 시작 옵션 (`uag`)

### `--workdir` / `-C <경로>`

작업 디렉터리. 설정되지 않은 경우 `UAGENT_WORKDIR` 환경 변수를 우선 적용하고, 그 다음에는 현재 디렉터리를 사용합니다.
디렉터리가 존재하지 않으면 생성됩니다.

### `--tool-genre-mask <정수>`

도구 장르 비트 마스크. 이 옵션이 지정되면 대화형 장르 선택 프롬프트가 건너뜁니다.

| 비트 | 장르 | 설명 |
|-----|-------|-------------|
| 1 | basic | 필수 파일/채팅 도구 |
| 2 | comm | 통신 도구 (Bluesky, Teams) |
| 4 | office | 오피스 제품군 도구 (Excel, PDF, PPTX) |
| 8 | devel | 개발 도구 (git, lint, compile) |
| 16 | iot | IoT 기기 도구 (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | 명령어 실행 도구 |
| 64 | external | 외부 플러그인 도구 |
| 128 | media | 이미지/오디오 생성 및 분석 |
| 256 | file | 파일 관리 도구 |
| 512 | index | 소스/인덱스 탐색 도구 |
| 1024 | dev | 개발자 및 저장소 도구 |
| 2048 | web | 웹 및 브라우저 도구 |
| 4096 | utility | 유틸리티 및 지원 도구 |
| 8191 | all | 모든 도구 |

예시:

```
uag --tool-genre-mask 1 # 기본 도구만
uag --tool-genre-mask 9 # 기본 + 개발 (1 + 8)
uag --tool-genre-mask 8191    # 모든 도구
```

### `--use-tool` / `--no-use-tool`

LLM에 도구 정의를 전송할지 여부를 설정합니다. `UAGENT_USE_TOOL` 환경 변수를 재정의합니다.

- `--use-tool`은 도구 전송을 강제 활성화합니다.
- `--no-use-tool`은 도구 전송을 강제 비활성화합니다.

비활성화된 경우, LLM은 도구 정의를 수신하지 않으며 어떤 도구도 호출할 수 없습니다.

### `--computer-use` / `--no-computer-use`

Computer Use을 활성화하거나 비활성화합니다. `UAGENT_COMPUTER_USE` 환경 변수를 재정의합니다.

### `--inject-message` / `-M <message>`

시작 시 LLM에 메시지를 삽입하고, 작업 완료 후 종료합니다. 이는 `--non-interactive`를 의미합니다.

### `--embedded`

자원이 제한적이거나 재현성이 중요한 배포를 위한 임베디드 모드입니다.

- 세션 저장소를 비활성화합니다.
- 명시적으로 활성화되지 않는 한 도구 관리 도구(`tool_catalog`, `tool_load`, `unload_tool`)를 숨깁니다.
- `--tool-genre-mask`를 무시합니다. 도구를 명시적으로 로드하려면 `--enable-tool`을 사용하십시오.

### `--enable-tool <이름>`

시작 시 도구를 명시적으로 로드합니다. 이 옵션을 여러 번 지정할 수 있으며, 쉼표로 구분된 이름도 허용됩니다.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

지정된 순서는 유지되며, LLM에 전달되는 도구 순서에 반영됩니다. 명시적으로 활성화된 도구는 자동 언로드되지 않도록 고정됩니다.

### `--plugin-dir <경로>`

지정된 디렉터리에서 플러그인을 로드합니다. 이 옵션을 반복하여 지정할 수 있습니다.

______________________________________________________________________

## CLI 전용 옵션

### `--inject-message-auto <goal-options>`

비대화형 주입 목표에서 자동 조종 모드를 시작합니다. 이 값은 `:auto`와 동일한 옵션을 사용하며, 옵션이 포함된 경우 전체 값을 따옴표로 묶어야 합니다.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "항목 정렬 --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "항목 정렬 --infinite"
```

일반 모드는 검토자의 판단 경로를 사용합니다. `UAGENT_AUTO_SENTINEL=1`를 설정하여 단일 LLM 센티넬 모드를 선택하십시오. 이 모드에서 대상 LLM은 각 응답을 다음 중 정확히 하나만 사용하여 끝내야 합니다:

- `<AUTO_CONTINUE>` — 다음 라운드 실행
- `<AUTO_COMPLETE>` — 성공적으로 완료

마커가 없거나 유효하지 않은 경우 자동 조종 모드가 안전하게 중지됩니다. 이 경우 대상 LLM은 여전히 실행되지만, 추가적인 검토자 LLM 호출만 생략됩니다.

### `--non-interactive`

비대화형 모드입니다. stdin 루프를 시작하지 않습니다. 파일 경로가 위치 인수로 지정된 경우, 해당 경로를 처리한 후 프로그램이 즉시 종료됩니다.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## 웹 서버 옵션 (`uagw`)

### `--host <address>`

웹 서버의 바인딩 주소(기본값: `127.0.0.1`, `UAGENT_WEB_HOST`로 재정의 가능).

기본적으로 웹 서버는 localhost(`127.0.0.1`)에서만 연결을 수신 대기합니다. 네트워크상의 다른 컴퓨터에서도 접근할 수 있게 하려면 `--host 0.0.0.0`을 사용하십시오.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

위에서 설명한 것과 동일한 비트 마스크를 사용하여 도구 장르를 선택합니다. 이 옵션이 지정되면 대화형 장르 프롬프트가 건너뜁니다.

### `--use-tool` / `--no-use-tool`

LLM으로 도구 정의를 전송하도록 설정하거나 비활성화합니다. `UAGENT_USE_TOOL`을 재정의합니다.

### `--computer-use` / `--no-computer-use`

Computer Use을 활성화하거나 비활성화합니다. `UAGENT_COMPUTER_USE`을 재정의합니다.

### `--no-frontend`

HTML 템플릿이나 정적 프론트엔드 파일 없이 API만 실행합니다.

### `--embedded`

세션 저장소를 비활성화하고 도구 관리 도구(`tool_catalog`, `tool_load`, `unload_tool`)를 숨깁니다.

______________________________________________________________________

## A2A 서버 옵션 (`uaga`)

### `--host <address>`

A2A HTTP 서버의 바인딩 주소(기본값: `0.0.0.0`, `UAGENT_A2A_HOST`로 재정의 가능).

### `--port <숫자>`

A2A HTTP 서버의 포트 번호(기본값: `8765`, `UAGENT_A2A_PORT`로 재정의 가능).

### `--reload`

코드 변경 시 핫 리로드를 활성화합니다(기본값: 비활성화, `UAGENT_A2A_RELOAD`으로 재정의 가능).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <정수>`

위에서 설명한 비트 마스크를 사용하여 도구 장르를 선택합니다. 이 옵션이 지정되면 대화형 장르 프롬프트가 건너뜁니다.

### `--use-tool` / `--no-use-tool`

LLM으로 도구 정의를 전송하는 기능을 활성화하거나 비활성화합니다. `UAGENT_USE_TOOL`을 재정의합니다.

### `--computer-use` / `--no-computer-use`

Computer Use을 활성화하거나 비활성화합니다. `UAGENT_COMPUTER_USE`을 재정의합니다.

### `--embedded`

세션 저장소를 비활성화하고 도구 관리 도구(`tool_catalog`, `tool_load`, `unload_tool`)를 숨깁니다.

______________________________________________________________________

## 관련 환경 변수

| 변수 | 설명 |
|---|---|
| `UAGENT_PROVIDER` | LLM 공급자 이름 (시작 시 필수) |
| `UAGENT_*_API_KEY` | 선택한 공급자에 대한 API 키 |
| `UAGENT_WORKDIR` | 기본 작업 디렉터리 |
| `UAGENT_WEB_HOST` | 웹 서버 바인드 주소 (기본값: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A 서버 바인드 주소 (기본값: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | A2A 서버 포트 (기본값: `8765`) |
| `UAGENT_A2A_RELOAD` | 기본적으로 A2A 핫 리로드 활성화 |
| `UAGENT_USE_TOOL` | `0`, `false`, `no` 또는 `off`로 설정 시 도구 비활성화 |
| `UAGENT_COMPUTER_USE` | 기본적으로 Computer Use 활성화 또는 비활성화 |
| `UAGENT_SESSION_STORE` | 세션 저장소 활성화 또는 비활성화; 임베디드 모드에서는 `0`으로 강제 설정 |
| `UAGENT_PLUGIN_DIRS` | 추가 플러그인 검색 디렉터리 |
| `UAGENT_AUTO_SENTINEL` | `1`로 설정 시 단일 LLM 오토파일럿 센티넬 모드를 선택 |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | 최대 연속 신규 도구 호출 횟수 (기본값: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | 사용자 작업당 최대 LLM/tool 라운드 수 (기본값: `200`) |
| `UAGENT_SHRINK_CNT` | 메시지 내 선택적 자동 축소 임계값 (`0`/설정 없음 = 비활성화) |
| `UAGENT_SHRINK_KEEP_LAST` | 축소 후 유지할 메시지 수 (기본값: `20`) |
| `UAGENT_LANG` | 인터페이스 언어 (`ja`, `en` 등) |

환경 변수의 전체 목록은 [ENVIRONMENT.md](ENVIRONMENT.md)를 참조하십시오.

______________________________________________________________________

## 예제

### OpenAI를 사용한 최소 구성

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### 기본 도구만 포함된 로컬 Ollama

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### 모든 인터페이스에 웹 서버

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

또는

```
uagw --host 0.0.0.0
```

### 사용자 지정 포트를 사용하는 로컬호스트의 A2A 서버

```
uaga --host 127.0.0.1 --port 8080
```

### 소규모 모델에 대한 도구 비활성화

```
uag --no-use-tool --tool-genre-mask 1
```

### 비대화형 파일 처리

```
uag --non-interactive README.md
```
