<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Gateway Universal de IA</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Seu ambiente, sua liberdade.
</p>

<p align="center">
  Operações de arquivo / Pesquisa na Web / Geração e análise de imagens / Extração de PDF e Excel / Controle de IoT / Integração MCP<br>
  24 providers/3 UIs / Execução de ferramenta paralela / Mercado Agent Skills
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Por que UAG?

**Liberte-se da dependência do fornecedor.** A maioria dos assistentes de IA vincula você a um provedor ou serviço de nuvem específico. UAG é diferente.

- **Executa localmente** em sua máquina. Seus dados permanecem com você (exceto as chamadas de API que você faz).
- **Liberdade de provedor**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 23 provedores, todos acessíveis em uma única interface. Alterne entre eles reconfigurando variáveis ​​de ambiente — sem reinstalação, sem migração.
- **222 ferramentas**: E/S de arquivos, pesquisa na web, geração de imagens, Gmail, verificação de dispositivos BLE, integração de servidor MCP — **130 são seguras em paralelo** (até 8 são executadas simultaneamente por meio de pool de threads, configuráveis ​​via `UAGENT_PARALLEL_WORKERS`). Quando o LLM dispara várias chamadas de ferramenta ao mesmo tempo, o uag as paraleliza automaticamente.
- **3 UIs + A2A**: CLI, GUI, Web e protocolo de agente para agente. Mesmo motor, qualquer interface.
- **Habilidades do agente**: instale habilidades criadas pela comunidade no mercado. Estenda o UAG indefinidamente.

uag é **seu assistente de IA nos seus termos**. Não vinculado a um provedor, não vinculado a uma interface, não vinculado a uma plataforma.

## Início rápido

```bash
pip install uag
uag
```

Na primeira inicialização, o assistente de configuração orienta você na configuração do provedor.
Consulte [docs/ENVIRONMENT.md](ENVIRONMENT.md) para todas as variáveis ​​de ambiente.

## Características

### 🧠 Arquitetura Multi-Provedor

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Todos os provedores compartilham o mesmo conjunto de ferramentas e interface. Alterne configurando `UAGENT_PROVIDER` — sem alterações de código, sem instalações separadas.

### ⚡ Execução de ferramenta paralela

Quando o LLM solicita várias ferramentas simultaneamente, o uag as **paraleliza automaticamente**.
130 ferramentas são marcadas como `x_parallel_safe` e são executadas simultaneamente por meio de um `ThreadPoolExecutor` (8 threads por padrão; defina `UAGENT_PARALLEL_WORKERS` para alterar).

**Exemplo**: Pergunte "Verifique o clima nas capitais nórdicas" → LLM dispara `search_web` × 5 países → todas as 5 pesquisas são executadas em paralelo → resultados coletados em um lote.

Ferramentas somente leitura (pesquisa de arquivos, cálculo de hash, listagem de diretórios, tradução, consultas de banco de dados, etc.) são agressivamente paralelizadas.

### 🧩 Sistema de plug-ins (compatível com Claude Code)

uagent implementa um **sistema de plug-ins compatível com Claude Code**. Os plug-ins agrupam habilidades, agentes, servidores MCP, ganchos e muito mais em diretórios independentes com o manifesto `.claude-plugin/plugin.json`.

**Componentes suportados**: habilidades, subagentes, servidores MCP, ganchos (12 eventos de ciclo de vida), comandos de barra, estilos de saída, userConfig, dependências, canais, mercados

**CLI commands**:

```
:plugin list                         # Listar plug-ins instalados
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Instalar do mercado
:plugin remove <name>                # Desinstalar
:plugin enable/disable <name>        # Alternar
:plugin marketplace add/remove/list  # Gerenciar mercados
:plugin init <name>                  # Criar a estrutura de um novo plug-in
```

Consulte a documentação completa em [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md).

### 🔄 Continuidade da Sessão

- **Trocar de provedor durante a sessão**: `UAGENT_PROVIDER` — o histórico de conversas é preservado.
- **Recarregar sessões anteriores**: `:load <index>` — continue de onde parou.

### 🛠 222 Ferramentas

| Categoria | Ferramentas |
|---|---|
| **Operações de arquivo** | ler/escrever/criar/excluir/pesquisar/grep/hash/zip, file_type, parse_eml (arquivos .eml) |
| **Web** | fetch_url, search_web, captura de tela, browser_playwright |
| **Mídia** | gerar_imagem, analisar_imagem, img2img, audio_speech, audio_transcribe |
| **Documentos** | Extração de PDF/PPTX/DOCX/RTF/ODT, extração estruturada em Excel |
| **Previsão** | Previsão de séries temporais com 9 modelos (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), seleção automática de modelo, geração de gráficos, i18n |
| **Comunicação** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook , **pybitchat** (BLE Mesh) — veja [COMMUNICATION.md](COMMUNICATION.md) and [BITCHAT.md](BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **APIs de nuvem** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Ferramentas de desenvolvimento** | git_ops, python_compile, lint_format, run_tests, db_query, **29 navegadores de código-fonte (família idx)** |
| **MCP** | Conecte-se a servidores MCP externos, liste ferramentas, execute — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Comunicação entre agentes (com outras instâncias UAG ou servidores compatíveis com A2A) |
| **Sistema** | env vars, especificações do sistema, hora, cálculo de data, uuid_gen, slugify, quantities ||
| **Navegação de origem** | **29 ferramentas idx** para Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — obtenha um índice de função/classe ou definição específica sem ler o arquivo inteiro |

#### Revisão e cobertura do repositório

- `git_review`: resume alterações do Git, arquivos arriscados, candidatos de teste e descobertas secretas sem expor valores secretos.
- `security_scan`: verifica os arquivos do repositório em busca de segredos prováveis e arquivos de configuração arriscados.
- `coverage_report`: executa e normaliza a cobertura para Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift e Dart/Flutter.
- Dependências de cobertura ausentes podem ser instaladas automaticamente quando a execução é solicitada; `dry_run` nunca instala pacotes.

Veja [Ferramentas de análise de repositório](REPOSITORY_TOOLS.md) para parâmetros, saída e detalhes de segurança.

### 🖥 4 interfaces + extensão de código VS

| Modo | Comando | Finalidade |
|---|---|---|
| **CLI** | `uag` | Operação rápida baseada em terminal |
| **GUI** | `uagg` | UI da área de trabalho via tkinter |
| **Web** | `uagw` | Acesso baseado em navegador |
| **Servidor A2A** | `uaga` | Protocolo Agent2Agent para comunicação multiagente |
| **Código VS** | — | [Extensão](VSCODE.md) com painel de bate-papo, explicação, refatoração, correção de erros e visualização em árvore de ferramentas |

Consulte [VSCODE.md](VSCODE.md) para obter detalhes sobre a extensão do VS Code — instalação, comandos, atalhos de teclado e configuração.

### 🏠 Controle de dispositivos IoT

- **Matéria**: Inspeção somente leitura da topologia do controlador/ponte/dispositivo

Consulte [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Mercado de habilidades do agente

`:skills mp_search` para procurar [SkillsMP](https://skillsmp.com) e [ClawHub](https://clawhub.ai) para habilidades da comunidade.
Instale e amplie os recursos do UAG em tempo real.

### 🤖 Piloto Automático (`:auto`)

uag pode **perseguir uma meta de forma autônoma em várias rodadas de LLM**. Perfeito para tarefas complexas e de várias etapas que precisam de refinamento iterativo.

- **Como funciona**: Cada rodada tem uma consulta principal (Etapa A) seguida por um julgamento do revisor (Etapa B) que decide "CONCLUIR ou CONTINUAR?"
- **Mesmo provedor, mesma API**: o julgamento do revisor usa o caminho de código idêntico à consulta principal, incluindo suporte à API de respostas.
- **Juiz separado LLM** (opcional): Defina `UAGENT_AP_PROVIDER` para usar um provedor/modelo diferente para o revisor (por exemplo, use um modelo mais barato para julgar).
- **Sair a qualquer momento**: Pressione a tecla `x` para parar imediatamente, mesmo no meio da resposta. Ou deixe o revisor decidir quando a meta será alcançada.
- **Configurável**: `--max-rounds N` para controlar o orçamento.

Consulte [README_AUTO.md](README_AUTO.md) para obter a documentação completa.

### 🧩 Gerenciador de estado em lote

O uag pode acompanhar o progresso em tarefas de vários arquivos de longa duração. Quando o LLM processa dezenas de arquivos, `batch_state` persiste a lista de arquivos pendentes, concluídos e com falha no disco. Se a sessão terminar ou uma rodada expirar, a próxima execução será retomada de onde parou – nada será perdido.

### 🛡 Humano no Loop

`human_ask` permite que o LLM faça uma pausa e peça sua confirmação antes de executar operações destrutivas (exclusão de arquivos, substituições, comandos shell). Você permanece no controle.

### 🛑 Interromper (tecla c / botão Parar)

Pare a geração de resposta do LLM a qualquer momento e injete um comando de parada de volta ao LLM.

| Interface | Como interromper |
|---|---|
| **CLI** | Pressione a tecla `c` durante o streaming do LLM - a resposta atual é interrompida e `"Stop"` é enviado como uma mensagem do usuário para que o LLM responda adequadamente |
| **IU da WEB** | Clique no botão vermelho **■ Parar** (aparece automaticamente durante o processamento do LLM) |
| **GUI da área de trabalho** | Clique no botão vermelho **■** (aparece automaticamente durante o processamento do LLM) |

A interrupção funciona como uma "injeção de prompt": em vez de apenas abortar, ela envia `"Stop"` de volta ao LLM como uma mensagem do usuário, permitindo que ele conclua ou reconheça a interrupção normalmente.

Pressione a tecla `x` para sair do modo piloto automático (consulte [README_AUTO.md](README_AUTO.md)).

### 🕵️ Automação do navegador e inspetor da Web

Duas ferramentas complementares baseadas no Dramaturgo:

- **browser_playwright**: Automatize sessões reais do navegador — navegue, clique, preencha formulários, extraia dados, lide com fluxos de várias páginas. Funciona sem cabeça ou com cabeça.
- **playwright_inspector**: Grave transições do navegador, capture instantâneos e capturas de tela do DOM em cada etapa. Útil para depurar interações na web ou auditar alterações de páginas ao longo do tempo.

### 🔄 Carregamento dinâmico de ferramentas

`tool_catalog` e `tool_load` permitem descobrir e ativar ferramentas em tempo de execução.
Não há necessidade de carregar tudo na inicialização — ative apenas o que você precisa, quando precisar.

### 🦀 Rust Native Tools

### 🌐i18n/L10n

日本語 / Inglês / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / e muito mais.
Defina `UAGENT_LANG` para alternar. Consulte [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) para adicionar uma nova localidade.

As traduções deste README estão disponíveis em [docs/README.translations.md](README.translations.md).

### 🔒 Variáveis ​​de ambiente criptografadas

Armazene chaves e segredos de API em `.env.sec` — um arquivo `.env` criptografado.
Gerencie com `uag_envsec`.

## Configuração e detalhes

- **Variáveis de ambiente**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Assistente de configuração**: `python -m uagent.setup_cli`
- **Env criptografado**: `uag_envsec` — criptografar `.env` como `.env.sec`
- **API de respostas**: defina `UAGENT_RESPONSES=1` para o modo API de respostas (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Habilitado automaticamente para Sakana AI (Fugu).
- **Documentos para desenvolvedores**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Pequenas dicas de LLM**: [SLM_TIPS.md](SLM_TIPS.md)

## Filosofia do Projeto

uag aspira ser **sua IA, em sua máquina, em seus termos.**

- Sem dependência de SaaS – funciona localmente
- Sem dependência de provedor - mude a qualquer momento
- Sem bloqueio de UI — CLI/GUI/Web/A2A
- Sem dependência de recursos - amplie com ferramentas e habilidades

Uma experiência de agente de IA gratuita, livre de dependência de fornecedor.

### ✨ Crie suas próprias ferramentas

[pt_BR.md](TOOL_CREATOR_GUIDE.pt_BR.md)

## Contribuir

Contribuições são bem-vindas! Relatórios de bugs, sugestões de recursos, melhorias na documentação, traduções e solicitações pull – tudo apreciado.

- **Issues**: Abra um problema GitHub para bugs ou solicitações de recursos.
- **Pull requests**: Faça um fork do repositório, aplique suas alterações e envie um PR. Consulte [DEVELOP.md](../src/uagent/docs/DEVELOP.md) para a configuração de desenvolvimento e as diretrizes.

Realtime Voz e AEC3

## Realtime O modo de voz suporta microfone full-duplex e entrada/saída de alto-falante. Se o backend AEC3 estiver faltando, uag instalará automaticamente pywebrtc-audio.

**Provedores em tempo real**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice e Amazon Bedrock Nova Sonic. O SDK de streaming bidirecional do Bedrock é instalado automaticamente somente quando o Bedrock é selecionado.

```bat
python scheck.py realtime
```

AEC3 usa o sinal real do microfone (próximo) e o áudio realmente enviado ao alto-falante (distante). Ative o diagnóstico somente ao investigar problemas de áudio.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime oferece suporte a uma integração Function Calling com segurança limitada. O adaptador atual expõe a função get_current_time somente leitura automaticamente. Ferramentas destrutivas e controles de dispositivos exigem uma lista de permissões explícita e um fluxo de confirmação. Grok em tempo real usa um adaptador separado e não usa esse caminho Function Calling específico de OpenAI.
