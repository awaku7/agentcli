<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (로컬 AI 에이전트)

uag는 로컬 PC에서 **명령 실행**, **파일 조작**, **다양한 데이터 형식**(PDF/PPTX/Excel 등) 읽기를 수행하는 대화형 에이전트입니다. CLI, GUI, Web의 세 가지 인터페이스를 제공합니다.

uag는 **벤더에 종속된 앱에서 벗어날 수 있도록** 설계되었습니다. 작업 흐름에 맞는 인터페이스를 사용하고, 제공자를 바꾸며, 환경을 직접 제어하세요.

GitHub: https://github.com/awaku7/agentcli

## 설치

pip를 통해 `uag`를 설치할 수 있습니다:

```bash
pip install uag
```

설치 후 `uag`를 처음 실행하면 환경 변수를 구성하기 위한 **대화형 설정 마법사**가 자동으로 실행됩니다. 구성 및 암호화에 대한 자세한 정보는 \*\*[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)\*\*를 참조하십시오.

## 주요 특징

- **실용적인 도구 모음**: 로컬 환경에서 즉시 실행 가능한 파일 조작, 웹 검색, 데이터 추출(PDF/PPTX/Excel), 이미지 생성 및 분석 도구를 탑재하고 있습니다.
- **멀티 프로바이더 지원**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI 를 지원합니다.
- **유연한 인터페이스**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: 외부 MCP 도구 서버와의 연동을 지원합니다.
- **세션 연속성**: 프로바이더나 모델을 전환해도 대화 문맥을 유지합니다.
- **Web Inspector**: `playwright_inspector`를 사용하여 브라우저 이동, DOM, 스크린샷을 자동으로 저장합니다.
- **내장 문서**: `uag docs` 명령을 사용하여 상세한 내부 문서를 즉시 확인할 수 있습니다.
- **IoT device support**: Control SwitchBot, ECHONET Lite, Matter, and UPnP devices. See [IOT_USECASE.md](IOT_USECASE.md).

## 사용법

## IoT Device Support

Control smart home and IoT devices through multiple interfaces:

- **SwitchBot Cloud**: List, control, and batch-operate SwitchBot devices (TV, air conditioner, lights, etc.).
  - Infrared remote devices (on/off, brightness, temperature)
  - Air conditioner mode and fan speed control
  - Batch execution of multiple commands
- **SwitchBot BLE**: Scan and control nearby SwitchBot BLE devices.
- **ECHONET Lite**: Discover and control ECHONET Lite home appliances over the local network.
- **Matter**: Inspect Matter controller/bridge/device structure (read-only).
- **UPnP**: Discover UPnP devices and manage IGD port forwarding.

For detailed usage, see [IOT_USECASE.md](IOT_USECASE.md).

### 시작 및 종료

터미널에서 `uag`를 실행하여 시작합니다. 종료하려면 `:exit`를 입력하십시오.

### A2A (Agent2Agent) 서버

기존 인터페이스와 별도로 A2A 호환 HTTP 서버를 실행할 수 있습니다.

```bash
uaga
# 또는 python -m uagent.a2a.server
```

### Responses API 참고

`UAGENT_RESPONSES=1`을 설정하면 지원되는 제공자에 대해 Responses API가 사용됩니다: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI는 자체 API 경로를 사용하며 Responses API 대상이 아닙니다.
그 외의 제공자에 대해서는 uag가 제공자별 경로 또는 chat-completions 경로로 돌아갑니다.

인증, 호스트, 포트, 리로드, 공개 기본 URL, 동시 실행 수, 엔진 등의 `UAGENT_A2A_*` 설정은 [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)를 참조하세요.

### 유용한 팁 (연속성 및 제어)

- `:tools`: 로드된 도구 목록을 표시합니다.
- `:logs [n]`: 세션 로그를 표시합니다 (`n`으로 항목 수 지정).
- `:load <index>`: 과거 세션을 불러와 대화를 재개합니다.
- `:skills`: 에이전트 스킬(추가 역할 또는 지침)을 선택하고 로드합니다.
- `:shrink [n]`: 기록을 정리하여 마지막 `n`개의 메시지만 남겨 토큰을 절약합니다.

## 설정 및 상세 정보

### 환경 변수 및 설정

상세 설정(API 키, 표시 언어 `UAGENT_LANG`, 기록 압축 설정 등)에 대해서는 \*\*[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)\*\*를 참조하십시오.

- **설정**: `python -m uagent.setup_cli`를 통해 대화형으로 구성합니다.
- **암호화**: `uag_envsec` 도구를 사용하여 `.env` 파일을 안전하게 암호화할 수 있습니다.
- **업데이트**: 기존 `.env.sec` 파일에 변수를 추가하거나 업데이트하려면 `uag_envsec add --file .env.sec --key NAME --value VALUE`를 사용하세요.

### 개발자 및 국제화

- **개발자 문서**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **로캘 추가**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **다른 언어의 README**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
