<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Gateway Universal de IA</h1>

<p align="center">
  <b>U</b>universal <b>A</b>I <b>Gateway — Seu ambiente, sua liberdade.
</p>

<p align="center">
  Operações de arquivos / Pesquisa na Web / Geração e análise de imagens / Extração de PDF e Excel / Controle de IoT / Integração MCP<br>
  Mais de 15 provedores / 3 UIs / Execução de ferramentas paralelas / Mercado de habilidades de agente
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Leia isto no seu idioma</a>
</p>

---

## Por que UAG?

**Liberte-se da dependência do fornecedor.** A maioria dos assistentes de IA vincula você a um provedor ou serviço de nuvem específico. UAG é diferente.

- **Executa localmente** em sua máquina. Seus dados permanecem com você (exceto as chamadas de API que você faz).
- **Liberdade de provedor**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... Mais de 15 provedores, todos acessíveis em uma única interface. Alterne entre eles reconfigurando variáveis ​​de ambiente — sem reinstalação, sem migração.
- **111 ferramentas**: E/S de arquivos, pesquisa na Web, geração de imagens, verificação de dispositivos BLE, integração de servidor MCP — e **55 delas são executadas em paralelo**. Quando o LLM dispara múltiplas chamadas de ferramenta ao mesmo tempo, o uag as executa automaticamente por meio de um conjunto de threads.
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

## Recursos

### 🧠 Arquitetura Multi-Provedor

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

Todos os provedores compartilham o mesmo conjunto de ferramentas e interface. Alterne configurando `UAGENT_PROVIDER` — sem alterações de código, sem instalações separadas.

### ⚡ Execução de ferramenta paralela

Quando o LLM solicita várias ferramentas simultaneamente, o uag as **paraleliza automaticamente**.
55 ferramentas são marcadas como `x_parallel_safe` e são executadas simultaneamente por meio de um `ThreadPoolExecutor` de 4 threads.

**Exemplo**: Pergunte "Verifique o clima nas capitais nórdicas" → LLM dispara `search_web` × 5 países → todas as 5 pesquisas são executadas em paralelo → resultados coletados em um lote.

Ferramentas somente leitura (pesquisa de arquivos, cálculo de hash, listagem de diretórios, tradução, consultas de banco de dados, etc.) são agressivamente paralelizadas.

### 🔄 Continuidade da Sessão

- **Trocar de provedor no meio da sessão** com `UAGENT_PROVIDER` — o histórico de conversas é preservado.
- **Recarregue sessões anteriores** com `:load <index>` — continue de onde parou.
- **Cache de resultados da ferramenta** evita a reexecução redundante quando a mesma chamada de ferramenta se repete.

### 🛠 111 Ferramentas

| Categoria | Ferramentas |
|---|---|
| **Operações de arquivo** | ler/escrever/criar/excluir/pesquisar/grep/hash/zip |
| **Web** | fetch_url, search_web, captura de tela, browser_playwright |
| **Mídia** | gerar_imagem, analisar_imagem, img2img, audio_speech, audio_transcribe |
| **Documentos** | Extração de PDF/PPTX/DOCX/RTF/ODT, extração estruturada em Excel |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matéria, UPnP |
| **Ferramentas de desenvolvimento**, ****11 ferramentas idx** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — obtenha um índice de funções/classes ou uma definição específica sem ler o arquivo inteiro** | git_ops, python_compile, lint_format, run_tests, db_query, ****11 ferramentas idx** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — obtenha um índice de funções/classes ou uma definição específica sem ler o arquivo inteiro** |
| **MCP** | Conecte-se a servidores MCP externos, liste ferramentas, execute |
| **A2A** | Comunicação entre agentes (com outras instâncias UAG ou servidores compatíveis com A2A) |
| **Sistema** | env vars, especificações do sistema, hora, cálculo de data |
| **Navegação de código** | **11 ferramentas idx** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — obtenha um índice de funções/classes ou uma definição específica sem ler o arquivo inteiro |

### 🖥 3 Interfaces + A2A

| Modo | Comando | Finalidade |
|---|---|---|
| **CLI** | `uag` | Operação rápida baseada em terminal |
| **GUI** | `uagg` | UI da área de trabalho via tkinter |
| **Web** | `uagw` | Acesso baseado em navegador |
| **Servidor A2A** | `uaga` | Protocolo Agent2Agent para comunicação multiagente |

### 🏠 Controle de dispositivos IoT

- **SwitchBot**: controle de lote na nuvem e verificação/controle BLE
- **ECHONET Lite**: Descubra e controle eletrodomésticos (AC, luzes, aquecedores de água, etc.) na rede local
- **Matéria**: Inspeção somente leitura da topologia do controlador/ponte/dispositivo
- **UPnP**: descoberta de dispositivos e encaminhamento de porta IGD

Consulte [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Mercado de habilidades do agente

`:skills mp_search` para procurar [SkillsMP](https://skillsmp.com) e [ClawHub](https://clawhub.ai) para habilidades da comunidade.
Instale e amplie os recursos do UAG em tempo real.

### 🧩 Gerenciador de estado em lote

O uag pode acompanhar o progresso em tarefas de vários arquivos de longa duração. Quando o LLM processa dezenas de arquivos, `batch_state` persiste a lista de arquivos pendentes, concluídos e com falha no disco. Se a sessão terminar ou uma rodada expirar, a próxima execução será retomada de onde parou – nada será perdido.

### 🛡 Humano no Loop

`human_ask` permite que o LLM faça uma pausa e peça sua confirmação antes de executar operações destrutivas (exclusão de arquivos, substituições, comandos shell). Você permanece no controle.

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

### 🔒 Variáveis de ambiente criptografadas

Armazene chaves e segredos de API em `.env.sec` — um arquivo `.env` criptografado.
Gerencie com `uag_envsec`.

## Configuração e detalhes

- **Variáveis de ambiente**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Assistente de configuração**: `python -m uagent.setup_cli`
- **Env criptografado**: `uag_envsec` — criptografar `.env` como `.env.sec`
- **API de respostas**: defina `UAGENT_RESPONSES=1` para o modo API de respostas (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Documentos para desenvolvedores**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Pequenas dicas de LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filosofia do Projeto

uag aspira ser **sua IA, em sua máquina, em seus termos.**

- Sem dependência de SaaS – funciona localmente
- Sem dependência de provedor - mude a qualquer momento
- Sem bloqueio de UI — CLI/GUI/Web/A2A
- Sem dependência de recursos - amplie com ferramentas e habilidades

Uma experiência de agente de IA gratuita, livre de dependência de fornecedor.