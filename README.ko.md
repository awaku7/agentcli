```
██╗   ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗██╗     ██╗
██║   ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██║     ██║
██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     ██║     ██║
██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝╚══════╝╚═╝
```

# uag (로컬 AI 에이전트)

uag는 로컬 PC에서 **명령 실행**, **파일 조작**, **다양한 데이터 형식**(PDF/PPTX/Excel 등) 읽기를 수행하는 대화형 에이전트입니다. CLI, GUI, Web의 세 가지 인터페이스를 제공합니다.

## 설치

pip를 통해 `uag`를 설치할 수 있습니다:

```bash
pip install uag
```

설치 후 `uag`를 처음 실행하면 환경 변수를 구성하기 위한 **대화형 설정 마법사**가 자동으로 실행됩니다. 구성 및 암호화에 대한 자세한 정보는 **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**를 참조하십시오.

## 주요 특징

- **실용적인 도구 모음**: 로컬 환경에서 즉시 실행 가능한 파일 조작, 웹 검색, 데이터 추출(PDF/PPTX/Excel), 이미지 생성 및 분석 도구를 탑재하고 있습니다.
- **멀티 프로바이더 지원**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Claude / Grok / NVIDIA를 지원합니다.
- **유연한 인터페이스**: 
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: 외부 MCP 도구 서버와의 연동을 지원합니다.
- **세션 연속성**: 프로바이더나 모델을 전환해도 대화 문맥을 유지합니다.
- **Web Inspector**: `playwright_inspector`를 사용하여 브라우저 이동, DOM, 스크린샷을 자동으로 저장합니다.
- **내장 문서**: `uag docs` 명령을 사용하여 상세한 내부 문서를 즉시 확인할 수 있습니다.

## 사용법

### 시작 및 종료
터미널에서 `uag`를 실행하여 시작합니다. 종료하려면 `:exit`를 입력하십시오.

### A2A (Agent2Agent) 서버
기존 인터페이스와 별도로 A2A 호환 HTTP 서버를 실행할 수 있습니다.
```bash
uaga
# 또는 python -m uagent.a2a.server
```

### 유용한 팁 (연속성 및 제어)
- `:tools`: 로드된 도구 목록을 표시합니다.
- `:logs [n]`: 세션 로그를 표시합니다 (`n`으로 항목 수 지정).
- `:load <index>`: 과거 세션을 불러와 대화를 재개합니다.
- `:skills`: 에이전트 스킬(추가 역할 또는 지침)을 선택하고 로드합니다.
- `:shrink [n]`: 기록을 정리하여 마지막 `n`개의 메시지만 남겨 토큰을 절약합니다.

## 설정 및 상세 정보

### 환경 변수 및 설정
상세 설정(API 키, 표시 언어 `UAGENT_LANG`, 기록 압축 설정 등)에 대해서는 **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**를 참조하십시오.
- **설정**: `python -m uagent.setup_cli`를 통해 대화형으로 구성합니다.
- **암호화**: `uag_envsec` 도구를 사용하여 `.env` 파일을 안전하게 암호화할 수 있습니다.

### 개발자 및 국제화
- **개발자 문서**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **로캘 추가**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **다른 언어의 README**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md)
