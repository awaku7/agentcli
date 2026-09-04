# USO (Opções de linha de comando)

Este documento descreve as opções de linha de comando disponíveis para os pontos de entrada uag.

______________________________________________________________________

## Pontos de entrada

| Comando | Módulo Python | Interface |
|---|---|---|
| `uag` | `python -m uagent` | CLI (loop de stdin) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Servidor web (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | servidor A2A HTTP |

______________________________________________________________________

## Opções de inicialização da CLI (`uag`)

### `--workdir` / `-C <caminho>`

Diretório de trabalho. Se não for definido, recorre à variável de ambiente `UAGENT_WORKDIR` e, em seguida, ao diretório atual.
O diretório é criado caso não exista.

### `--tool-genre-mask <int>`

Máscara de bits do tipo de ferramenta. Quando fornecida, a solicitação interativa de seleção de tipo é ignorada.

| Bit | Tipo | Descrição |
|-----|-------|-------------|
| 1 | basic | Ferramentas essenciais de arquivos/bate-papo |
| 2 | comm | Ferramentas de comunicação (Bluesky, Teams) |
| 4 | office | Ferramentas de suíte de escritório (Excel, PDF, PPTX) |
| 8 | devel | Ferramentas de desenvolvimento (git, lint, compile) |
| 16 | iot | Ferramentas para dispositivos IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Ferramentas de execução de comandos |
| 64 | external | Ferramentas de plug-ins externos |
| 128 | media | Geração e análise de imagens/áudio |
| 256 | file | Ferramentas de gerenciamento de arquivos |
| 512 | index | Ferramentas de navegação em código-fonte/índice |
| 1024 | dev | Ferramentas para desenvolvedores e repositórios |
| 2048 | web | Ferramentas para a web e navegadores |
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

Quando desativado, o `LLM` não recebe definições de ferramentas e não pode chamar nenhuma ferramenta.

### `--computer-use` / `--no-computer-use`

Ativa ou desativa o uso do computador. Substitui a variável de ambiente `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <mensagem>`

Inserir uma mensagem no `LLM` na inicialização e encerrar após a conclusão. Isso implica `--non-interactive`.

### `--embedded`

Modo incorporado para implantações restritas ou sensíveis à reprodutibilidade.

- Desativa o armazenamento de sessão.
- Oculta as ferramentas de gerenciamento de ferramentas (`tool_catalog`, `tool_load`, `unload_tool`), a menos que sejam explicitamente ativadas.
- Ignora `--tool-genre-mask`; use `--enable-tool` para carregamento explícito de ferramentas.

### `--enable-tool <nome>`

Carrega explicitamente uma ferramenta na inicialização. A opção pode ser repetida, e nomes separados por vírgulas também são aceitos.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

A ordem especificada é preservada e refletida na ordem das ferramentas apresentada ao LLM. As ferramentas ativadas explicitamente são protegidas contra o descarregamento automático.

### `--plugin-dir <caminho>`

Carrega plug-ins do diretório especificado. A opção pode ser repetida.

______________________________________________________________________

## Opções exclusivas da CLI

### `--inject-message-auto <goal-options>`

Inicia o piloto automático a partir de uma meta injetada não interativa. O valor utiliza as mesmas opções que `:auto`; coloque o valor completo entre aspas quando ele contiver opções.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Classificar os itens --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Classificar os itens --infinite"
```

O modo normal utiliza o caminho de julgamento do revisor. Defina `UAGENT_AUTO_SENTINEL=1` para ativar o modo de sentinela única LLM. Nesse modo, o LLM de destino deve encerrar cada resposta com exatamente um dos seguintes:

- `<AUTO_CONTINUE>` — executar outra rodada
- `<AUTO_COMPLETE>` — concluir com sucesso

Marcadores ausentes ou inválidos interrompem o piloto automático com segurança. Isso ainda executa o LLM de destino; apenas evita a chamada adicional do revisor ao LLM.

### `--non-interactive`

Modo não interativo. Não inicia o loop de stdin. Se um caminho de arquivo for fornecido como argumento posicional, ele será processado e o programa será encerrado imediatamente.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Opções do servidor web (`uagw`)

### `--host <address>`

Endereço de ligação para o servidor web (padrão: `127.0.0.1`, substituível por `UAGENT_WEB_HOST`).

Por padrão, o servidor Web escuta apenas no localhost (`127.0.0.1`). Para torná-lo acessível a partir de outras máquinas na rede, use `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Selecione gêneros de ferramentas usando a mesma máscara de bits descrita acima. Quando especificado, o prompt interativo de gênero é ignorado.

### `--use-tool` / `--no-use-tool`

Ativa ou desativa o envio de definições de ferramentas para o LLM. Substitui `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Ativa ou desativa o uso do computador. Substitui `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Executa apenas o API sem modelos HTML ou arquivos estáticos de interface.

### `--embedded`

Desativa o armazenamento de sessão e oculta as ferramentas de gerenciamento de ferramentas (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Opções do servidor A2A (`uaga`)

### `--host <address>`

Endereço de ligação para o servidor A2A HTTP (padrão: `0.0.0.0`, substituível por `UAGENT_A2A_HOST`).

### `--port <número>`

Número da porta para o servidor A2A HTTP (padrão: `8765`, pode ser substituído por `UAGENT_A2A_PORT`).

### `--reload`

Ativa a recarga dinâmica ao alterar o código (padrão: desativado, pode ser substituído por `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Selecione os tipos de ferramentas usando a máscara de bits descrita acima. Quando especificado, o prompt interativo de gênero é ignorado.

### `--use-tool` / `--no-use-tool`

Ativa ou desativa o envio de definições de ferramentas para o `LLM`. Substitui `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Ativa ou desativa o uso do computador. Substitui `UAGENT_COMPUTER_USE`.

### `--embedded`

Desativa o armazenamento de sessão e oculta as ferramentas de gerenciamento de ferramentas (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Variáveis de ambiente relacionadas

| Variável | Descrição |
|---|---|
| `UAGENT_PROVIDER` | Nome do provedor do `LLM` (obrigatório na inicialização) |
| `UAGENT_*_API_KEY` | Chave do `API` para o provedor selecionado |
| `UAGENT_WORKDIR` | Diretório de trabalho padrão |
| `UAGENT_WEB_HOST` | Endereço de ligação do servidor web (padrão: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Endereço de ligação do servidor A2A (padrão: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Porta do servidor A2A (padrão: `8765`) |
| `UAGENT_A2A_RELOAD` | Ativar recarga dinâmica do A2A por padrão |
| `UAGENT_USE_TOOL` | Desativar ferramentas quando definido como `0`, `false`, `no` ou `off` |
| `UAGENT_COMPUTER_USE` | Ativar ou desativar o uso em computador por padrão |
| `UAGENT_SESSION_STORE` | Ativar ou desativar o armazenamento de sessões; O modo incorporado força o valor `0` |
| `UAGENT_PLUGIN_DIRS` | Diretórios adicionais de busca de plug-ins |
| `UAGENT_AUTO_SENTINEL` | Ativa o modo sentinela de piloto automático único `LLM` quando definido como `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Número máximo de chamadas consecutivas de ferramentas novas (padrão: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Número máximo de rodadas de `LLM`/ferramenta por operação do usuário (padrão: `200`) |
| `UAGENT_SHRINK_CNT` | Limite opcional de redução automática nas mensagens (`0`/não definido = desativado) |
| `UAGENT_SHRINK_KEEP_LAST` | Mensagens a serem mantidas após a redução (padrão: `20`) |
| `UAGENT_LANG` | Idioma da interface (`ja`, `en`, etc.) |

Para a lista completa de variáveis de ambiente, consulte [ENVIRONMENT.md](ENVIRONMENT.md).

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

### Servidor web em todas as interfaces

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

### Processamento não interativo de arquivos

```
uag --non-interactive README.md
```
