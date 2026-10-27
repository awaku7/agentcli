<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Um agente local. Qualquer modelo. Qualquer ferramenta. O seu ambiente, as suas regras.
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

**Porquê o uag?**

O uag é um agente de IA local-first que liga o modelo que prefere às ferramentas que realmente utiliza.
Oferece-lhe um único runtime extensível para ficheiros, browsers, bases de código, comunicação, APIs de cloud,
dispositivos IoT, servidores MCP e fluxos de trabalho multiagente.

- **Liberdade de fornecedores** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek e muito mais.
- **Execução local-first** — o runtime do agente e a execução das ferramentas permanecem na sua máquina; apenas as chamadas à API que escolher saem dela.
- **Uma camada de ferramentas** — as mesmas ferramentas funcionam na CLI, GUI de desktop, UI web, VS Code e A2A.
- **Paralelismo por conceção** — operações independentes e só de leitura podem ser executadas em simultâneo.
- **Extensível** — adicione ferramentas, plugins, Agent Skills, servidores MCP e ferramentas suportadas por Rust sem alterar o núcleo.
- **Com segurança em mente** — ações destrutivas, credenciais, controlos de dispositivos e escritas na rede suportam confirmação explícita e controlos de políticas.

> **Em resumo:** o uag é o plano de controlo entre os seus modelos de IA e o seu ambiente real.

> **🧠 Resultados de ferramentas sensíveis ao contexto** — Os resultados de ferramentas de grande dimensão são mantidos fora do contexto ativo do modelo, sempre que possível. O uag armazena-os como Artefactos e, em vez disso, transmite ao modelo uma pré-visualização limitada com uma referência estável ao Artifact. Isto pode reduzir substancialmente o número de tokens de entrada necessários para as rondas seguintes quando uma ferramenta produz um resultado extenso.
> [Guia detalhado de compressão de contexto](CONTEXT_COMPRESSION.pt.md)

## Início rápido

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

O primeiro arranque abre o assistente de configuração. Este ajuda a configurar um fornecedor e guarda as definições selecionadas
no seu ambiente local.

Para os grupos de funcionalidades comuns:

```bash
python -m pip install "uag[core,providers,tools]"
```

> As integrações de plataforma são opcionais. Instale apenas aquilo de que o seu sistema operativo necessita; consulte

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Interfaces

| Interface | Comando | Mais indicado para |
|---|---|---|
| **CLI** | `uag` | Trabalho rápido, orientado para o teclado |
| **GUI de desktop** | `uagg` | Uma experiência de desktop nativa |
| **UI web** | `uagw` | Acesso através do browser |
| **Servidor A2A** | `uaga` | Comunicação entre agentes |
| **VS Code** | Extension | Explicar, refatorar, corrigir e explorar ferramentas no editor |

Todas as interfaces partilham a mesma configuração de fornecedores, o registo de ferramentas, as regras de segurança e os dados das sessões.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## O que você pode criar

Os adaptadores de fornecedores abrangem runtimes alojados e locais, incluindo:

- Ler, criar, editar, pesquisar, calcular hashes, arquivar e inspecionar ficheiros
- Rever alterações Git, procurar segredos, executar testes, fazer lint, compilar e medir a cobertura
- Navegar em grandes bases de código Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA e outras
- Automatizar browsers com Playwright, incluindo fluxos de trabalho com várias páginas e transferências

- **MCP** — ligue servidores de ferramentas externos, incluindo serviços com OAuth
- **A2A** — coordene com outros agentes e servidores compatíveis
- **Cloud** — acesso às APIs da AWS, Google Cloud e Azure com confirmação para escritas
- **Comunicação** — Gmail, Bluesky, Discord, Microsoft Teams e pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA e UPnP
- **Multimédia** — geração/edição de imagens, transcrição/síntese de áudio, captura de câmara e códigos QR
- **Documentos** — análise de PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL e registos

- **SwitchBot** — descoberta na Cloud e por BLE, estado, controlo, operações em lote e subscrições
- **ECHONET Lite** — descubra e controle eletrodomésticos japoneses, incluindo notificações INF
- **Matter** — endpoints, clusters, atributos, histórico de estado, subscrições e controlo
- **BACnet / Modbus TCP / OPC UA** — leituras, escritas, navegação e monitorização para automação industrial e predial
- **UPnP** — descoberta de dispositivos, estado WAN e gestão do mapeamento de portas do router

### Onde se enquadra o uag

O uag situa-se entre as pessoas e as interfaces, por um lado, e os modelos, as ferramentas e os sistemas do mundo real, por outro.
Coordena a conversa, seleciona capacidades, aplica regras de segurança e mantém o fluxo de trabalho retomável.

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

Transforme o uag num agente especializado sem criar um fork do núcleo:

- Instale **plugins compatíveis com Claude Code** a partir de um diretório, ZIP, repositório Git, fonte HTTP ou marketplace
- Reúna skills, subagentes, servidores MCP, hooks, comandos slash, estilos de saída, dependências e canais
- Explore capacidades da comunidade no [SkillsMP](https://skillsmp.com) e no [ClawHub](https://clawhub.ai)
- Adicione skills e ferramentas privadas da sua organização localmente através de `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Consulte o [Guia de desenvolvimento de plugins](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **Mais de 200 ferramentas** para ficheiros, web, multimédia, documentos, código, cloud, comunicação e IoT
- **Descoberta e carregamento dinâmicos** — use `tool_catalog` para encontrar capacidades e `tool_load` para as ativar apenas quando necessário
- **Inteligência de código** — `code_map`, navegadores `idx` específicos de cada linguagem, revisão Git, execução de testes, linting, compilação e cobertura
- **Plugins compatíveis com Claude Code** com skills, agentes, servidores MCP, hooks, comandos e marketplaces
- **Agent Skills** do SkillsMP e do ClawHub
- **Ferramentas Python personalizadas** com `TOOL_SPEC` e `run_tool()`
- **Ferramentas suportadas por Rust** para extensões nativas leves

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Criado para fluxos de trabalho reais

### 🧠 Resultados de ferramentas sensíveis ao contexto

Os resultados de ferramentas de grande dimensão são mantidos fora do contexto ativo do modelo, sempre que possível. O uag armazena-os como Artefactos e, em vez disso, transmite ao modelo uma pré-visualização limitada com uma referência estável ao Artifact. Isto pode reduzir substancialmente o número de tokens de entrada necessários para as rondas seguintes quando uma ferramenta produz um resultado extenso.

Retome conversas anteriores com `:load <index>`. Os resultados das ferramentas podem ser colocados em cache e os fornecedores podem ser alterados
sem reconstruir a aplicação.

[Context compression](CONTEXT_COMPRESSION.pt.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Piloto automático

Use `:auto` para trabalho com várias rondas e um modelo revisor opcional. Defina um limite de rondas com `--max-rounds N`.
Prima **F12** para parar o piloto automático ou **F12** para parar a resposta atual.

Operações independentes e só de leitura são executadas em simultâneo quando é seguro. Pesquisas na web, inspeção de ficheiros,
análise de repositórios e cargas de trabalho semelhantes podem ser concluídas em paralelo com um grupo de workers configurável
(`UAGENT_PARALLEL_WORKERS`). As operações de escrita continuam serializadas ou requerem confirmação.

A continuidade de sessões, a colocação em cache dos resultados das ferramentas, o estado de lotes, a recuperação após reinício, o agendamento DAG e
a orquestração multiagente tornam o trabalho complexo retomável em vez de ser executado de uma só vez.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privado, multilingue e consciente das políticas

`human_ask` pausa antes de ações sensíveis. A eliminação e substituição de ficheiros, comandos shell, controlos de dispositivos,
operações com credenciais e escritas na rede podem ser regidas por regras de confirmação e de políticas.

Utilize o armazenamento de credenciais em vez de colocar segredos de longa duração nos prompts:

A interface web inclui início de sessão OIDC usando Authorization Code + PKCE, tokens de ID verificados, sessões no lado do servidor e controlos de acesso a projetos/salas. As declarações de grupo Microsoft Entra ID verificadas podem alimentar políticas de acesso baseadas em diretórios quando configuradas. Implementações de Windows Active Directory, OAuth e trusted-proxy podem ser integradas através de adaptadores de identidade explicitamente verificados; o Windows AD requer um verificador Kerberos/Negotiate específico da implementação e não está ativado por predefinição.

uag inclui rastreamento OpenTelemetry opcional e neutro em termos de provedor e métricas para Agent, LLM, ferramenta, Context, Memory e operações de recuperação. A observabilidade está desabilitada por padrão.

A execução prioritariamente local não significa que o UAG funcione totalmente offline ou que todas as ferramentas estejam isoladas por predefinição. As chamadas a modelos e serviços externos dependem da configuração.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Tradução multilíngue

- `translate_text` suporta o Google Translate e o cliente oficial do DeepL para Python através de `provider=auto`, `provider=deepl` ou `provider=google`.
- As definições das ferramentas estão disponíveis em 37 localizações, além do inglês (38 no total), com os espaços reservados e os identificadores técnicos preservados.

A voz full-duplex está disponível através de OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
e Bedrock Nova Sonic, com cancelamento de eco AEC3 opcional e chamadas de funções em tempo real limitadas por segurança.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Documentação

| Tópico | Documentação |
|---|---|
| Variáveis de ambiente | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Arquitetura e invariantes | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Ferramentas do repositório | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Casos de utilização de IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Ferramentas de comunicação | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Piloto automático | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| OAuth / Proxy MCP | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Extensão VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Guia do programador | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Fluxo das ferramentas | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

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

Para obter o fluxo de desenvolvimento completo, consulte [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

São bem-vindos relatórios de erros, ideias de funcionalidades, melhorias na documentação, traduções, ferramentas, skills e pull requests.
Abra um issue ou uma discussão antes de fazer alterações de grande dimensão. Leia o [Guia do programador](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
e execute as verificações acima antes de submeter um pull request.

## License

Licensed under the [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
