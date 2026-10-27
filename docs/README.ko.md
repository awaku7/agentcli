<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>당신의 AI 모델. 당신의 도구. 당신의 환경.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">다른 언어</a></p>

---

**UAG는 오픈 소스이자 로컬 우선 AI 에이전트 런타임입니다.** 선택한 언어 모델을 실제로 사용하는 도구와 시스템에 연결합니다. 한 가지 모델 공급업체에 워크플로를 종속시키지 않고 일관된 인터페이스에서 코드, 파일, 브라우저, 서비스, 기기를 다룰 수 있습니다.

| **모델 직접 선택** | **실제 도구 연결** | **제어권 유지** |
| :--- | :--- | :--- |
| OpenAI, Claude, Gemini, Grok, Bedrock, Ollama 등의 호스팅 및 로컬 모델 | 파일, 코드, 웹, MCP, Agent Skills, 플러그인, 클라우드 서비스, IoT | 로컬 실행, 사용자 확인, 자격 증명 저장, 설정 가능한 정책 |

> UAG는 **모델 제공업체가 아니라 에이전트 실행 계층**입니다. 외부 모델이나 연동 서비스로 요청을 보내는지는 설정에 따라 달라집니다. 로컬 우선이라는 말은 기본적으로 완전히 오프라인이거나 모든 도구 실행이 격리된다는 뜻이 아닙니다.

## 빠른 시작
<!-- README-SYNC:quick-start -->

**Python 3.11 이상**이 필요합니다. [PyPI](https://pypi.org/project/uag/)에서 설치한 뒤 대화형 CLI를 실행하세요:

~~~bash
python -m pip install --upgrade uag
uag
~~~

처음 시작하면 설정 마법사가 모델 제공업체 선택과 자격 증명 설정을 안내합니다. 환경 변수나 자격 증명 저장소로 설정할 수도 있습니다. 공급업체 및 도구 의존성을 미리 더 많이 설치하려면 다음 명령을 실행하세요:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

다음과 같은 요청을 시도해 보세요:

~~~text
> 이 Git 저장소에서 무엇이 변경됐나요? 위험 요소를 요약해 주세요.
> 이 라이브러리의 최신 문서를 찾아 마이그레이션 단계를 설명해 주세요.
> 이 파일들을 조사해 간결한 보고서를 작성해 주세요.
> :help
~~~

처음 사용한다면 Git과 가상 환경 준비 방법을 포함한 Windows 설치 가이드, 그리고 환경 설정 문서를 읽어 보세요: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## 인터페이스
<!-- README-SYNC:interfaces -->

여러 실행 방식이 동일한 에이전트 런타임과 도구 레지스트리를 공유합니다.

| 인터페이스 | 시작 명령 | 적합한 용도 |
| :--- | :--- | :--- |
| **CLI** | `uag` | 터미널 작업과 자동화 |
| **데스크톱** | `uagg` | 네이티브 앱에서 대화 |
| **웹** | `uagw` | 브라우저 대화와 룸 |
| **A2A** | `uaga` | 에이전트 간 연동 |
| **VS Code** | [확장 안내](VSCODE.md) | 코드 작업과 병행 |

데스크톱과 웹 인터페이스에는 빠른 설치의 `uag[core,providers,tools]`에 포함되지 않은 추가 의존성이 필요합니다:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

웹 서버는 시작 시 FastAPI와 Uvicorn 설치를 시도할 수도 있습니다. 미리 설치하면 런타임 자동 설치에 의존하지 않아도 됩니다. 자세한 정보: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## UAG로 할 수 있는 일
<!-- README-SYNC:capabilities -->

| 기능 | UAG가 제공하는 것 |
| :--- | :--- |
| **모델 독립적인 워크플로** | `UAGENT_PROVIDER`로 로컬·호스팅 제공업체를 전환하며 도구를 다시 작성할 필요 없음 |
| **코드 및 파일 작업** | 저장소 탐색, Git 점검, 린트, 테스트, 파일 작업, 브라우저 자동화 |
| **확장 가능한 도구** | 200개 이상의 도구, `tool_catalog` / `tool_load` 동적 검색, Python·Rust 기반 사용자 정의 도구 |
| **연결된 에이전트** | MCP, A2A, Claude Code 호환 플러그인, Agent Skills, 하위 에이전트 |
| **장시간 작업** | 자동 실행, 독립적인 읽기 작업 병렬 처리, 예약 작업, 재시작 복구, 영구 세션 |
| **터미널 그 이상** | 클라우드와 커뮤니케이션, 문서, 미디어, 실시간 음성, 지원되는 IoT 프로토콜 |

### 하나의 런타임과 다양한 연동
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**지원하는 모델 제공업체 예시**는 아래와 같습니다. 제공업체별 설정은 환경 설정 문서를 참고하세요.

### 스킬과 플러그인으로 확장
<!-- README-SYNC:extensions -->

핵심 코드를 변경하지 않고 UAG를 확장할 수 있습니다. SkillsMP 또는 ClawHub에서 Agent Skills를 설치하거나, MCP 서버를 연결하거나, 도구·스킬·에이전트·훅을 포함한 Claude Code 호환 플러그인을 로드하세요.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

사용자 정의 도구는 `TOOL_SPEC`와 `run_tool()`을 제공할 수 있으며 Rust 기반 도구도 지원합니다. 시작할 때 참고할 문서: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## 실제 업무에 적합한 설계
<!-- README-SYNC:workflows -->

### 컨텍스트와 메모리
<!-- README-SYNC:context-memory -->

큰 도구 결과를 모델의 활성 컨텍스트에 모두 넣는 대신 **아티팩트**로 저장할 수 있습니다. 이후 `artifact_read`로 필요한 부분만 검색합니다. 세션은 기본적으로 SQLite에 저장하며 기록 검색과 명시적인 메모리 검토 기능도 제공됩니다.

- [Context compression](CONTEXT_COMPRESSION.ko.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### 자동화와 협업
<!-- README-SYNC:automation -->

UAG는 독립적인 읽기 작업의 병렬 실행, 다중 에이전트 조정, 세션 복구, 여러 차례에 걸친 작업을 위한 자동 실행을 지원합니다. `:auto`로 시작하고 **F12**를 누르면 현재 응답을 중단하고 자동 실행의 종료를 요청할 수 있습니다.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 보안과 관측 가능성
<!-- README-SYNC:security -->

민감한 작업은 `human_ask` 확인을 요구하도록 설정할 수 있습니다. 자격 증명은 운영체제의 자격 증명 관리자 또는 암호화 파일에 저장할 수 있습니다. 웹 UI는 설정된 OIDC 로그인 및 접근 제어를 지원합니다. OpenTelemetry 추적과 지표 수집은 **선택 사항**입니다.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

이러한 제어 기능은 설정에 따라 달라지며, **모든 도구 실행이 샌드박스에서 격리된다는 보장은 아닙니다**. 신뢰할 수 없는 사용자나 네트워크에 UAG를 노출하기 전 배포 및 정책 지침을 확인하세요.

### 언어, 기기, 음성
<!-- README-SYNC:languages -->

UAG는 **38개 로케일**(영어와 37개 번역)의 언어 리소스, 선택적 전이중 음성 연동, SwitchBot·Matter·ECHONET Lite·BACnet·Modbus TCP·OPC UA 도구를 제공합니다.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## 문서
<!-- README-SYNC:documentation -->

시작할 때 유용한 문서와 더 깊이 알아볼 자료를 확인하세요:

| 여기서 시작 | 자세히 알아보기 |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

문서 디렉터리 전체와 다른 언어 버전도 살펴볼 수 있습니다: [Documentation](./) · [Other languages](README.translations.md).

## 개발 및 기여
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

**Python 코드**를 변경하는 풀 리퀘스트를 제출하기 전에 관련 테스트와 프로젝트 검사를 실행하세요:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

기여 지침과 개발자 가이드는 다음 문서에서 확인할 수 있습니다. 버그 제보, 문서 개선, 도구, 번역, 범위가 명확한 풀 리퀘스트를 환영합니다: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## 라이선스
<!-- README-SYNC:license -->

UAG는 다음 라이선스로 배포됩니다: [Apache License 2.0](../LICENSE).
