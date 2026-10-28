<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Os seus modelos de IA. As suas ferramentas. O seu ambiente.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Outros idiomas</a></p>

---

**O UAG é um ambiente de execução de agentes de IA de código aberto, com prioridade à execução local.** Liga o modelo de linguagem à sua escolha às ferramentas e sistemas que utiliza. Permite trabalhar com código, ficheiros, navegadores, serviços e dispositivos numa interface coerente, sem depender de um único fornecedor de modelos.

| **Escolha o seu modelo** | **Ligue ferramentas reais** | **Mantenha o controlo** |
| :--- | :--- | :--- |
| Modelos alojados e locais, incluindo OpenAI, Claude, Gemini, Grok, Bedrock e Ollama | Ficheiros, código, Web, MCP, Agent Skills, plugins, serviços cloud e IoT | Execução local, confirmação humana, armazenamento de credenciais e políticas configuráveis |

> O UAG é **a camada de execução de agentes, não um fornecedor de modelos**. As chamadas a modelos externos e serviços ligados dependem da configuração. A prioridade ao processamento local não implica funcionamento inteiramente offline nem isolamento de todas as ferramentas por predefinição.

## Início rápido
<!-- README-SYNC:quick-start -->

É necessário **Python 3.11 ou mais recente**. Instale o UAG através do [PyPI](https://pypi.org/project/uag/) e inicie a linha de comandos interativa:

~~~bash
python -m pip install --upgrade uag
uag
~~~

No primeiro arranque, o assistente ajuda a escolher um fornecedor e a configurar as credenciais. Também pode utilizar variáveis de ambiente ou o armazenamento de credenciais. Para instalar antecipadamente mais dependências de fornecedores e ferramentas:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Em seguida, experimente os pedidos seguintes:

~~~text
> O que mudou neste repositório Git? Resume os riscos.
> Encontra a documentação mais recente desta biblioteca e explica os passos de migração.
> Analisa estes ficheiros e prepara um relatório conciso.
> :help
~~~

Se está a começar, consulte o guia de instalação para Windows, incluindo Git e ambientes virtuais, e a referência de configuração: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Interfaces
<!-- README-SYNC:interfaces -->

Todas as formas de acesso utilizam o mesmo ambiente de execução de agentes e o mesmo registo de ferramentas.

| Interface | Início | Melhor para |
| :--- | :--- | :--- |
| **CLI** | `uag` | Trabalho no terminal e automação |
| **Desktop** | `uagg` | Conversas numa aplicação nativa |
| **Web** | `uagw` | Conversas e salas no navegador |
| **A2A** | `uaga` | Comunicação entre agentes |
| **VS Code** | [Guia da extensão](VSCODE.md) | Trabalhar junto do código |

As interfaces Desktop e Web precisam de dependências adicionais não incluídas no conjunto inicial `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

O servidor Web pode tentar instalar FastAPI e Uvicorn ao arrancar. A instalação antecipada evita depender dessa instalação automática. Saiba mais: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## O que pode fazer com o UAG
<!-- README-SYNC:capabilities -->

| Capacidade | O que o UAG disponibiliza |
| :--- | :--- |
| **Fluxos independentes do modelo** | Alternar fornecedores locais e alojados com `UAGENT_PROVIDER` sem reescrever ferramentas |
| **Código e ficheiros** | Navegação em repositórios, inspeção Git, análise de código, testes, operações com ficheiros e automação do navegador |
| **Ferramentas extensíveis** | Mais de 200 ferramentas, descoberta dinâmica com `tool_catalog` / `tool_load`, ferramentas próprias em Python e Rust |
| **Agentes ligados** | MCP, A2A, plugins compatíveis com Claude Code, Agent Skills e subagentes |
| **Tarefas prolongadas** | Piloto automático, leituras independentes em paralelo, tarefas agendadas, recuperação e sessões persistentes |
| **Além do terminal** | Serviços cloud e de comunicação, documentos, multimédia, voz em tempo real e protocolos IoT suportados |

### Um único ambiente de execução, muitas integrações
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

**Exemplos de fornecedores suportados** encontram-se abaixo. As definições específicas estão na referência do ambiente.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Personalizar com skills e plugins
<!-- README-SYNC:extensions -->

Alargue o UAG sem alterar o núcleo. Instale Agent Skills através do SkillsMP ou ClawHub, ligue servidores MCP ou carregue plugins compatíveis com Claude Code que incluam ferramentas, skills, agentes e hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

As ferramentas próprias podem disponibilizar `TOOL_SPEC` e `run_tool()`; as ferramentas baseadas em Rust também são suportadas. Consulte os guias: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Concebido para trabalho real
<!-- README-SYNC:workflows -->

### Contexto e memória
<!-- README-SYNC:context-memory -->

Os resultados extensos das ferramentas podem ser guardados como **artefactos**, em vez de sobrecarregarem o contexto ativo do modelo. Mais tarde, o agente recupera a parte relevante com `artifact_read`. Por predefinição, as sessões são guardadas em SQLite, com pesquisa no histórico e revisão explícita da memória.

- [Context compression](CONTEXT_COMPRESSION.pt.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automação e colaboração
<!-- README-SYNC:automation -->

O UAG permite leituras independentes em paralelo, coordenação de vários agentes, recuperação de sessões e piloto automático para tarefas em várias rondas. Inicie-o com `:auto`; prima **F12** para interromper a resposta atual e solicitar a paragem do piloto automático.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Segurança e observabilidade
<!-- README-SYNC:security -->

As operações sensíveis podem exigir confirmação através de `human_ask`. As credenciais podem ser guardadas no gestor do sistema operativo ou num ficheiro cifrado. A interface Web suporta início de sessão OIDC e controlo de acesso, quando configurados. Os rastos e métricas OpenTelemetry são **opcionais**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Estes mecanismos são configuráveis e **não garantem** que toda a execução de ferramentas seja isolada numa sandbox. Consulte os guias de implementação e políticas antes de disponibilizar o UAG a utilizadores ou redes não fiáveis.

### Idiomas, dispositivos e voz
<!-- README-SYNC:languages -->

O UAG inclui recursos para **38 idiomas e variantes regionais** (inglês e 37 traduções), integração opcional de voz bidirecional e ferramentas para SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP e OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Documentação
<!-- README-SYNC:documentation -->

Comece por estes recursos e aprofunde os assuntos conforme necessário:

| Comece aqui | Aprofundar |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Também pode consultar o diretório completo de documentação e as restantes traduções: [Documentation](./) · [Other languages](README.translations.md).

## Desenvolvimento e contributos
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Antes de um pull request que altere **código Python**, execute os testes relevantes e as verificações do projeto:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Consulte as regras de contribuição e o guia de desenvolvimento. São bem-vindos relatos de erros, melhorias da documentação, ferramentas, traduções e pull requests focados: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licença
<!-- README-SYNC:license -->

O UAG é distribuído ao abrigo da licença: [Apache License 2.0](../LICENSE).
