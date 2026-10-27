<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Um agente local. Qualquer modelo. Qualquer ferramenta. Seu ambiente, suas regras.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Discussões</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Traduções</a>
</p>

______________________________________________________________________

**Por que o uag?**

O uag é um agente de IA local-first que conecta o modelo de sua preferência às ferramentas que você realmente usa.
Ele oferece um único runtime extensível para arquivos, navegadores, bases de código, comunicação, APIs de nuvem,
dispositivos IoT, servidores MCP e fluxos de trabalho multiagente.

- **Liberdade de provedores** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek e muito mais.
- **Execução local-first** — o runtime do agente e a execução das ferramentas permanecem na sua máquina; somente as chamadas de API que você escolher saem dela.
- **Uma camada de ferramentas** — as mesmas ferramentas funcionam na CLI, na GUI desktop, na interface web, no VS Code e no A2A.
- **Paralelismo por design** — operações independentes e somente de leitura podem ser executadas simultaneamente.
- **Extensível** — adicione ferramentas, plugins, Agent Skills, servidores MCP e ferramentas baseadas em Rust sem alterar o núcleo.
- **Ciente de segurança** — ações destrutivas, credenciais, controles de dispositivos e gravações na rede oferecem confirmação explícita e controles de política.

> **Em resumo:** o uag é o plano de controle entre seus modelos de IA e seu ambiente real.

> **🧠 Resultados de ferramentas sensíveis ao contexto** — Resultados extensos de ferramentas são mantidos fora do contexto ativo do modelo, sempre que possível. O `uag` os armazena como Artefatos e, em vez disso, passa ao modelo uma pré-visualização limitada com uma referência estável ao `Artifact`. Isso pode reduzir substancialmente o número de tokens de entrada necessários para as rodadas seguintes quando uma ferramenta produz um resultado extenso.
> [Guia detalhado de compactação de contexto](CONTEXT_COMPRESSION.pt_BR.md)

## Início rápido

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Na primeira inicialização, o assistente de configuração é aberto. Ele ajuda a configurar um provedor e armazena as configurações selecionadas
no seu ambiente local.

Para os grupos de recursos comuns:

```bash
python -m pip install "uag[core,providers,tools]"
```

> As integrações de plataforma são opcionais. Instale somente o que seu sistema operacional precisa; consulte

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Interfaces

| Interface | Comando | Melhor para |
|---|---|---|
| **CLI** | `uag` | Trabalho rápido, priorizando o teclado |
| **GUI desktop** | `uagg` | Uma experiência desktop nativa |
| **Interface web** | `uagw` | Acesso pelo navegador |
| **Servidor A2A** | `uaga` | Comunicação entre agentes |
| **VS Code** | Extensão | Explicar, refatorar, corrigir e explorar ferramentas no editor |

Todas as interfaces compartilham a mesma configuração de provedor, registro de ferramentas, regras de segurança e dados de sessão.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## O que você pode criar

Os adaptadores de provedores abrangem runtimes hospedados e locais, incluindo:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Ler, criar, editar, pesquisar, gerar hash, arquivar e inspecionar arquivos
- Revisar alterações do Git, procurar segredos, executar testes, fazer lint, compilar e medir a cobertura
- Navegar por grandes bases de código em Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA e outras linguagens
- Automatizar navegadores com Playwright, incluindo fluxos com várias páginas e downloads

- **MCP** — conecte servidores de ferramentas externos, incluindo serviços com OAuth
- **A2A** — coordene-se com outros agentes e servidores compatíveis
- **Cloud** — acesso às APIs da AWS, Google Cloud e Azure com confirmação para escritas
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams e pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA e UPnP
- **Media** — geração/edição de imagens, transcrição/síntese de áudio, captura de câmera e códigos QR
- **Documents** — análise de PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL e logs

- **SwitchBot** — descoberta na nuvem e via BLE, status, controle, processamento em lote e assinaturas
- **ECHONET Lite** — descubra e controle eletrodomésticos japoneses, incluindo notificações INF
- **Matter** — endpoints, clusters, atributos, histórico de estado, assinaturas e controle
- **BACnet / Modbus TCP / OPC UA** — leituras, escritas, navegação e monitoramento de automação industrial e predial
- **UPnP** — descoberta de dispositivos, status WAN e gerenciamento de mapeamento de portas do roteador

### Onde o uag se encaixa

O uag fica entre pessoas e interfaces, de um lado, e modelos, ferramentas e sistemas do mundo real, do outro.
Ele coordena a conversa, seleciona recursos, aplica regras de segurança e mantém o fluxo de trabalho retomável.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugins, Agent Skills e marketplaces

Transforme o uag em um agente especializado sem fazer fork do núcleo:

- Instale **plugins compatíveis com Claude Code** a partir de um diretório, ZIP, repositório Git, fonte HTTP ou marketplace
- Agrupe skills, subagentes, servidores MCP, hooks, comandos slash, estilos de saída, dependências e canais
- Explore recursos da comunidade no [SkillsMP](https://skillsmp.com) e no [ClawHub](https://clawhub.ai)
- Adicione skills e ferramentas privadas da organização localmente por meio de `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Consulte o [Guia de desenvolvimento de plugins](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **Mais de 200 ferramentas** para arquivos, web, mídia, documentos, código, nuvem, comunicação e IoT
- **Descoberta e carregamento dinâmicos** — use `tool_catalog` para encontrar recursos e `tool_load` para ativá-los somente quando necessário
- **Inteligência de código** — `code_map`, navegadores `idx` específicos por linguagem, revisão de Git, execução de testes, linting, compilação e cobertura
- **Plugins compatíveis com Claude Code**, com skills, agentes, servidores MCP, hooks, comandos e marketplaces
- **Agent Skills** do SkillsMP e do ClawHub
- **Ferramentas Python personalizadas** com `TOOL_SPEC` e `run_tool()`
- **Ferramentas baseadas em Rust** para extensões nativas leves

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Feito para fluxos de trabalho reais

### 🧠 Resultados de ferramentas sensíveis ao contexto

Resultados extensos de ferramentas são mantidos fora do contexto ativo do modelo, sempre que possível. O `uag` os armazena como Artefatos e, em vez disso, passa ao modelo uma pré-visualização limitada com uma referência estável ao `Artifact`. Isso pode reduzir substancialmente o número de tokens de entrada necessários para as rodadas seguintes quando uma ferramenta produz um resultado extenso.

Retome conversas anteriores com `:load <index>`. Os resultados das ferramentas podem ser armazenados em cache, e os provedores podem ser alterados
sem reconstruir o aplicativo.

[Context compression](CONTEXT_COMPRESSION.pt_BR.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Piloto automático

Use `:auto` para trabalhos com várias rodadas e um modelo revisor opcional. Defina um limite de rodadas com `--max-rounds N`.
Pressione **F12** para interromper o piloto automático ou **F12** para interromper a resposta atual.

Operações independentes e somente de leitura são executadas simultaneamente quando isso é seguro. Pesquisas na web, inspeção de arquivos,
análise de repositórios e cargas de trabalho semelhantes podem ser concluídas em paralelo com um pool de workers
configurável (`UAGENT_PARALLEL_WORKERS`). Operações de escrita permanecem serializadas ou exigem confirmação.

Continuidade de sessões, cache de resultados de ferramentas, estado em lote, recuperação após reinicialização, agendamento de DAG
e orquestração multiagente tornam trabalhos complexos retomáveis em vez de limitados a uma única execução.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privado, multilíngue e orientado por políticas

`human_ask` pausa antes de ações sensíveis. Exclusão e substituição de arquivos, comandos de shell, controles de dispositivos,
operações com credenciais e escritas na rede podem ser governados por regras de confirmação e política.

Use o armazenamento de credenciais em vez de colocar segredos de longa duração nos prompts:

A interface web inclui login OIDC usando Authorization Code + PKCE, tokens de ID verificados, sessões no lado do servidor e controles de acesso a projetos/salas. Reivindicações de grupo Microsoft Entra ID verificadas podem alimentar políticas de acesso baseadas em diretório quando configuradas. Implantações do Windows Active Directory, OAuth e trusted-proxy podem ser integradas por meio de adaptadores de identidade verificados explicitamente; o Windows AD requer um verificador Kerberos/Negotiate específico da implantação e não está habilitado por padrão.

uag inclui rastreamento OpenTelemetry opcional e neutro em termos de provedor e métricas para Agent, LLM, ferramenta, Context, Memory e operações de recuperação. A observabilidade está desabilitada por padrão.

Local-first não significa que o UAG funcione totalmente offline nem que todas as ferramentas sejam isoladas por padrão. As chamadas a modelos e serviços externos dependem da configuração.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Tradução multilíngue

- `translate_text` é compatível com Google Translate e com o cliente oficial do DeepL para Python por meio de `provider=auto`, `provider=deepl` ou `provider=google`.
- As definições das ferramentas estão disponíveis em 37 idiomas, além do inglês (38 no total), com os espaços reservados e os identificadores técnicos preservados.

A voz full-duplex está disponível por meio de OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
e Bedrock Nova Sonic, com cancelamento de eco AEC3 opcional e chamadas de funções em tempo real limitadas por segurança.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Documentação

| Tópico | Documentação |
|---|---|
| Variáveis de ambiente | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Arquitetura e invariantes | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Ferramentas do repositório | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Casos de uso de IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Ferramentas de comunicação | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Piloto automático | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| OAuth / Proxy do MCP | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Extensão do VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Guia do desenvolvedor | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Fluxo de ferramentas | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Desenvolvimento e contribuição

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Execute as verificações pré-PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Para o fluxo completo de desenvolvimento, consulte [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Relatórios de bugs, ideias de recursos, melhorias na documentação, traduções, ferramentas, skills e pull requests são bem-vindos.
Abra uma issue ou discussão antes de fazer alterações grandes. Leia o [Guia do desenvolvedor](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
e execute as verificações acima antes de enviar um pull request.

## License

Licensed under the [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
