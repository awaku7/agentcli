<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Seus modelos de IA. Suas ferramentas. Seu ambiente.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Outros idiomas</a></p>

---

**O UAG é um ambiente de execução de agentes de IA de código aberto que prioriza a operação local.** Ele conecta o modelo de linguagem escolhido às ferramentas e aos sistemas que você usa. Trabalhe com código, arquivos, navegadores, serviços e dispositivos por meio de uma interface consistente, sem ficar preso a um único provedor de modelos.

| **Escolha seu modelo** | **Conecte ferramentas reais** | **Mantenha o controle** |
| :--- | :--- | :--- |
| Modelos hospedados ou locais, como OpenAI, Claude, Gemini, Grok, Bedrock e Ollama | Arquivos, código, web, MCP, Agent Skills, plugins, serviços em nuvem e IoT | Execução local, confirmação humana, armazenamento de credenciais e políticas configuráveis |

> O UAG é **a camada de execução de agentes, não um provedor de modelos**. Chamadas a modelos externos e serviços conectados dependem da configuração escolhida. Priorizar o ambiente local não significa operar totalmente offline ou executar todas as ferramentas em isolamento por padrão.

## Início rápido
<!-- README-SYNC:quick-start -->

É necessário ter **Python 3.11 ou superior**. Instale o UAG pelo [PyPI](https://pypi.org/project/uag/) e inicie a interface de linha de comando:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Na primeira execução, o assistente ajuda você a selecionar um provedor e configurar as credenciais. Também é possível usar variáveis de ambiente ou o armazenamento de credenciais. Para instalar antecipadamente um conjunto maior de dependências de modelos e ferramentas:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Depois, experimente estas solicitações:

~~~text
> O que mudou neste repositório Git? Resuma os riscos.
> Encontre a documentação mais recente desta biblioteca e explique os passos da migração.
> Inspecione estes arquivos e produza um relatório conciso.
> :help
~~~

Para começar, veja o guia de instalação no Windows, incluindo Git e ambientes virtuais, e a referência de configuração: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Interfaces
<!-- README-SYNC:interfaces -->

Os diferentes pontos de entrada usam o mesmo mecanismo de agentes e o mesmo registro de ferramentas.

| Interface | Inicialização | Indicada para |
| :--- | :--- | :--- |
| **CLI** | `uag` | Trabalho no terminal e automação |
| **Desktop** | `uagg` | Conversas em aplicativo nativo |
| **Web** | `uagw` | Conversas e salas no navegador |
| **A2A** | `uaga` | Comunicação entre agentes |
| **VS Code** | [Guia da extensão](VSCODE.md) | Trabalho ao lado do código |

As interfaces Desktop e Web exigem dependências extras que não fazem parte de `uag[core,providers,tools]` da instalação inicial:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

O servidor Web também pode tentar instalar FastAPI e Uvicorn ao iniciar. A instalação prévia evita depender dessa instalação automática. Saiba mais: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## O que você pode fazer com o UAG
<!-- README-SYNC:capabilities -->

| Capacidade | O que o UAG oferece |
| :--- | :--- |
| **Fluxos independentes de modelo** | Alternar entre provedores locais e hospedados com `UAGENT_PROVIDER` sem reescrever ferramentas |
| **Código e arquivos** | Navegação em repositórios, inspeção do Git, lint, testes, operações em arquivos e automação do navegador |
| **Ferramentas extensíveis** | Mais de 200 ferramentas, descoberta dinâmica com `tool_catalog` / `tool_load`, ferramentas personalizadas em Python e Rust |
| **Agentes conectados** | Servidores MCP, A2A, plugins compatíveis com Claude Code, Agent Skills e subagentes |
| **Tarefas prolongadas** | Piloto automático, leituras independentes em paralelo, tarefas agendadas, recuperação e sessões persistentes |
| **Além do terminal** | Integrações com nuvem e comunicação, documentos, mídia, voz em tempo real e protocolos IoT compatíveis |

### Um único ambiente para muitas integrações
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

**Exemplos de provedores compatíveis:** veja a lista abaixo. As configurações específicas estão na referência do ambiente.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Personalize com skills e plugins
<!-- README-SYNC:extensions -->

Amplie o UAG sem modificar o núcleo. Instale Agent Skills pelo SkillsMP ou ClawHub, conecte servidores MCP ou carregue plugins compatíveis com Claude Code que incluam ferramentas, skills, agentes e hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Ferramentas personalizadas podem expor `TOOL_SPEC` e `run_tool()`; ferramentas implementadas com Rust também são suportadas. Consulte os guias: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Feito para trabalhos reais
<!-- README-SYNC:workflows -->

### Contexto e memória
<!-- README-SYNC:context-memory -->

Resultados grandes de ferramentas podem ser salvos como **artefatos**, em vez de sobrecarregar o contexto ativo do modelo. O agente pode recuperar posteriormente apenas o trecho necessário com `artifact_read`. As sessões são armazenadas em SQLite por padrão, com pesquisa de histórico e revisão explícita de memória.

- [Context compression](CONTEXT_COMPRESSION.pt_BR.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automação e colaboração
<!-- README-SYNC:automation -->

O UAG oferece execução paralela de leituras independentes, coordenação entre agentes, recuperação de sessões e piloto automático para tarefas em várias rodadas. Inicie com `:auto`; pressione **F12** para interromper a resposta atual e solicitar a parada do piloto automático.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Segurança e observabilidade
<!-- README-SYNC:security -->

Operações sensíveis podem exigir confirmação por `human_ask`. As credenciais podem ficar no gerenciador nativo do sistema operacional ou em arquivos criptografados. A interface Web oferece autenticação OIDC e controles de acesso quando configurados. Rastreamento e métricas do OpenTelemetry são **opcionais**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Esses controles são configuráveis e **não garantem** que qualquer execução de ferramenta esteja isolada em sandbox. Consulte os guias de implantação e políticas antes de disponibilizar o UAG a usuários ou redes não confiáveis.

### Idiomas, dispositivos e voz
<!-- README-SYNC:languages -->

O UAG oferece recursos para **38 localidades** (inglês e 37 traduções), integrações opcionais de voz bidirecional e ferramentas para SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP e OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Documentação
<!-- README-SYNC:documentation -->

Comece pelos materiais abaixo e aprofunde-se conforme a necessidade:

| Comece aqui | Aprofunde-se |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Explore também o diretório de documentação e as traduções: [Documentation](./) · [Other languages](README.translations.md).

## Desenvolvimento e contribuições
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Antes de um pull request com alterações em **código Python**, execute os testes relevantes e as verificações do projeto:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Leia as normas de contribuição e o guia de desenvolvimento. Relatórios de erros, melhorias na documentação, traduções, ferramentas e pull requests específicos são bem-vindos: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licença
<!-- README-SYNC:license -->

O UAG é disponibilizado sob a licença: [Apache License 2.0](../LICENSE).
