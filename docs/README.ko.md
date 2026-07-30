<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — 범용 AI 게이트웨이</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  20+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## 왜 uag인가요?

**공급업체 종속에서 벗어나세요.** 대부분의 AI 도우미는 사용자를 특정 공급자나 클라우드 서비스에 연결합니다. uag는 다릅니다.

- **컴퓨터에서 로컬로 실행**됩니다. 귀하의 데이터는 귀하와 함께 유지됩니다(귀하의 API 호출 제외).
- **제공자의 자유**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21개 이상의 제공자, 모두 단일 인터페이스에서 액세스 가능. 환경 변수를 재구성하여 서로 교체하세요. 다시 설치하거나 마이그레이션할 필요가 없습니다.
- **135개 도구**: 파일 I/O, 웹 검색, 이미지 생성, Gmail, BLE 장치 검색, MCP 서버 통합 — **78개는 병렬 안전**(스레드 풀을 통해 최대 8개가 동시에 실행되고 `UAGENT_PARALLEL_WORKERS`를 통해 구성 가능). LLM이 한 번에 여러 도구 호출을 실행하면 uag가 자동으로 이를 병렬화합니다.
- **3개의 UI + A2A**: CLI, GUI, 웹 및 에이전트 간 프로토콜. 동일한 엔진, 모든 인터페이스.
- **에이전트 스킬**: 마켓플레이스에서 커뮤니티 구축 스킬을 설치합니다. uag를 끝없이 확장하세요.

uag는 **귀하의 조건에 맞는 AI 비서**입니다. 공급자에 묶이지 않고, 인터페이스에 묶이지 않고, 플랫폼에 묶이지 않습니다.

## 빠른 시작

```bash
pip install uag
uag
```

처음 실행하면 설정 마법사가 공급자 구성 과정을 안내합니다.
모든 환경 변수는 [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)를 참조하세요.

## 특징

### 🧠 다중 제공자 아키텍처

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI(Zhipu AI) / HuggingFace / Alibaba Cloud(Qwen) / KIMI(Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI(Fugu)** / **Together AI** / **Vercel AI Gateway**

모든 공급자는 동일한 도구 세트와 인터페이스를 공유합니다. `UAGENT_PROVIDER` 설정으로 전환하세요. 코드 변경이나 별도 설치가 필요하지 않습니다.

### ⚡ 병렬 도구 실행

LLM이 여러 도구를 동시에 요청하면 uag가 해당 도구를 **자동으로 병렬화**합니다.
78개의 도구는 `x_parallel_safe`로 표시되어 `ThreadPoolExecutor`를 통해 동시에 실행됩니다(기본적으로 8개의 스레드, 변경하려면 `UAGENT_PARALLEL_WORKERS` 설정).

**예**: "북유럽 수도의 날씨를 확인하세요"라고 질문 → LLM에서 `search_web` × 5개 국가 실행 → 5개 검색이 모두 병렬로 실행됨 → 결과가 한 번에 수집됩니다.

읽기 전용 도구(파일 검색, 해시 계산, 디렉터리 목록, 번역, DB 쿼리 등)는 적극적으로 병렬화됩니다.


### 🧩 Plugin System (Claude Code Compatible)

uagent implements a **Claude Code-compatible plugin system**. Plugins bundle skills, agents, MCP servers, hooks, and more into self-contained directories with a `.claude-plugin/plugin.json` manifest.

**Supported components**: Skills, Sub-agents, MCP servers, Hooks (12 lifecycle events), Slash commands, Output styles, userConfig, Dependencies, Channels, Marketplaces

**CLI commands**:
```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

See [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for full documentation.


### 🔄 세션 연속성

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 195  도구

| 카테고리 | 도구 |
|---|---|
| **파일 작업** | 읽기/쓰기/생성/삭제/검색/grep/hash/zip, file_type, parse_eml(.eml 파일) |
| **웹** | fetch_url, search_web, 스크린샷, browser_playwright |
| **미디어** | generate_image, analyze_image, img2img, audio_speech, audio_transcribe |
| **문서** | PDF/PPTX/DOCX/RTF/ODT 추출, Excel 구조 추출 |
| **예측** | 9개 모델(AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM 등)을 사용한 시계열 예측, 자동 모델 선택, 플롯 생성, i18n |
| **커뮤니케이션** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook, **pybitchat** (BLE Mesh) — [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) 및 [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) 참조|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **개발 도구** | git_ops, python_compile, lint_format, run_tests, db_query, **26개의 소스 코드 탐색기(idx 제품군)** |
| **MCP** | 외부 MCP 서버에 연결하고, 도구를 나열하고, 실행 |
| **A2A** | 에이전트 간 통신(다른 uag 인스턴스 또는 A2A 호환 서버 사용) |
| **시스템** | 환경 변수, 시스템 사양, 시간, 날짜 계산, uuid_gen, slugify ||
| **소스 탐색** | Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL용 **26가지 idx 도구** — 전체 파일을 읽지 않고도 함수/클래스 색인 또는 특정 정의 가져오기 |

### 🖥 4가지 인터페이스 + VS 코드 확장

| 모드 | 명령 | 목적 |
|---|---|---|
| **CLI** | `uag` | 빠른 터미널 기반 운영 |
| **GUI** | `uagg` | tkinter를 통한 데스크탑 UI |
| **웹** | `uagw` | 브라우저 기반 액세스 |
| **A2A 서버** | `uaga` | 다중 에이전트 통신을 위한 Agent2Agent 프로토콜 |
| **VS 코드** | — | 채팅 패널, 설명, 리팩터링, 오류 수정 및 도구 트리 보기가 포함된 [확장](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |

VS Code 확장(설치, 명령, 키 바인딩 및 구성)에 대한 자세한 내용은 [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md)를 참조하세요.

### 🏠 IoT 장치 제어
- **사항**: 컨트롤러/브릿지/장치 토폴로지의 읽기 전용 검사

[IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)를 참조하세요.


### 🎯 상담원 기술 마켓플레이스

`:skills mp_search`를 사용하여 [SkillsMP](https://skillsmp.com) 및 [ClawHub](https://clawhub.ai)에서 커뮤니티 기술을 찾아보세요.
uag의 기능을 즉시 설치하고 확장하세요.

### 🤖 자동 조종(`:auto`)

uag는 **여러 LLM 라운드에서 자율적으로 목표를 추구**할 수 있습니다. 반복적인 개선이 필요한 복잡한 다단계 작업에 적합합니다.

- **작동 방식**: 각 라운드에는 기본 쿼리(A단계)와 "COMPLETE 또는 CONTINUE?"를 결정하는 리뷰어 판단(B단계)이 있습니다.
- **동일한 공급자, 동일한 API**: 리뷰어 판단에서는 Responses API 지원을 포함하여 기본 쿼리와 동일한 코드 경로를 사용합니다.
- **별도의 심사위원 LLM**(선택 사항): 심사자에게 다른 제공자/모델을 사용하려면 `UAGENT_AP_PROVIDER`를 설정합니다(예: 심사를 위해 더 저렴한 모델 사용).
- **언제든지 종료**: `x` 키를 누르면 응답 중간에도 즉시 중지됩니다. 아니면 검토자가 목표 달성 시기를 결정하도록 하세요.
- **구성 가능**: `--max-rounds N`으로 예산을 제어합니다.

전체 문서는 [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)를 참조하세요.

### 🧩 배치 상태 관리자

uag는 장기 실행 다중 파일 작업의 진행 상황을 추적할 수 있습니다. LLM이 수십 개의 파일을 처리할 때 `batch_state`는 보류 중인 파일, 완료된 파일, 실패한 파일 목록을 디스크에 유지합니다. 세션이 종료되거나 라운드 시간이 초과되면 다음 실행이 중지된 지점부터 다시 시작되므로 아무것도 손실되지 않습니다.

### 🛡 인간 참여형

`human_ask`를 사용하면 LLM이 파괴적인 작업(파일 삭제, 덮어쓰기, 셸 명령)을 수행하기 전에 일시 중지하고 확인을 요청할 수 있습니다. 당신은 통제권을 유지합니다.

### 🛑 중단(c-키/정지 버튼)

언제든지 LLM 응답 생성을 중지하고 LLM에 중지 명령을 다시 삽입하십시오.

| 인터페이스 | 방해하는 방법 |
|---|---|
| **CLI** | LLM 스트리밍 중에 `c` 키를 누르세요. 현재 응답이 중지되고 `"Stop"`이 사용자 메시지로 전송되어 LLM이 그에 따라 응답합니다 |
| **웹 UI** | 빨간색 **■ 중지** 버튼을 클릭합니다(LLM 처리 중에 자동으로 나타남) |
| **데스크탑 GUI** | 빨간색 **■** 버튼 클릭(LLM 처리 중 자동으로 나타남) |

인터럽트는 "즉시 주입"으로 작동합니다. 단순히 중단하는 대신 "Stop"을 사용자 메시지로 LLM에 다시 공급하여 중단을 정상적으로 종료하거나 승인할 수 있도록 합니다.

자동 조종 모드를 종료하려면 'x' 키를 누르세요([README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) 참조).

### 🕵️ 브라우저 자동화 및 웹 검사기

두 가지 보완적인 극작가 기반 도구:

- **browser_playwright**: 실제 브라우저 세션을 자동화합니다. 탐색, 클릭, 양식 채우기, 데이터 추출, 다중 페이지 흐름 처리. 헤드리스 또는 헤드리스로 작동합니다.
- **playwright_inspector**: 브라우저 전환을 기록하고 각 단계에서 DOM 스냅샷 및 스크린샷을 캡처합니다. 웹 상호 작용을 디버깅하거나 시간 경과에 따른 페이지 변경 사항을 감사하는 데 유용합니다.

### 🔄 동적 도구 로딩

`tool_catalog` 및 `tool_load`를 사용하면 런타임에 도구를 검색하고 활성화할 수 있습니다.
시작할 때 모든 것을 로드할 필요가 없습니다. 필요할 때 필요한 것만 활성화하세요.


### 🦀 Rust Native Tools

`uuid_gen` and `slugify` are implemented in Rust (via PyO3) for performance.
They load directly from a pre-built `.pyd` — **no `pip install` required**.

External developers can also ship Rust-based tools: place a `.pyd` next to the
wrapper `.py`, use ``load_rust_pyd()`` from ``uagent.tools.rust_helper``, and
users get the tool without any extra dependencies. See
[TOOL_CREATOR_GUIDE.ko.md](TOOL_CREATOR_GUIDE.ko.md).

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / and more.
전환하려면 'UAGENT_LANG'을 설정하세요. 새 로케일을 추가하려면 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)를 참조하세요.

이 README의 번역은 [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)에서 확인할 수 있습니다.

### 🔒 암호화된 환경 변수

암호화된 `.env` 파일인 `.env.sec`에 API 키와 비밀을 저장합니다.
`uag_envsec`으로 관리하세요.

## 구성 및 세부정보

- **환경 변수**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **설정 마법사**: `python -m uagent.setup_cli`
- **암호화된 환경**: `uag_envsec` — `.env`를 `.env.sec`로 암호화합니다.
- **응답 API**: 응답 API 모드(OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)에 대해 `UAGENT_RESPONSES=1`을 설정합니다. Sakana AI(Fugu)가 자동 활성화됩니다.
- **개발자 문서**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **도구 흐름**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **작은 LLM 팁**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## 프로젝트 철학

uag는 **귀하의 머신에서, 귀하의 조건에 따라 귀하의 AI가 되기를 열망합니다.**

- SaaS 종속성 없음 — 로컬에서 실행
- 공급자 종속 없음 - 언제든지 전환 가능
- UI 잠금 없음 — CLI / GUI / 웹 / A2A
- 기능 고정 없음 - 도구 및 기술로 확장

벤더 종속이 없는 무료 AI 에이전트 환경입니다.

### ✨ Create Your Own Tools

Writing a new tool for uag is straightforward — create a single `.py` file with
`TOOL_SPEC` and `run_tool()`, place it in ``UAGENT_EXTERNAL_TOOLS_DIR``, and
it's immediately available. For Rust developers, ship a pre-built `.pyd` with
zero extra dependencies for users.

See [TOOL_CREATOR_GUIDE.ko.md](TOOL_CREATOR_GUIDE.ko.md)
for the step-by-step guide.

## Contributing

Contributions are welcome! Bug reports, feature suggestions, documentation improvements, translations, and pull requests — all appreciated.

- **Issues**: Open a GitHub issue for bugs or feature requests.
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [DEVELOP.md](../src/uagent/docs/DEVELOP.md) for development setup and guidelines.
- **Translations**: README translations and locale additions are welcome. See [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: New tool plugins and Agent Skills can be contributed via the marketplace.

Realtime 음성 및 AEC3

## Realtime 음성 모드는 전이중 마이크 및 스피커 입력/출력을 지원합니다. AEC3 백엔드가 없으면 uag은 pywebrtc-audio을 자동으로 설치합니다.

**Realtime providers:** OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice, and Amazon Bedrock Nova Sonic. The Bedrock bidirectional-streaming SDK is installed automatically only when Bedrock is selected.

```bat
python scheck.py realtime
```

AEC3은 실제 마이크 신호(근거리)와 실제로 스피커(원거리)로 전송된 오디오를 사용합니다. 오디오 문제를 조사할 때만 진단을 활성화하십시오.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime는 안전이 제한된 Function Calling 통합을 지원합니다. 현재 어댑터는 읽기 전용 get_current_time 함수를 자동으로 노출합니다. 파괴적인 도구와 장치 제어에는 명시적인 허용 목록과 확인 흐름이 필요합니다. Grok 실시간은 별도의 어댑터를 사용하며 이 OpenAI 관련 Function Calling 경로를 사용하지 않습니다.
