<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag 로고" width="720">
</p>

<h1 align="center">uag — 범용 AI 게이트웨이</h1>

<p align="center">
  <b>U</b>유니버설 <b>A</b>I <b>G</b>ateway — 환경이 곧 자유입니다.
</p>

<p align="center">
  파일 운영 / 웹 검색 / 이미지 생성 및 분석 / PDF 및 엑셀 추출 / IoT 제어 / MCP 통합<br>
  15개 이상의 공급자 / 3개의 UI / 병렬 도구 실행 / 상담원 기술 마켓플레이스
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">귀하의 언어로 읽어보세요</a>
</p>

---

## 왜 uag인가요?

**공급업체 종속에서 벗어나세요.** 대부분의 AI 도우미는 사용자를 특정 공급자나 클라우드 서비스에 연결합니다. uag는 다릅니다.

- **컴퓨터에서 로컬로 실행**됩니다. 귀하의 데이터는 귀하와 함께 유지됩니다(귀하의 API 호출 제외).
- **제공자의 자유**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15개 이상의 제공자, 모두 단일 인터페이스에서 액세스 가능. 환경 변수를 재구성하여 서로 교체하세요. 다시 설치하거나 마이그레이션할 필요가 없습니다.
- **131개 도구**: 파일 I/O, 웹 검색, 이미지 생성, BLE 장치 검색, MCP 서버 통합 및 **76개 도구가 병렬로 실행됩니다**. LLM이 한 번에 여러 도구 호출을 실행하면 uag는 스레드 풀을 통해 자동으로 실행합니다.
- **4개의 UI + A2A**: CLI, GUI, 웹 및 에이전트 간 프로토콜. 동일한 엔진, 모든 인터페이스.
- **IoT 지원**: SwitchBot, ECHONET Lite, Matter, UPnP — AI를 통해 홈 장치를 제어하세요.
- **에이전트 스킬**: 마켓플레이스에서 커뮤니티 구축 스킬을 설치합니다. uag를 끝없이 확장하세요.

uag는 **귀하의 조건에 맞는 AI 비서**입니다. 공급자에 묶이지 않고, 인터페이스에 묶이지 않고, 플랫폼에 묶이지 않습니다.

## 빠른 시작

```bash
pip install uag
uag
```

처음 실행하면 설정 마법사가 공급자 구성 과정을 안내합니다.
모든 환경 변수는 [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)를 참조하세요.

## 기능

### 🧠 다중 제공자 아키텍처

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud(Qwen) / KIMI(Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

모든 공급자는 동일한 도구 세트와 인터페이스를 공유합니다. `UAGENT_PROVIDER` 설정으로 전환하세요. 코드 변경이나 별도 설치가 필요하지 않습니다.

### ⚡ 병렬 도구 실행

LLM이 여러 도구를 동시에 요청하면 uag가 해당 도구를 **자동으로 병렬화**합니다.
76개의 도구는 `x_parallel_safe`로 표시되어 있으며 4스레드 `ThreadPoolExecutor`를 통해 동시에 실행됩니다.

**예**: "북유럽 수도의 날씨를 확인하세요"라고 질문 → LLM에서 `search_web` × 5개 국가 실행 → 5개 검색이 모두 병렬로 실행됨 → 결과가 한 번에 수집됩니다.

읽기 전용 도구(파일 검색, 해시 계산, 디렉터리 목록, 번역, DB 쿼리 등)는 적극적으로 병렬화됩니다.

### 🔄 세션 연속성

- `UAGENT_PROVIDER`를 사용하여 **세션 중간에 공급자 전환** — 대화 기록이 보존됩니다.
- `:load <index>`를 사용하여 **지난 세션 다시 로드** — 중단한 부분부터 다시 시작하세요.
- **도구 결과 캐싱**은 동일한 도구 호출이 반복될 때 중복된 재실행을 방지합니다.

### 🛠 131 도구

| 카테고리 | 도구 |
|---|---|
| **파일 작업** | 읽기/쓰기/생성/삭제/검색/grep/해시/zip |
| **웹** | fetch_url, search_web, 스크린샷, browser_playwright |
| **미디어** | generate_image, analyze_image, img2img, audio_speech, audio_transcribe |
| **문서** | PDF/PPTX/DOCX/RTF/ODT 추출, Excel 구조 추출 |
| **IoT** | SwitchBot(클라우드 + BLE), ECHONET Lite, Matter, UPnP |
| **개발 도구** | git_ops, python_compile, lint_format, run_tests, db_query, **13 idx tools** |
| **MCP** | 외부 MCP 서버에 연결하고, 도구를 나열하고, 실행 |
| **A2A** | 에이전트 간 통신(다른 uag 인스턴스 또는 A2A 호환 서버 사용) |
| **시스템** | 환경 변수, 시스템 사양, 시간, 날짜 계산 |

### 🖥 3개 인터페이스 + A2A + VS Code

| 모드 | 명령 | 목적 |
|---|---|---|
| **CLI** | `uag` | 빠른 터미널 기반 운영 |
| **GUI** | `uagg` | tkinter를 통한 데스크탑 UI |
| **웹** | `uagw` | 브라우저 기반 액세스 |
| **A2A 서버** | `uaga` | 다중 에이전트 통신을 위한 Agent2Agent 프로토콜 |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](VSCODE.md) |

### 🏠 IoT 장치 제어

- **SwitchBot**: 클라우드 일괄 제어 및 BLE 스캔/제어
- **ECHONET Lite**: 로컬 네트워크에서 가전제품(AC, 조명, 온수기 등)을 검색하고 제어합니다.
- **사항**: 컨트롤러/브릿지/장치 토폴로지의 읽기 전용 검사
- **UPnP**: 장치 검색 및 IGD 포트 전달

[IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)를 참조하세요.

### 🎯 상담원 기술 마켓플레이스

`:skills mp_search`를 사용하여 [SkillsMP](https://skillsmp.com) 및 [ClawHub](https://clawhub.ai)에서 커뮤니티 기술을 찾아보세요.
uag의 기능을 즉시 설치하고 확장하세요.

### 🧩 배치 상태 관리자

uag는 장기 실행 다중 파일 작업의 진행 상황을 추적할 수 있습니다. LLM이 수십 개의 파일을 처리할 때 `batch_state`는 보류 중인 파일, 완료된 파일, 실패한 파일 목록을 디스크에 유지합니다. 세션이 종료되거나 라운드 시간이 초과되면 다음 실행이 중지된 지점부터 다시 시작되므로 아무것도 손실되지 않습니다.

### 🛡 인간 참여형

`human_ask`를 사용하면 LLM이 파괴적인 작업(파일 삭제, 덮어쓰기, 셸 명령)을 수행하기 전에 일시 중지하고 확인을 요청할 수 있습니다. 당신은 통제권을 유지합니다.

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming -- the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

### 🕵️ 브라우저 자동화 및 웹 검사기

두 가지 보완적인 극작가 기반 도구:

- **browser_playwright**: 실제 브라우저 세션을 자동화합니다. 탐색, 클릭, 양식 채우기, 데이터 추출, 다중 페이지 흐름 처리. 헤드리스 또는 헤드리스로 작동합니다.
- **playwright_inspector**: 브라우저 전환을 기록하고 각 단계에서 DOM 스냅샷 및 스크린샷을 캡처합니다. 웹 상호 작용을 디버깅하거나 시간 경과에 따른 페이지 변경 사항을 감사하는 데 유용합니다.

### 🔄 동적 도구 로딩

`tool_catalog` 및 `tool_load`를 사용하면 런타임에 도구를 검색하고 활성화할 수 있습니다.
시작할 때 모든 것을 로드할 필요가 없습니다. 필요할 때 필요한 것만 활성화하세요.

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / and more.
전환하려면 'UAGENT_LANG'을 설정하세요. 새 로케일을 추가하려면 [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)를 참조하세요.

이 README의 번역은 [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)에서 확인할 수 있습니다.

### 🔒 암호화된 환경 변수

암호화된 `.env` 파일인 `.env.sec`에 API 키와 비밀을 저장합니다.
`uag_envsec`으로 관리하세요.

## 구성 및 세부정보

- **환경 변수**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **설정 마법사**: `python -m uagent.setup_cli`
- **암호화된 환경**: `uag_envsec` — `.env`를 `.env.sec`로 암호화합니다.
- **응답 API**: 응답 API 모드(OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)에 대해 'UAGENT_RESPONSES=1'을 설정합니다.
- **개발자 문서**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **작은 LLM 팁**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## 프로젝트 철학

uag는 **귀하의 머신에서, 귀하의 조건에 따라 귀하의 AI가 되기를 열망합니다.**

- SaaS 종속성 없음 — 로컬에서 실행
- 공급자 종속 없음 - 언제든지 전환 가능
- UI 잠금 없음 — CLI / GUI / 웹 / A2A
- 기능 고정 없음 - 도구 및 기술로 확장

벤더 종속이 없는 무료 AI 에이전트 환경입니다.