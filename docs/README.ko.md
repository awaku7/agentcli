<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — 범용 AI 게이트웨이</h1>

<p align="center">
 <b>U</b>universal <b>A</b>I <b>G</b>ateway — 환경은 자유입니다.
</p>

<p align="center">
 파일 작업 / Web 검색 / 이미지 생성 및 분석 / PDF 및 Excel 추출 / IoT 제어 / MCP 통합<br>
 24개 공급자 / 3개 UI / 병렬 도구 실행 / 에이전트 기술 마켓플레이스
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">귀하의 언어로 읽어보세요</a>
</p>

______________________________________________________________________

## 왜 uag인가요?

**공급업체 종속에서 벗어나세요.** 대부분의 AI 도우미는 사용자를 특정 공급자나 클라우드 서비스에 연결합니다. uag은 다릅니다.

- **컴퓨터에서 로컬로 실행**됩니다. 귀하의 데이터는 귀하와 함께 유지됩니다(귀하의 API 통화 제외).
- **제공자의 자유**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24개의 제공자, 모두 단일 인터페이스에서 액세스 가능. 환경 변수를 재구성하여 교체하세요. 재설치나 마이그레이션이 필요하지 않습니다.
- **222개 도구**: 파일 I/O, 웹 검색, 이미지 생성, Gmail, BLE 장치 검색, MCP 서버 통합 — **130개는 정적으로 병렬 안전으로 표시됩니다**(최대 8개는 스레드 풀을 통해 동시에 실행되며 `UAGENT_PARALLEL_WORKERS`를 통해 구성 가능). LLM이 한 번에 여러 도구 호출을 실행하면 uag이 자동으로 이를 병렬화합니다.
- **3 UI + A2A**: CLI, GUI, Web 및 에이전트 간 프로토콜. 동일한 엔진, 모든 인터페이스.
- **IoT 지원**: SwitchBot, ECHONET Lite, Matter, UPnP — AI를 통해 홈 장치를 제어합니다.
- **에이전트 기술**: 마켓플레이스에서 커뮤니티 구축 기술을 설치합니다. uag을 끝없이 확장하세요.

uag은 **귀하의 조건에 맞는 AI 비서**입니다. 공급자에 묶이지 않고, 인터페이스에 묶이지 않고, 플랫폼에 묶이지 않습니다.

## 빠른 시작

```bash
pip install uag
uag
```

처음 시작하면 설정 마법사가 공급자 구성 과정을 안내합니다.
모든 환경 변수는 [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)를 참조하세요.

## Computer Use

Computer Use은 선택 사항이며 표시되는 Playwright 브라우저 런타임
과 데스크톱 런타임을 모두 지원합니다. 활성화되면 두 런타임이 모두 생성 및 등록됩니다.
선택한 런타임은 `UAGENT_COMPUTER_ENVIRONMENT`에 의해 제어됩니다:

```bat
set UAGENT_COMPUTER_USE=1
set UAGENT_COMPUTER_ENVIRONMENT=browser
```

대신 `desktop`을 사용하여 OS 데스크톱 런타임을 선택하세요. Runtime 리소스는
정상 종료, `Ctrl-C` 및 프로세스 종료 시 함께 닫힙니다. 브라우저 기반 CI 또는 스모크 테스트의 경우
`UAGENT_COMPUTER_HEADLESS=1`을 설정합니다.
통합 및 안전 세부정보는 [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
를 참조하세요.

## 실시간 음성 및 AEC3

실시간 음성 모드는 전이중 마이크 및 스피커 I/O를 갖춘 OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API 및 Amazon Bedrock Nova Sonic을 지원합니다. 필수 `pywebrtc-audio` AEC3 백엔드는 자동으로 설치되며 Bedrock의 선택적 양방향 스트리밍 SDK는 Bedrock 공급자가 선택된 경우에만 자동으로 설치됩니다.

```bash
python scheck.py realtime
```

AEC3 파이프라인은 실제 마이크 신호(`near`)와 실제로 스피커(`far`)로 전달되는 오디오를 수신하므로 보조자가 말하는 동안 들을 수 있습니다. 오디오 문제를 조사할 때만 진단 활성화:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI 실시간 함수 호출

OpenAI Realtime은 안전이 제한된 함수 호출 통합을 지원합니다. 현재 실시간 어댑터는 읽기 전용 'get_current_time'을 자동으로 노출합니다. 파괴적인 도구와 장치 제어는 명시적인 허용 목록 및 확인 흐름 없이는 노출되지 않습니다. Grok 실시간은 별도의 어댑터를 사용하며 이 OpenAI 관련 함수 호출 경로를 사용하지 않습니다.

## 기능

### 🧠 다중 공급자 아키텍처

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI(Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI(Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI(Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

모든 제공업체는 동일한 도구 세트와 인터페이스를 공유합니다. `UAGENT_PROVIDER` 설정으로 전환하세요. 코드 변경이나 별도 설치가 필요하지 않습니다.

#### Ollama와 llama.cpp

Ollama와 llama.cpp는 별도의 공급자입니다. Ollama는 자체 서비스 및 모델 관리를 사용하는 반면 `llama.cpp`는 `llama-server` OpenAI 호환 엔드포인트에 연결됩니다:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

llama.cpp 공급자는 채팅 완료 호환 경로를 사용합니다. 호환되는 프록시가 구성되어 있지 않으면 `UAGENT_RESPONSES=0`을 유지합니다.

### ⚡ 병렬 도구 실행

LLM이 여러 도구를 동시에 요청하면 uag **자동으로 병렬화**합니다.
130개 도구는 정적으로 `x_parallel_safe`로 표시되고 `ThreadPoolExecutor`를 통해 동시에 실행됩니다(기본적으로 8개의 스레드, 설정됨). `UAGENT_PARALLEL_WORKERS` 변경).

**예**: "북유럽 수도의 날씨를 확인하세요"라고 질문 → LLM은 `search_web` × 5개 국가 실행 → 5개의 검색이 모두 병렬로 실행 → 결과가 한 배치로 수집됩니다.

현재 개수는 'TOOL_SPEC'을 정의하는 도구 모듈을 기반으로 합니다(현재 222개, `src/uagent/tools_rust/`). `http_request`는 메소드에 민감한 안전성을 사용합니다. `GET`/`HEAD`/`OPTIONS` 호출은 병렬로 실행될 수 있지만 쓰기 메소드는 직렬로 유지됩니다.

읽기 전용 도구(파일 검색, 해시 계산, 디렉토리 목록, 번역, DB 쿼리 등)는 적극적으로 병렬화됩니다.

### 🧩 플러그인 시스템(Claude 코드 호환)

uagent는 **Claude를 구현합니다. 코드 호환 플러그인 시스템**. 플러그인은 기술, 에이전트, MCP 서버, 후크 등을 `.claude-plugin/plugin.json` 매니페스트를 통해 자체 포함 디렉터리에 포함합니다.

**지원되는 구성 요소**: 기술, 하위 에이전트, MCP 서버, 후크(12개의 수명 주기 이벤트), 슬래시 명령, 출력 스타일, userConfig, 종속성, 채널, 마켓플레이스

**CLI 명령**:

```
:plugin list # 설치된 플러그인 목록
:plugin install <source> [--scope] # 설치 (dir/zip/git/http)
:plugin install <name>@<marketplace> # 마켓플레이스에서 설치
:plugin delete <name> # Uninstall
:plugin 활성화/비활성화 <name> # Toggle
:plugin 마켓플레이스 add/remove/list # 관리 마켓플레이스
:plugin init <name> # 스캐폴드 새 플러그인
```

전체 문서는 [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md)를 참조하세요.

### 🔄 세션 연속성

- **세션 중간에 공급자 전환** `UAGENT_PROVIDER` — 대화 기록이 보존됩니다.
- `:load <index>`를 사용하여 **이전 세션 다시 로드** — 중단한 부분부터 다시 시작합니다.
- **도구 결과 캐싱**은 동일한 도구 호출이 반복될 때 중복 재실행을 방지합니다.

### 🛠 229 도구

| 카테고리 | 도구 |
|---|---|
| **파일 작업** | 읽기/쓰기/생성/삭제/검색/grep/hash/zip, file_type, pars_eml (.eml 파일), `path_alias` |
| **Web** | fetch_url, search_web, 스크린샷, browser_playwright, `url_alias`, `public_transit_route` ([가이드](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **미디어** | generate_image, analyze_image, img2img, audio_speech, audio_transcribe |
| **문서** | PDF/PPTX/DOCX/RTF/ODT 추출, Excel 구조 추출 |
| **예측** | 9개 모델(AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM 등)을 사용한 시계열 예측, 자동 모델 선택, 플롯 생성, i18n |
| **커뮤니케이션** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook, **pybitchat**(BLE 메시) - [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) 참조 및 [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot(클라우드 + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **클라우드 API** | `aws_api`, `gcp_api`, `azure_api` — 일반 AWS, Google 클라우드 및 Azure API 작업. 쓰기 작업에는 명시적인 확인이 필요합니다 |
| **개발 도구** | 작업 공간_상태, git_ops, git_review, security_scan, Coverage_report, python_compile, lint_format, run_tests, db_query, **29 소스 코드 탐색기(idx 제품군)** |
| **MCP** | 외부 MCP 서버에 연결, 도구 나열, 실행 — [OAuth/프록시 가이드](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | 에이전트 간 통신(다른 uag 인스턴스 또는 A2A 호환 서버 사용) |
| **시스템** | env 변수, 시스템 사양, 시간, 날짜 계산, [수량](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **소스 탐색** | **29개의 idx 도구**(Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — 전체 파일을 읽지 않고 함수/클래스 색인 또는 특정 정의 가져오기 |

#### 저장소 검토 및 적용 범위

- `workspace_status`: 활성 작업공간의 Git 분기, 변경 사항 보고, 파일을 수정하지 않고 업스트림 동기화 상태, Python 런타임 및 일반 프로젝트 마커.
- `git_review`: 비밀 값을 노출하지 않고 Git 변경 사항, 위험한 파일, 테스트 후보, 비밀 결과를 요약합니다.
- `security_scan`: 저장소 파일에서 가능성이 있는 비밀과 위험한 구성 파일을 검색합니다.
- `coverage_report`: Python, TypeScript/JavaScript, Rust, Go에 대한 적용 범위를 실행하고 정규화합니다. Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift 및 Dart/Flutter.
- 누락된 적용 범위 종속성은 실행 요청 시 자동으로 설치될 수 있습니다. `dry_run`은 패키지를 설치하지 않습니다.

매개변수, 출력 및 안전 세부정보는 [리포지토리 분석 도구](docs/REPOSITORY_TOOLS.md)를 참조하세요.

도구 인수에서 반복되는 파일 경로와 URL을 단축하려면 [경로 및 URL 별칭](docs/PATH_URL_ALIASES.md)을 참조하세요.

### 🖥 4 인터페이스 + VS 코드 확장 프로그램

| 모드 | 명령 | 목적 |
|---|---|---|
| **CLI** | \`\`uag`| 빠른 터미널 기반 작업 | | **GUI** |`uagg`| tkinter를 통한 데스크탑 UI | | **Web** |`uagw`| 브라우저 기반 액세스 | | **A2A 서버** |`uaga\` | 다중 에이전트 통신을 위한 Agent2Agent 프로토콜 |
| **VS 코드** | — | 채팅 패널, 설명, 리팩터링, 오류 수정 및 도구 트리 보기가 포함된 [확장](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |

VS Code 확장(설치, 명령, 키 바인딩 및 구성.

### 🏠 IoT 장치 제어

- **BACnet**: BACnet/IP 장치(HVAC, 조명, 전력계)를 읽고 씁니다. 푸시 알림을 위한 COV 구독
- **Modbus TCP**: 보유/입력 레지스터 및 코일 읽기/쓰기. 폴링 기반 변경 모니터링
- **OPC UA**: 주소 공간 탐색, 변수 읽기/쓰기, 데이터 변경 구독
- **SwitchBot**: 클라우드 일괄 제어 및 BLE 스캔/제어. 폴링 기반 구독
- **ECHONET Lite**: 가전제품(AC, 조명, 온수기 등)의 INF 알림 검색, 제어 및 구독
- **Matter**: 읽기/쓰기 제어 + 상태 변경 모니터링을 위한 속성 구독
- **UPnP**: 장치 검색 및 IGD 포트 전달

참조 [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search`를 통해 커뮤니티의 [SkillsMP](https://skillsmp.com) 및 [ClawHub](https://clawhub.ai)를 찾아보세요.
즉시 uag의 기능을 설치하고 확장합니다.

### 🤖 자동 조종(`:auto`)

uag은 **여러 LLM 라운드에 걸쳐 자동으로 목표를 추구**할 수 있습니다. 반복적인 개선이 필요한 복잡한 다단계 작업에 적합합니다.

- **작동 방식**: 각 라운드에는 기본 쿼리(A단계)가 있고 이어서 "COMPLETE 또는 CONTINUE?"를 결정하는 리뷰어 판단(단계 B)이 있습니다.
- **동일한 공급자, 동일 API**: 리뷰어 판단은 응답 API 지원을 포함하여 기본 쿼리와 동일한 코드 경로를 사용합니다.
- **별도의 판단 LLM** (선택 사항): 검토자를 위해 다른 제공업체/모델을 사용하려면 `UAGENT_AP_PROVIDER`를 설정합니다(예: 심사를 위해 더 저렴한 모델 사용).
- **언제든지 종료**: 응답 도중이라도 즉시 중지하려면 `x` 키를 누르세요. 또는 검토자가 목표 달성 시기를 결정하도록 합니다.
- **구성 가능**: `--max-rounds N`으로 예산을 제어합니다.

전체 문서는 [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)를 참조하세요.

### 🧩 배치 상태 Manager

uag은 장기 실행 다중 파일 작업의 진행 상황을 추적할 수 있습니다. LLM이 수십 개의 파일을 처리할 때 'batch_state'는 보류 중인 파일, 완료된 파일, 실패한 파일 목록을 디스크에 유지합니다. 세션이 종료되거나 라운드 시간이 초과되면 다음 실행이 중지된 곳에서 다시 시작됩니다. 아무 것도 손실되지 않습니다.

### 🛡 Human-in-the-Loop

`human_ask`를 사용하면 파괴적인 작업(파일 삭제, 덮어쓰기, 셸 명령)을 수행하기 전에 LLM을 일시 중지하고 확인을 요청할 수 있습니다. 제어권을 유지합니다.

### 🛑 인터럽트(c-키/중지 버튼)

언제든지 LLM 응답 생성을 중지하고 LLM에 중지 명령을 다시 삽입합니다.

| 인터페이스 | 방해하는 방법 |
|---|---|
| **CLI** | LLM 스트리밍 중에 `c` 키를 누르세요. 현재 응답이 중지되고 `"Stop"`이 사용자 메시지로 전송되어 LLM이 그에 따라 응답합니다 |
| **웹 UI** | 빨간색 **■ 중지** 버튼을 클릭합니다(LLM 처리 중에 자동으로 나타남) |
| **데스크톱 GUI** | 빨간색 **■** 버튼을 클릭합니다(LLM 처리 중에 자동으로 나타남) |

인터럽트는 "프롬프트 주입"으로 작동합니다. 단순히 중단하는 대신 LLM에 사용자 메시지로 `"중지"`를 다시 제공하여 중단을 정상적으로 종료하거나 승인할 수 있도록 합니다.

자동 조종 모드를 종료하려면 `x` 키를 누르세요. [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ 브라우저 자동화 및 Web Inspector

2개의 보완적인 Playwright 기반 도구:

- **browser_playwright**: 실제 브라우저 세션 자동화 — 탐색, 클릭, 양식 채우기, 데이터를 추출하고, 다중 페이지 흐름을 처리합니다. 헤드리스 또는 헤드리스로 작동합니다.
- **playwright_inspector**: 브라우저 전환을 기록하고 각 단계에서 DOM 스냅샷 및 스크린샷을 캡처합니다. 웹 상호 작용 디버깅이나 시간 경과에 따른 페이지 변경 감사에 유용합니다.

### 🔄 동적 도구 로딩

`tool_catalog` 및 `tool_load`를 사용하면 런타임에 도구를 검색하고 활성화할 수 있습니다.
시작 시 모든 것을 로드할 필요가 없습니다. 필요할 때 필요한 것만 활성화하세요.

### 🦀 Rust Native Tools

`uuid_gen` 및 `slugify`는 성능을 위해 Rust(PyO3를 통해)로 구현됩니다.
미리 빌드된 `.pyd`에서 직접 로드합니다 — **`pip install`이 필요하지 않습니다**.

외부 개발자도 Rust 기반 도구를 출시할 수 있습니다.
래퍼 `.py` 옆에 `.pyd`를 배치하고 `uagent.tools.rust_helper`에서 `load_rust_pyd()`를 사용합니다. 그리고
사용자는 추가 종속성 없이 도구를 얻을 수 있습니다.
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)를 참조하세요.

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / English / Español / Français / Русский / 등.
`UAGENT_LANG`을 스위치로 설정하세요. 새 로케일을 추가하려면 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)를 참조하세요.

이 README의 번역은 다음에서 제공됩니다. [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 암호화된 환경 변수

API 키와 비밀을 `.env.sec`(암호화된 `.env` 파일)에 저장합니다.
관리 `uag_envsec`.

## 구성 및 세부 정보

- **환경 변수**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **설정 마법사**: `python -m uagent.setup_cli`
- **암호화된 환경**: `uag_envsec` — encrypt `.env`를 `.env.sec`
  로 - **응답 API**: 응답 API 모드(OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)에 대해 'UAGENT_RESPONSES=1'을 설정합니다. Sakana AI(Fugu)에 대해 자동 활성화됩니다.
- **개발자 문서**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **도구 흐름**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — 도구가 LLM으로 전송되는 방법(장르 마스크, 도구_카탈로그, GPT-5.4+ 기본 도구_검색)
- **소형 LLM 팁**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## 프로젝트 철학

uag는 \*\*귀하의 머신에서, 귀하의 조건에 따라 **귀하의 AI가 되기를 열망합니다.**

- SaaS 종속성 없음 — 로컬로 실행
- 공급자 종속 없음 — 언제든지 전환
- UI 종속 없음 — CLI / GUI / Web / A2A
- 기능 종속 없음 — 도구 및 기술로 확장

무료 공급업체 종속이 없는 AI 에이전트 경험.

### ✨ 나만의 도구 만들기

uag용 새 도구를 작성하는 것은 간단합니다.
`TOOL_SPEC` 및 `run_tool()`을 사용하여 단일 `.py` 파일을 만들고 `UAGENT_EXTERNAL_TOOLS_DIR`에 배치하면
즉시 사용할 수 있습니다. Rust 개발자의 경우 사용자에 대한 추가 종속성이 전혀 없는
사전 빌드 `.pyd`를 제공하세요.

단계별 가이드는 [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
를 참조하세요.

## 기여

기여를 환영합니다! 버그 보고서, 기능 제안, 문서 개선, 번역 및 끌어오기 요청 — 모두 감사합니다.

- **문제**: 버그 또는 기능 요청에 대해 GitHub 문제를 엽니다.
- **풀 요청**: 저장소를 포크하고, 변경하고, PR을 제출합니다. 개발 설정 및 지침은 [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)를 참조하세요.
- **번역**: README 번역 및 로케일 추가를 환영합니다. [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)를 참조하세요.
- **도구 및 기술**: 새로운 도구 플러그인과 에이전트 기술은 마켓플레이스를 통해 기여할 수 있습니다.

### 개발 확인(PR 전)

테스트 전용 종속성을 먼저 설치하세요. 런타임
종속성 목록에서 제외됩니다:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

푸시하기 전에 GitHub에서 사용하는 것과 동일한 검사를 실행합니다.

```bash
python -m ruff check src 테스트
python -m black --check src 테스트
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

더 빠른 로컬 반복을 위해 영향을 받은 테스트만 실행하세요:

```bash
pytest -q 테스트/<영향을 받는_지역>
```

다음 경우에 추가 확인 관련:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

로케일(`.po`) 편집 후: `python scripts/compile_locales.py` 및 `python scripts/po_qc_summary.py`.

Runtime 정책(세부 사항 [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): 'sys.exit' 대신 도우미가 발생합니다. 도구 호스트는 `SystemExit`/`Exception` 도구를 오류 문자열로 변환하므로 단일 도구가 프로세스를 종료할 수 없습니다. 시작 시 빠른 종료는 의도된 것입니다.

## 아키텍처 및 운영 불변성

A2A 수명 주기, I18N 컨텍스트, 선택적 종속성 설치, 도구 안전, 공급자 기능, OAuth 신뢰 경계, 구조화된 이벤트 및 승인 확인을 다루는 지속 가능한 계약은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를 참조하세요.

## 엔터프라이즈 정책 엔진

도구, 공급자, 자격 증명, MCP 서버, 네트워크, 기술 및 플러그인에 대한 조직 수준 정책이 지원됩니다. `UAGENT_POLICY_FILE`을 JSON/YAML 정책 파일로 설정합니다. 구성 예, 역할, 확인 및 허용 목록은 [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md)를 참조하세요.

### Runtime 복구 및 오케스트레이션

[RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md)를 참조하세요. 내구성 있는 복구, 종속성 인식 실행, 다중 에이전트 오케스트레이션 및 원격 A2A 사용을 위한 [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md).

참조 공유 런타임 리더 임대 조정을 위한 [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md)
