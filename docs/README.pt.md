<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag – Gateway Universal de IA</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Por que UAG?

**Liberte-se da dependência do fornecedor.** A maioria dos assistentes de IA vincula você a um provedor ou serviço de nuvem específico. UAG é diferente.

- **Executa localmente** em sua máquina. Seus dados permanecem com você (exceto as chamadas de API que você faz).
- **Liberdade de provedor**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... Mais de 15 provedores, todos acessíveis em uma única interface. Alterne entre eles reconfigurando variáveis ​​de ambiente — sem reinstalação, sem migração.
- **131 ferramentas**: E/S de arquivos, pesquisa na web, geração de imagens, Gmail, verificação de dispositivos BLE, integração de servidor MCP — **76 são seguras em paralelo** (até 8 são executadas simultaneamente por meio de pool de threads, configuráveis ​​via `UAGENT_PARALLEL_WORKERS`). Quando o LLM dispara várias chamadas de ferramenta ao mesmo tempo, o uag as paraleliza automaticamente.
- **3 UIs + A2A**: CLI, GUI, Web e protocolo de agente para agente. Mesmo motor, qualquer interface.
- **Pronto para IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — controle seus dispositivos domésticos por meio de IA.
- **Habilidades do agente**: instale habilidades criadas pela comunidade no mercado. Estenda o UAG indefinidamente.

uag é **seu assistente de IA nos seus termos**. Não vinculado a um provedor, não vinculado a uma interface, não vinculado a uma plataforma.

## Início rápido

```bash
pip install uag
uag
```

Na primeira inicialização, o assistente de configuração orienta você na configuração do provedor.
Consulte [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) para todas as variáveis ​​de ambiente.

## Características

### 🧠 Arquitetura Multi-Provedor

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Todos os provedores compartilham o mesmo conjunto de ferramentas e interface. Alterne configurando `UAGENT_PROVIDER` — sem alterações de código, sem instalações separadas.

### ⚡ Execução de ferramenta paralela

Quando o LLM solicita várias ferramentas simultaneamente, o uag as **paraleliza automaticamente**.
76 ferramentas são marcadas como `x_parallel_safe` e são executadas simultaneamente por meio de um `ThreadPoolExecutor` (8 threads por padrão; defina `UAGENT_PARALLEL_WORKERS` para alterar).

**Exemplo**: Pergunte "Verifique o clima nas capitais nórdicas" → LLM dispara `search_web` × 5 países → todas as 5 pesquisas são executadas em paralelo → resultados coletados em um lote.

Ferramentas somente leitura (pesquisa de arquivos, cálculo de hash, listagem de diretórios, tradução, consultas de banco de dados, etc.) são agressivamente paralelizadas.

### 🔄 Continuidade da Sessão

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 Ferramentas

| Categoria | Ferramentas |
|---|---|
| **Operações de arquivo** | ler/escrever/criar/excluir/pesquisar/grep/hash/zip, parse_eml (arquivos .eml) |
| **Web** | fetch_url, search_web, captura de tela, browser_playwright |
| **Mídia** | gerar_imagem, analisar_imagem, img2img, audio_speech, audio_transcribe |
| **Documentos** | Extração de PDF/PPTX/DOCX/RTF/ODT, extração estruturada em Excel |
| **Comunicação** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook — veja [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matéria, UPnP |
| **Ferramentas de desenvolvimento** | git_ops, python_compile, lint_format, run_tests, db_query, **13 navegadores de código-fonte (família idx)** |
| **MCP** | Conecte-se a servidores MCP externos, liste ferramentas, execute |
| **A2A** | Comunicação entre agentes (com outras instâncias UAG ou servidores compatíveis com A2A) |
| **Sistema** | env vars, especificações do sistema, hora, cálculo de data |
| **Navegação de origem** | **13 ferramentas idx** para Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — obtenha um índice de função/classe ou definição específica sem ler o arquivo inteiro |

### 🖥 4 interfaces + extensão de código VS

| Modo | Comando | Finalidade |
|---|---|---|
| **CLI** | `uag` | Operação rápida baseada em terminal |
| **GUI** | `uagg` | UI da área de trabalho via tkinter |
| **Web** | `uagw` | Acesso baseado em navegador |
| **Servidor A2A** | `uaga` | Protocolo Agent2Agent para comunicação multiagente |
| **Código VS** | — | [Extensão](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) com painel de bate-papo, explicação, refatoração, correção de erros e visualização em árvore de ferramentas |

Consulte [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) para obter detalhes sobre a extensão do VS Code — instalação, comandos, atalhos de teclado e configuração.

### 🏠 Controle de dispositivos IoT

- **SwitchBot**: controle de lote na nuvem e verificação/controle BLE
- **ECHONET Lite**: Descubra e controle eletrodomésticos (AC, luzes, aquecedores de água, etc.) na rede local
- **Matéria**: Inspeção somente leitura da topologia do controlador/ponte/dispositivo
- **UPnP**: descoberta de dispositivos e encaminhamento de porta IGD

Consulte [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

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

Consulte [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) para obter a documentação completa.

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

Pressione a tecla `x` para sair do modo piloto automático (consulte [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ Automação do navegador e inspetor da Web

Duas ferramentas complementares baseadas no Dramaturgo:

- **browser_playwright**: Automatize sessões reais do navegador — navegue, clique, preencha formulários, extraia dados, lide com fluxos de várias páginas. Funciona sem cabeça ou com cabeça.
- **playwright_inspector**: Grave transições do navegador, capture instantâneos e capturas de tela do DOM em cada etapa. Útil para depurar interações na web ou auditar alterações de página ao longo do tempo.

### 🔄 Carregamento dinâmico de ferramentas

`tool_catalog` e `tool_load` permitem descobrir e ativar ferramentas em tempo de execução.
Não há necessidade de carregar tudo na inicialização — ative apenas o que você precisa, quando precisar.

### 🌐i18n/L10n

日本語 / Inglês / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / e muito mais.
Defina `UAGENT_LANG` para alternar. Consulte [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) para adicionar uma nova localidade.

As traduções deste README estão disponíveis em [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variáveis ​​de ambiente criptografadas

Armazene chaves e segredos de API em `.env.sec` — um arquivo `.env` criptografado.
Gerencie com `uag_envsec`.

## Configuração e detalhes

- **Variáveis de ambiente**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Assistente de configuração**: `python -m uagent.setup_cli`
- **Env criptografado**: `uag_envsec` — criptografar `.env` como `.env.sec`
- **API de respostas**: defina `UAGENT_RESPONSES=1` para o modo API de respostas (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Habilitado automaticamente para Sakana AI (Fugu).
- **Documentos para desenvolvedores**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Pequenas dicas de LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filosofia do Projeto

uag aspira ser **sua IA, em sua máquina, em seus termos.**

- Sem dependência de SaaS – funciona localmente
- Sem dependência de provedor - mude a qualquer momento
- Sem bloqueio de UI — CLI/GUI/Web/A2A
- Sem dependência de recursos - amplie com ferramentas e habilidades

Uma experiência de agente de IA gratuita, livre de dependência de fornecedor.
