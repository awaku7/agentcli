# UTILIZAÇÃO (Opções da linha de comandos)

Este documento descreve as opções da linha de comandos disponíveis para os pontos de entrada uag.

______________________________________________________________________

## Pontos de entrada

| Comando | Módulo Python | Interface |
|---|---|---|
| `uag` | `python -m uagent` | CLI (loop stdin) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Servidor Web (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | Servidor A2A HTTP |

______________________________________________________________________

## Opções de arranque da CLI (`uag`)

### `--workdir` / `-C <caminho>`

Diretório de trabalho. Se não for definido, recorre à variável de ambiente `UAGENT_WORKDIR` e, em seguida, ao diretório atual.
O diretório é criado caso não exista.

### `--tool-genre-mask <int>`

Máscara de bits do tipo de ferramenta. Quando fornecida, o prompt interativo de seleção de tipo é ignorado.

| Bit | Tipo | Descrição |
|-----|-------|-------------|
| 1 | basic | Ferramentas essenciais de ficheiros/conversação |
| 2 | comm | Ferramentas de comunicação (Bluesky, Teams) |
| 4 | office | Ferramentas do pacote Office (Excel, PDF, PPTX) |
| 8 | devel | Ferramentas de desenvolvimento (git, lint, compile) |
| 16 | iot | Ferramentas para dispositivos IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Ferramentas de execução de comandos |
| 64 | external | Ferramentas de plug-ins externos |
| 128 | media | Geração e análise de imagem/áudio |
| 256 | file | Ferramentas de gestão de ficheiros |
| 512 | index | Ferramentas de navegação em código-fonte/índice |
| 1024 | dev | Ferramentas para programadores e repositórios |
| 2048 | web | Ferramentas para a Web e navegadores |
| 4096 | utility | Ferramentas utilitárias e de suporte |
| 8191 | all | Todas as ferramentas |

Exemplos:

```
uag --tool-genre-mask 1 # apenas básico
uag --tool-genre-mask 9 # básico + desenvolvimento (1 + 8)
uag --tool-genre-mask 8191    # todas as ferramentas
```

### `--use-tool` / `--no-use-tool`

Ativa ou desativa o envio de definições de ferramentas para o `LLM`. Substitui a variável de ambiente `UAGENT_USE_TOOL`.

- `--use-tool` força o envio de ferramentas a ser ativado.
- `--no-use-tool` força o envio de ferramentas a ser desativado.

Quando desativado, o LLM não recebe definições de ferramentas e não pode chamar nenhuma ferramenta.

### `--computer-use` / `--no-computer-use`

Ativa ou desativa a utilização do computador. Substitui a variável de ambiente `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <mensagem>`

Injeta uma mensagem no `LLM` no arranque e termina após a conclusão. Isto implica `--non-interactive`.

### `--embedded`

Modo incorporado para implementações com restrições ou sensíveis à reprodutibilidade.

- Desativa o armazenamento de sessões.
- Oculta as ferramentas de gestão de ferramentas (`tool_catalog`, `tool_load`, `unload_tool`), a menos que sejam explicitamente ativadas.
- Ignora `--tool-genre-mask`; utilize `--enable-tool` para o carregamento explícito de ferramentas.

### `--enable-tool <nome>`

Carrega explicitamente uma ferramenta no arranque. A opção pode ser repetida, sendo também aceites nomes separados por vírgulas.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

A ordem especificada é preservada e reflete-se na ordem das ferramentas apresentada ao LLM. As ferramentas ativadas explicitamente são bloqueadas contra o descarregamento automático.

### `--plugin-dir <caminho>`

Carregar plugins a partir do diretório especificado. A opção pode ser repetida.

______________________________________________________________________

## Opções exclusivas da CLI

### `--inject-message-auto <goal-options>`

Inicia o piloto automático a partir de um objetivo injetado não interativo. O valor utiliza as mesmas opções que `:auto`; coloque o valor completo entre aspas quando este contiver opções.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Ordenar os itens --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Ordenar os itens --infinite"
```

O modo normal utiliza o percurso de avaliação do revisor. Defina `UAGENT_AUTO_SENTINEL=1` para ativar o modo de sentinela única LLM. Nesse modo, o LLM de destino deve terminar cada resposta com exatamente um dos seguintes:

- `<AUTO_CONTINUE>` — executar mais uma ronda
- `<AUTO_COMPLETE>` — concluir com sucesso

Marcadores ausentes ou inválidos interrompem o piloto automático de forma segura. Isto continua a executar o LLM de destino; apenas evita a chamada adicional ao revisor LLM.

### `--non-interactive`

Modo não interativo. Não inicia o ciclo stdin. Se for fornecido um caminho de ficheiro como argumento posicional, este é processado e o programa termina imediatamente.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Opções do servidor Web (`uagw`)

### `--host <address>`

Endereço de ligação para o servidor Web (padrão: `127.0.0.1`, substituível por `UAGENT_WEB_HOST`).

Por predefinição, o servidor Web escuta apenas no localhost (`127.0.0.1`). Para o tornar acessível a partir de outras máquinas na rede, utilize `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Selecione os géneros de ferramentas utilizando a mesma máscara de bits descrita acima. Quando especificado, o prompt interativo de género é ignorado.

### `--use-tool` / `--no-use-tool`

Ativa ou desativa o envio de definições de ferramentas para o LLM. Substitui `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Ativa ou desativa a Utilização do Computador. Substitui `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Executa apenas o API sem modelos HTML nem ficheiros estáticos do frontend.

### `--embedded`

Desativa o armazenamento de sessões e oculta as ferramentas de gestão de ferramentas (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Opções do servidor `A2A` (`uaga`)

### `--host <address>`

Endereço de ligação para o servidor A2A HTTP (padrão: `0.0.0.0`, substituível por `UAGENT_A2A_HOST`).

### `--port <número>`

Número da porta para o servidor A2A HTTP (padrão: `8765`, substituível por `UAGENT_A2A_PORT`).

### `--reload`

Ativar a atualização dinâmica do código após alterações (predefinição: desativado, pode ser substituído por `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Seleciona os tipos de ferramentas utilizando a máscara de bits descrita acima. Quando especificado, o prompt interativo de tipo de ferramenta é ignorado.

### `--use-tool` / `--no-use-tool`

Ativa ou desativa o envio de definições de ferramentas para o `LLM`. Substitui `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Ativa ou desativa a Utilização do Computador. Substitui `UAGENT_COMPUTER_USE`.

### `--embedded`

Desativa o armazenamento de sessões e oculta as ferramentas de gestão de ferramentas (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Variáveis de ambiente relacionadas

| Variável | Descrição |
|---|---|
| `UAGENT_PROVIDER` | Nome do fornecedor do `LLM` (obrigatório no arranque) |
| `UAGENT_*_API_KEY` | Chave do `API` para o fornecedor selecionado |
| `UAGENT_WORKDIR` | Diretório de trabalho predefinido |
| `UAGENT_WEB_HOST` | Endereço de ligação do servidor Web (padrão: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Endereço de ligação do servidor A2A (padrão: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Porta do servidor A2A (padrão: `8765`) |
| `UAGENT_A2A_RELOAD` | Ativar a atualização a quente do A2A por predefinição |
| `UAGENT_USE_TOOL` | Desativar ferramentas quando definido como `0`, `false`, `no` ou `off` |
| `UAGENT_COMPUTER_USE` | Ativar ou desativar a utilização no computador por predefinição |
| `UAGENT_SESSION_STORE` | Ativar ou desativar o armazenamento de sessões; O modo incorporado impõe o valor `0` |
| `UAGENT_PLUGIN_DIRS` | Diretórios adicionais de pesquisa de plugins |
| `UAGENT_AUTO_SENTINEL` | Ativar o modo sentinela de piloto automático único `LLM` quando definido como `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Número máximo de chamadas consecutivas de ferramentas novas (predefinição: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Número máximo de rondas de `LLM`/ferramenta por operação do utilizador (predefinição: `200`) |
| `UAGENT_SHRINK_CNT` | Limiar opcional de redução automática nas mensagens (`0`/não definido = desativado) |
| `UAGENT_SHRINK_KEEP_LAST` | Mensagens a reter após a redução (padrão: `20`) |
| `UAGENT_LANG` | Idioma da interface (`ja`, `en`, etc.) |

Para consultar a lista completa de variáveis de ambiente, consulte [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Exemplos

### Inicialização mínima com OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Ollama local apenas com ferramentas básicas

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Servidor Web em todas as interfaces

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

ou

```
uagw --host 0.0.0.0
```

### Servidor A2A no localhost com porta personalizada

```
uaga --host 127.0.0.1 --port 8080
```

### Desativar ferramentas para um modelo pequeno

```
uag --no-use-tool --tool-genre-mask 1
```

### Processamento não interativo de ficheiros

```
uag --non-interactive README.md
```
