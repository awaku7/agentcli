<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
 <b>U</b>U</b>I <b>Gateway</b>universal — Seu ambiente, sua liberdade.
</p>

<p align="center">
 Operações de arquivo / Pesquisa na Web / Geração e análise de imagens / Extração de PDF e Excel / Controle de IoT / Integração MCP<br>
 24 provedores / 3 UIs / Execução de ferramentas paralelas / Habilidades do agente mercado
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Leia isto no seu idioma</a>
</p>

______________________________________________________________________

## Por que uag?

**Liberte-se da dependência de um fornecedor.** A maioria dos assistentes de IA vincula você a um provedor ou serviço de nuvem específico. uag é diferente.

- **Executa localmente** em sua máquina. Seus dados permanecem com você (exceto API chamadas que você faz).
- **Liberdade de provedor**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 provedores, todos acessíveis em uma única interface. Troque entre eles reconfigurando variáveis ​​de ambiente — sem reinstalação, sem migração.
- **222 ferramentas**: E/S de arquivos, pesquisa na web, geração de imagens, Gmail, verificação de dispositivos BLE, integração de servidor MCP — **130 são marcadas estaticamente como seguras para paralelo** (até 8 são executadas simultaneamente por meio de pool de threads, configuráveis ​​via `UAGENT_PARALLEL_WORKERS`). Quando o LLM dispara várias chamadas de ferramenta ao mesmo tempo, o uag as paraleliza automaticamente.
- **3 UIs + A2A**: CLI, GUI, Web e protocolo de agente para agente. O mesmo mecanismo, qualquer interface.
- **Pronto para IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — controle seus dispositivos domésticos por meio de IA.
- **Habilidades do agente**: instale habilidades criadas pela comunidade no mercado. Estenda uag indefinidamente.

uag é **seu assistente de IA nos seus termos**. Não vinculado a um provedor, não vinculado a uma interface, não vinculado a uma plataforma.

## Início rápido

```bash
pip install uag
uag
```

Na primeira inicialização, o assistente de configuração orienta você na configuração do provedor.
Consulte [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) para todos os ambientes variáveis.

## Uso do computador

O uso do computador é opcional e suporta um tempo de execução de navegador Playwright visível
e um tempo de execução de desktop. Quando ativado, ambos os tempos de execução são criados e registrados;

```bat
set UAGENT_COMPUTER_USE=1
```

Use `desktop` para selecionar o tempo de execução da área de trabalho do sistema operacional. Os recursos de tempo de execução são fechados juntos na saída normal, `Ctrl-C` e no encerramento do processo. Defina
`UAGENT_COMPUTER_HEADLESS=1` para CI baseado em navegador ou testes de fumaça.
Consulte [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
para obter detalhes de integração e segurança.

## Voz em tempo real e AEC3

O modo de voz em tempo real suporta OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API e Amazon Bedrock Nova Sonic com microfone full-duplex e E/S de alto-falante. O back-end `pywebrtc-audio` AEC3 necessário é instalado automaticamente, e o SDK de streaming bidirecional opcional do Bedrock é instalado automaticamente somente quando o provedor Bedrock é selecionado:

```bash
python scheck.py realtime
```

O pipeline AEC3 recebe o sinal real do microfone (`near`) e o áudio realmente entregue ao alto-falante (`far`) para que o assistente possa ouvir enquanto falando. Habilite o diagnóstico apenas ao investigar problemas de áudio:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Chamada de função em tempo real

OpenAI O tempo real oferece suporte a uma integração de chamada de função com segurança limitada. O adaptador em tempo real atual expõe `get_current_time` somente leitura automaticamente. Ferramentas destrutivas e controles de dispositivos não são expostos sem uma lista de permissões explícita e um fluxo de confirmação. Grok em tempo real usa um adaptador separado e não usa este caminho de chamada de função específico de OpenAI.

## Recursos

### 🧠 Arquitetura multi-provedor

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway
Todos os provedores compartilham o mesmo conjunto de ferramentas e interface. Alterne configurando `UAGENT_PROVIDER` - sem alterações de código, sem instalações separadas.

#### Ollama e llama.cpp

Ollama e llama.cpp são provedores separados. Ollama usa seu próprio serviço e gerenciamento de modelo, enquanto `llama.cpp` se conecta a um endpoint compatível com `llama-server` OpenAI:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

O provedor llama.cpp usa o caminho compatível com as conclusões de bate-papo. Mantenha `UAGENT_RESPONSES=0` a menos que um proxy compatível esteja configurado.

### ⚡ Execução de ferramenta paralela

Quando o LLM solicita múltiplas ferramentas simultaneamente, uag **paraleliza automaticamente** elas.
130 ferramentas são marcadas estaticamente como `x_parallel_safe` e são executadas simultaneamente por meio de um `ThreadPoolExecutor` (8 threads por padrão; definido `UAGENT_PARALLEL_WORKERS` para alterar).
**Exemplo**: Pergunte "Verifique o clima nas capitais nórdicas" → LLM dispara `search_web` × 5 países → todas as 5 pesquisas são executadas em paralelo → resultados coletados em um lote.
A contagem atual é baseada em módulos de ferramentas que definem um `TOOL_SPEC` (atualmente 222, incluindo as 2 ferramentas suportadas por Rust em `src/uagent/tools_rust/`). `http_request` usa segurança sensível ao método: chamadas `GET`/`HEAD`/`OPTIONS` podem ser executadas em paralelo, enquanto os métodos de gravação permanecem seriais.
Ferramentas somente leitura (pesquisa de arquivos, cálculo de hash, listagem de diretórios, tradução, consultas de banco de dados, etc.) são agressivamente paralelizadas.

### 🧩 Sistema de plug-ins (compatível com código Claude)

uagent implementa um **sistema de plug-ins compatível com código Claude**. Os plug-ins agrupam habilidades, agentes, servidores MCP, ganchos e muito mais em diretórios independentes com um manifesto `.claude-plugin/plugin.json`.
**Componentes suportados**: habilidades, subagentes, servidores MCP, ganchos (12 eventos de ciclo de vida), comandos Slash, estilos de saída, userConfig, dependências, canais, mercados
**CLI comandos**:

```
:plugin list # Lista plugins instalados
:plugin install <fonte> [--scope] # Instalar (dir/zip/git/http)
:plugin install <nome>@<marketplace> # Instalar do marketplace
:plugin remove <nome> # Desinstalar
:plugin ativar/desativar <nome> # Alternar
:plugin marketplace adicionar/remover/lista # Gerenciar marketplaces
:plugin init <nome> # Scaffold new plugin
```

Veja [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) para obter a documentação completa.

### 🔄 Continuidade da sessão

- **Alternar de provedor no meio da sessão** com `UAGENT_PROVIDER` — o histórico da conversa é preservado.
- **Recarregue sessões anteriores** com `:load <index>` — continue de onde parou.
- **O armazenamento em cache dos resultados da ferramenta** evita a reexecução redundante quando a mesma chamada de ferramenta se repete.

### 🛠 229 Ferramentas

| Categoria | Ferramentas |
|---|---|
| **Operações de arquivo** | leitura/gravação/criação/exclusão/pesquisa/grep/hash/zip, tipo de arquivo, parse_eml (arquivos .eml), `path_alias` |
| **Web** | fetch_url, search_web, captura de tela, browser_playwright, `url_alias`, `public_transit_route` ([guia](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Mídia** | gerar_imagem, analisar_imagem, img2img, audio_speech, audio_transcribe |
| **Documentos** | Extração de PDF/PPTX/DOCX/RTF/ODT, extração estruturada em Excel |
| **Previsão** | Previsão de série temporal com 9 modelos (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), seleção automática de modelo, geração de gráficos, i18n |
| **Comunicação** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook, **pybitchat** (BLE Mesh) — consulte [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) e [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matéria, UPnP, reverse_geocode |
| **APIs de nuvem** | `aws_api`, `gcp_api`, `azure_api` — operações genéricas AWS, Google Cloud e Azure API; operações de gravação requerem confirmação explícita |
| **Ferramentas de desenvolvimento** | workspace_status, git_ops, git_review, security_scan, cobertura_report, python_compile, lint_format, run_tests, db_query, **29 navegadores de código fonte (família idx)** |
| **MCP** | Conecte-se a servidores MCP externos, liste ferramentas, execute — [Guia OAuth / Proxy](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Comunicação entre agentes (com outras instâncias uag ou servidores compatíveis com A2A) |
| **Sistema** | env vars, especificações do sistema, hora, cálculo de data, [quantidades](docs/QUANTITIES.md), [distância_geodésica](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Navegação de origem** | **29 ferramentas idx** para Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — obtenha um índice de função/classe ou definição específica sem ler o arquivo inteiro |

#### Revisão e cobertura do repositório

- `workspace_status`: relata a ramificação Git do espaço de trabalho ativo, alterações, estado de sincronização upstream, tempo de execução do Python e projeto comum marcadores sem modificar arquivos.
- `git_review`: resume alterações do Git, arquivos arriscados, candidatos de teste e descobertas secretas sem expor valores secretos.
- `security_scan`: verifica arquivos de repositório em busca de segredos prováveis e arquivos de configuração arriscados.
- `coverage_report`: executa e normaliza a cobertura para Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift e Dart/Flutter.
- Dependências de cobertura ausentes podem ser instaladas automaticamente quando a execução é solicitada; `dry_run` nunca instala pacotes.
  Consulte [Ferramentas de análise de repositório] (docs/REPOSITORY_TOOLS.md) para parâmetros, saída e detalhes de segurança. Modo | Comando | Objetivo |
  |---|---|---|
  | **CLI** | `uag` | Operação rápida baseada em terminal |
  | **GUI** | `uagg` | UI da área de trabalho via tkinter |
  | **Web** | `uagw` | Acesso baseado em navegador |
  | **A2A Servidor** | `uaga` | Protocolo Agent2Agent para comunicação multiagente |
  | **Código VS** | — | [Extensão](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) com painel de bate-papo, explicação, refatoração, correção de erros e visualização em árvore de ferramentas |
  Consulte [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) para obter detalhes sobre a extensão do VS Code - instalação, comandos, atalhos de teclado e configuração.

### 🏠 Controle de dispositivos IoT

- **BACnet**: leitura/gravação de dispositivos BACnet/IP (HVAC, iluminação, medidores de energia). Assinatura COV para notificações push
- **Modbus TCP**: leitura/gravação de registros e bobinas de retenção/entrada. Monitoramento de alterações baseado em pesquisa
- **OPC UA**: navegue no espaço de endereço, leia/grave variáveis, assine alterações de dados
- **SwitchBot**: controle de lote na nuvem e verificação/controle BLE. Assinatura baseada em pesquisa
- **ECHONET Lite**: descubra, controle e assine notificações INF de eletrodomésticos (AC, luzes, aquecedores de água, etc.)
- **Matéria**: controle de leitura/gravação + assinatura de atributos para monitoramento de mudança de estado
- **UPnP**: descoberta de dispositivos e encaminhamento de porta IGD
  Consulte [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` para navegar em [SkillsMP](https://skillsmp.com) e [ClawHub](https://clawhub.ai) para a comunidade habilidades.
Instale e amplie os recursos do uag instantaneamente.

### 🤖 Piloto automático (`:auto`)

uag pode **perseguir um objetivo de forma autônoma em várias rodadas do LLM**. Perfeito para tarefas complexas e de várias etapas que precisam de refinamento iterativo.

- **Como funciona**: Cada rodada tem uma consulta principal (Etapa A) seguida por um julgamento do revisor (Etapa B) que decide "CONCLUIR ou CONTINUAR?" `UAGENT_AP_PROVIDER` para usar um provedor/modelo diferente para o revisor (por exemplo, use um modelo mais barato para julgar).
- **Sair a qualquer momento**: Pressione a tecla F11 para parar imediatamente, mesmo no meio da resposta. Ou deixe o revisor decidir quando a meta será alcançada.
- **Configurável**: `--max-rounds N` para controlar o orçamento.
  Consulte [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) para obter a documentação completa.

### 🧩 Batch State Manager

uag pode rastrear progresso em tarefas de vários arquivos de longa duração. Quando o LLM processa dezenas de arquivos, `batch_state` persiste a lista de arquivos pendentes, concluídos e com falha no disco. Se a sessão terminar ou uma rodada expirar, a próxima execução será retomada de onde parou - nada será perdido.

### 🛡 Human-in-the-Loop

`human_ask` permite que o LLM faça uma pausa e peça sua confirmação antes de executar operações destrutivas (exclusão de arquivos, substituições, comandos shell). Você permanece no controle.

### 🛑 Interromper (tecla c / botão Parar)

Pare a geração de resposta LLM a qualquer momento e injete um comando de parada de volta ao LLM.
| Interface | Como interromper |
|---|---|
| **CLI** | Pressione a tecla F12 durante o streaming de LLM — a resposta atual para e `"Stop"` é enviado como uma mensagem do usuário para que LLM responda adequadamente |
| **IU da WEB** | Clique no botão vermelho **■ Parar** (aparece automaticamente durante o processamento de LLM) |
| **GUI da área de trabalho** | Clique no botão vermelho **■** (aparece automaticamente durante o processamento de LLM) |
A interrupção funciona como "injeção de prompt": em vez de apenas abortar, ela envia `"Stop"` de volta ao LLM como uma mensagem do usuário, permitindo que ele conclua normalmente ou reconheça a interrupção.
Pressione a tecla F11 para sair do modo de piloto automático (consulte [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Automação do navegador e Web Inspector

Duas ferramentas complementares baseadas em Playwright:

- **browser_playwright**: automatize sessões reais do navegador - navegue, clique, preencha formulários, extraia dados, lide com várias páginas fluxos. Funciona sem cabeça ou sem cabeça.
- **playwright_inspector**: Grave transições do navegador, capture instantâneos e capturas de tela do DOM em cada etapa. Útil para depurar interações da web ou auditar alterações de página ao longo do tempo.

### 🔄 Carregamento dinâmico de ferramentas

`tool_catalog` e `tool_load` permitem descobrir e habilitar ferramentas em tempo de execução.
Não há necessidade de carregar tudo na inicialização - ative apenas o que você precisa, quando você precisar.

### 🦀 Rust Native Tools

`uuid_gen` e `slugify` são implementados em Rust (via PyO3) para desempenho.
Eles carregam diretamente de um `.pyd` pré-construído - \*\*não é necessário `pip install` \*\*.
Desenvolvedores externos também podem enviar ferramentas baseadas em Rust: coloque um `.pyd` próximo ao
wrapper `.py`, use `load_rust_pyd()` de `uagent.tools.rust_helper`, e
os usuários obtêm a ferramenta sem quaisquer dependências extras. Consulte
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Inglês / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / e muito mais.
Defina `UAGENT_LANG` para alternar. Consulte [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) para adicionar uma nova localidade.
As traduções deste README estão disponíveis em [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variáveis de ambiente criptografadas

Armazene chaves e segredos API em `.env.sec` — um arquivo `.env` criptografado.
Gerencie com `uag_envsec`.

## Configuração e detalhes

- **Variáveis de ambiente**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Assistente de configuração**: `python -m uagent.setup_cli`
- **Env criptografado**: `uag_envsec` - criptografar `.env` como `.env.sec`
- **Respostas API**: Defina `UAGENT_RESPONSES=1` para o modo Respostas API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Habilitado automaticamente para Sakana AI (Fugu).
- **Documentos do desenvolvedor**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Fluxo de ferramentas**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — como as ferramentas são enviadas para LLMs (máscara de gênero, catálogo de ferramentas, GPT-5.4+ pesquisa de ferramentas nativa)
- **Pequenas LLM dicas**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Filosofia do Projeto

uag aspira ser **sua IA, em sua máquina, em seus termos.**

- Sem dependência de SaaS - executado localmente
- Sem dependência de provedor - alterne a qualquer momento
- Sem dependência de UI - CLI / GUI / Web / A2A
- Sem dependência de recurso - estenda com ferramentas e habilidades

Uma experiência de agente de IA gratuita, livre do fornecedor lock-in.

### ✨ Crie suas próprias ferramentas

Escrever uma nova ferramenta para uag é simples - crie um único arquivo `.py` com
`TOOL_SPEC` e `run_tool()`, coloque-o em `UAGENT_EXTERNAL_TOOLS_DIR`, e
está imediatamente disponível. Para desenvolvedores Rust, envie um `.pyd` pré-construído com zero dependências extras para os usuários.## Contribuindo

Contribuições são bem-vindas! Relatórios de bugs, sugestões de recursos, melhorias na documentação, traduções e solicitações pull - todos apreciados.

- **Problemas**: Abra um problema GitHub para bugs ou solicitações de recursos.
- **Solicitações pull**: bifurque o repositório, faça suas alterações e envie um PR. Consulte [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) para configurações e diretrizes de desenvolvimento.
- **Traduções**: traduções README e acréscimos de localidade são bem-vindos. Consulte [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Ferramentas e habilidades**: novos plug-ins de ferramentas e habilidades de agente podem ser contribuídos por meio do mercado.

### Verificações de desenvolvimento (antes do PR)

Instale as dependências somente de teste primeiro. Eles são mantidos fora da lista de dependências do tempo de execução:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Execute as mesmas verificações usadas por GitHub Ações antes de enviar:

```bash
python -m ruff check src testes
python -m black --check src testes
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Para uma iteração local mais rápida, execute apenas os testes afetados:

```bash
pytest -q testes/<affected_area>
```

Verificações adicionais quando relevante:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Após as edições de locale (`.po`): `python scripts/compile_locales.py` e `python scripts/po_qc_summary.py`.

Política de tempo de execução (detalhes em [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): ajudantes aumentam em vez de `sys.exit`; o host da ferramenta transforma a ferramenta `SystemExit`/`Exception` em strings de erro para que uma única ferramenta não possa encerrar o processo. As saídas rápidas de inicialização permanecem intencionais.

## Arquitetura e invariantes operacionais

Veja [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para os contratos duráveis ​​que cobrem o ciclo de vida A2A, contextos I18N, instalação de dependência opcional, segurança de ferramentas, recursos do provedor, limites de confiança OAuth, eventos estruturados e verificação de aceitação.

## Enterprise Policy Engine

Políticas em nível de organização para ferramentas, provedores, credenciais, servidores MCP, redes, habilidades e plug-ins são suportadas. Defina `UAGENT_POLICY_FILE` como um arquivo de política JSON/YAML; consulte [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) para exemplos de configuração, funções, confirmação e listas de permissões.

### Recuperação e orquestração em tempo de execução

Veja [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) para recuperação durável, execução com reconhecimento de dependência, orquestração multiagente e uso remoto de A2A.

Consulte [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) para coordenação de locação líder em tempo de execução compartilhado.
