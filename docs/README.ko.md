<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  하나의 로컬 에이전트. 모든 모델. 모든 도구. 나의 환경, 나의 규칙.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**uag가 필요한 이유**

uag는 선호하는 모델을 실제로 사용하는 도구에 연결하는 로컬 우선 AI 에이전트입니다.
파일, 브라우저, 코드베이스, 커뮤니케이션, 클라우드 API, IoT 기기, MCP 서버,
멀티 에이전트 워크플로를 위한 단일 확장 가능 런타임을 제공합니다.

- **프로바이더 선택의 자유** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek 등.
- **로컬 우선 실행** — 에이전트 런타임과 도구 실행은 컴퓨터에 유지되며, 선택한 API 호출만 외부로 나갑니다.
- **하나의 도구 계층** — 동일한 도구를 CLI, 데스크톱 GUI, 웹 UI, VS Code, A2A에서 사용할 수 있습니다.
- **병렬 실행을 기본으로 설계** — 서로 독립적인 읽기 전용 작업을 동시에 실행할 수 있습니다.
- **확장 가능** — 코어를 변경하지 않고 도구, 플러그인, Agent Skills, MCP 서버, Rust 기반 도구를 추가할 수 있습니다.
- **안전 고려** — 파괴적 작업, 자격 증명, 기기 제어, 네트워크 쓰기에 명시적 확인과 정책 제어를 적용할 수 있습니다.

> **요약하면:** uag는 AI 모델과 실제 환경 사이의 제어 플레인입니다.

> **🧠 문맥을 고려한 도구 결과** — 가능한 경우, 대용량 도구 결과는 활성 모델 문맥에서 제외됩니다. uag은 이를 아티팩트로 저장하고, 대신 안정적인 Artifact 참조를 포함한 제한된 미리보기를 모델에 전달합니다. 이는 도구가 방대한 결과를 생성할 때 후속 턴에 필요한 입력 토큰 수를 상당히 줄일 수 있습니다.
> [컨텍스트 압축 상세 가이드](CONTEXT_COMPRESSION.ko.md)

## 빠른 시작

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

처음 실행하면 설정 마법사가 열립니다. 프로바이더 설정을 돕고 선택한 설정을 로컬 환경에 저장합니다.

일반적인 기능 그룹을 설치하려면:

```bash
python -m pip install "uag[core,providers,tools]"
```

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## 인터페이스

| 인터페이스 | 명령 | 적합한 용도 |
|---|---|---|
| **CLI** | `uag` | 빠른 키보드 중심 작업 |
| **데스크톱 GUI** | `uagg` | 네이티브 데스크톱 환경 |
| **웹 UI** | `uagw` | 브라우저 기반 액세스 |
| **A2A 서버** | `uaga` | 에이전트 간 커뮤니케이션 |
| **VS Code** | Extension | 편집기에서 도구를 설명하고, 리팩터링하고, 수정하고, 탐색 |

모든 인터페이스는 동일한 프로바이더 구성, 도구 레지스트리, 안전 규칙, 세션 데이터를 공유합니다.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## 무엇을 만들 수 있나요

프로바이더 어댑터는 다음을 포함한 호스팅 및 로컬 런타임을 지원합니다:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

`UAGENT_PROVIDER`로 프로바이더를 전환해도 도구와 인터페이스는 바뀌지 않습니다.

**환경과 작업**

- 파일 읽기, 생성, 편집, 검색, 해시 계산, 보관, 검사
- Git 변경 사항 검토, 시크릿 검색, 테스트 실행, 린트, 컴파일, 커버리지 측정
- 대규모 Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA 및 기타 코드베이스 탐색
- 다중 페이지 워크플로와 다운로드를 포함한 Playwright 브라우저 자동화

**서비스 및 기기 연결**

- **MCP** — OAuth 지원 서비스를 포함한 외부 도구 서버 연결
- **A2A** — 다른 에이전트 및 호환 서버와 협업
- **Cloud** — 쓰기 작업 확인을 포함한 AWS, Google Cloud, Azure API 액세스
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams, pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA, UPnP
- **Media** — 이미지 생성·편집, 오디오 전사·음성, 카메라 캡처, QR 코드
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL, 로그 분석

**IoT 및 현실 세계 제어**

- **SwitchBot** — 클라우드 및 BLE 검색, 상태, 제어, 일괄 처리, 구독
- **ECHONET Lite** — INF 알림을 포함한 일본 가전 검색 및 제어
- **Matter** — 엔드포인트, 클러스터, 속성, 상태 기록, 구독, 제어
- **BACnet / Modbus TCP / OPC UA** — 산업 및 빌딩 자동화의 읽기, 쓰기, 탐색, 모니터링
- **UPnP** — 기기 검색, WAN 상태, 라우터 포트 매핑 관리

### uag의 위치

한쪽의 사람과 인터페이스, 다른 쪽의 모델·도구·현실 세계 시스템 사이에 uag가 위치합니다.
대화를 조정하고, 기능을 선택하며, 안전 규칙을 적용하고, 워크플로를 재개할 수 있게 유지합니다.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### 플러그인, Agent Skills, 마켓플레이스

코어를 포크하지 않고 uag를 특화 에이전트로 만들 수 있습니다.

- 디렉터리, ZIP, Git 저장소, HTTP 소스, 마켓플레이스에서 **Claude Code 호환 플러그인** 설치
- 스킬, 하위 에이전트, MCP 서버, 훅, 슬래시 명령, 출력 스타일, 의존성, 채널 묶기
- [SkillsMP](https://skillsmp.com) 및 [ClawHub](https://clawhub.ai)에서 커뮤니티 기능 탐색
- `UAGENT_EXTERNAL_TOOLS_DIR`을 통해 비공개 조직 스킬과 도구를 로컬로 추가

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

[Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md)를 참조하세요.

- 파일, 웹, 미디어, 문서, 코드, 클라우드, 커뮤니케이션, IoT를 위한 **200개 이상의 도구**
- **동적 검색 및 로드** — `tool_catalog`으로 기능을 찾고 필요할 때만 `tool_load`로 활성화
- **코드 인텔리전스** — `code_map`, 언어별 `idx` 내비게이터, Git 검토, 테스트 실행, 린트, 컴파일, 커버리지
- 스킬, 에이전트, MCP 서버, 훅, 명령, 마켓플레이스를 지원하는 **Claude Code 호환 플러그인**
- SkillsMP와 ClawHub의 **Agent Skills**
- `TOOL_SPEC` 및 `run_tool()`을 사용하는 **커스텀 Python 도구**
- 가벼운 네이티브 확장을 위한 **Rust 기반 도구**

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## 실제 워크플로에 맞게 설계

### 🧠 문맥을 고려한 도구 결과

가능한 경우, 대용량 도구 결과는 활성 모델 문맥에서 제외됩니다. uag은 이를 아티팩트로 저장하고, 대신 안정적인 Artifact 참조를 포함한 제한된 미리보기를 모델에 전달합니다. 이는 도구가 방대한 결과를 생성할 때 후속 턴에 필요한 입력 토큰 수를 상당히 줄일 수 있습니다.

`:load <index>`로 이전 대화를 재개하세요. 도구 결과를 캐시할 수 있으며 애플리케이션을 다시 빌드하지 않고도 프로바이더를 변경할 수 있습니다.

[Context compression](CONTEXT_COMPRESSION.ko.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### 자동 조종

선택적 검토자 모델과 함께 여러 라운드의 작업을 수행하려면 `:auto`를 사용하세요. `--max-rounds N`으로 라운드 한도를 설정합니다.
자동 조종을 중지하려면 **F12**, 현재 응답을 중지하려면 **F12**를 누르세요.

안전한 경우 독립적인 읽기 전용 작업을 동시에 실행합니다. 웹 검색, 파일 검사,
저장소 분석 및 유사한 작업을 구성 가능한 작업자 풀(`UAGENT_PARALLEL_WORKERS`)로
병렬 완료할 수 있습니다. 쓰기 작업은 직렬화되거나 확인이 필요합니다.

세션 연속성, 도구 결과 캐싱, 배치 상태, 재시작 복구, DAG 스케줄링,
멀티 에이전트 오케스트레이션을 통해 복잡한 작업을 일회성 작업이 아닌 재개 가능한 작업으로 만듭니다.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 비공개·다국어·정책 인식

`human_ask`는 민감한 작업 전에 일시 중지합니다. 파일 삭제, 덮어쓰기, 셸 명령, 기기 제어,
자격 증명 작업, 네트워크 쓰기에 확인 및 정책 규칙을 적용할 수 있습니다.

프롬프트에 장기간 유효한 시크릿을 넣는 대신 자격 증명 저장소를 사용하세요.

웹 UI에는 Authorization Code + PKCE를 사용하는 OIDC 로그인, 검증된 ID 토큰, 서버 측 세션, 프로젝트/룸 접근 제어가 포함되어 있습니다. 구성된 경우 검증된 Microsoft Entra ID 그룹 클레임이 디렉터리 기반 접근 정책에 활용될 수 있습니다. Windows Active Directory, OAuth 및 trusted-proxy 배포는 명시적인 검증된 아이덴티티 어댑터를 통해 통합할 수 있으며, Windows AD는 배포별 Kerberos/Negotiate 검증기가 필요하며 기본적으로 활성화되어 있지 않습니다.

uag에는 Agent, LLM, 도구, Context, Memory 및 검색 작업에 대한 선택형, 공급자 중립적 OpenTelemetry 추적 및 측정항목이 포함되어 있습니다. 관찰 가능성은 기본적으로 비활성화되어 있습니다.

로컬 우선 방식이라고 해서 기본적으로 완전한 오프라인 작동이나 모든 도구 실행의 격리가 보장되는 것은 아닙니다. 외부 모델과 연동 서비스 호출은 설정에 따라 달라집니다.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 다국어 번역

- `translate_text`은 `provider=auto`, `provider=deepl` 또는 `provider=google`을 통해 Google Translate 및 공식 DeepL Python 클라이언트를 지원합니다.
- 도구 정의는 영어를 포함한 37개 로케일(총 38개)에서 사용할 수 있으며, 자리 표시자와 기술 식별자가 그대로 유지됩니다.

OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live, Bedrock Nova Sonic을 통한
전이중 음성을 사용할 수 있으며, AEC3 에코 제거와 안전 제한형 실시간 함수 호출을 선택적으로 지원합니다.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## 문서

| 주제 | 문서 |
|---|---|
| 환경 변수 | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| 아키텍처 및 불변식 | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| 저장소 도구 | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT 사용 사례 | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| 커뮤니케이션 도구 | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| 자동 조종 | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / 프록시 | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code 확장 | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| 개발자 가이드 | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| 도구 흐름 | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## 개발 및 기여

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

PR 전 검사를 실행하세요:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

전체 개발 워크플로는 [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)를 참조하세요.

버그 보고, 기능 아이디어, 문서 개선, 번역, 도구, 스킬, 풀 리퀘스트를 환영합니다.
큰 변경을 하기 전에 이슈나 토론을 열어 주세요. [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)를 읽고,
풀 리퀘스트를 제출하기 전에 위 검사를 실행하세요.

## License

Licensed under the [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
