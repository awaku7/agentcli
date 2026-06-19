<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Agente de IA Local)

O uag é um agente interativo que executa **comandos**, manipula **arquivos** e lê **vários formatos de dados** (PDF/PPTX/Excel, etc.) no seu PC local. Ele oferece três interfaces: CLI, GUI e Web.

O uag foi criado para **mantê-lo livre de aplicativos presos a um fornecedor**: use a interface que melhor se encaixa no seu fluxo de trabalho, troque de provedor e mantenha o controle do seu ambiente.

GitHub: https://github.com/awaku7/agentcli

## Instalação

Você pode instalar o `uag` via pip:

```bash
pip install uag
```

Após a instalação, a primeira execução do `uag` iniciará automaticamente um **assistente de configuração interativo** para configurar suas variáveis de ambiente. Para informações detalhadas sobre configuração e criptografia, consulte **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Principais Características

- **Conjunto de Ferramentas Práticas**: Equipado com ferramentas para manipulação de arquivos, busca na web, extração de dados (PDF/PPTX/Excel), geração de imagens e análise, todas executáveis em seu ambiente local.
- **Suporte Multi-Provedor**: Suporta OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI / MiMo / LM Studio.
- **Interfaces Flexíveis**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: Suporte para conexão com servidores de ferramentas MCP externos.
- **Continuidade de Sessão**: Mantém o contexto da conversa mesmo ao trocar de provedor ou modelo.
- **Mercado de habilidades de agente**: Navegue e instale habilidades da comunidade do [SkillsMP](https://skillsmp.com) ou [ClawHub](https://clawhub.ai) com `:skills mp_search`.
- **Web Inspector**: Salva automaticamente transições de navegador, DOM e capturas de tela usando o `playwright_inspector`.
- **Documentação Integrada**: Acesse instantaneamente a documentação interna detalhada usando o comando `uag docs`.
- **Catálogo de ferramentas (Novo!)**: Descubra e carregue ferramentas dinamicamente com `tool_catalog`/`tool_load`. Funciona com todos os provedores compatíveis — nenhuma API específica do provedor necessária.
- **IoT device support**: Control SwitchBot, ECHONET Lite, Matter, and UPnP devices. See [IOT_USECASE.md](IOT_USECASE.md).

## IoT Device Support

Control smart home and IoT devices through multiple interfaces:

- **SwitchBot Cloud**: List, control, and batch-operate SwitchBot devices (TV, air conditioner, lights, etc.).
  - Infrared remote devices (on/off, brightness, temperature)
  - Air conditioner mode and fan speed control
  - Batch execution of multiple commands
- **SwitchBot BLE**: Scan and control nearby SwitchBot BLE devices.
- **ECHONET Lite**: Discover and control ECHONET Lite home appliances over the local network.
- **Matter**: Inspect Matter controller/bridge/device structure (read-only).
- **UPnP**: Discover UPnP devices and manage IGD port forwarding.

For detailed usage, see [IOT_USECASE.md](IOT_USECASE.md).

## Uso

### Iniciar e Sair

Execute `uag` no seu terminal para começar. Digite `:exit` para sair.

For all command-line options, see [USAGE.md](USAGE.md).

### Servidor A2A (Agent2Agent)

Você pode iniciar um servidor HTTP compatível com A2A separado das interfaces existentes.

```bash
uaga
# ou python -m uagent.a2a.server
```

### Nota sobre a Responses API

Se você definir `UAGENT_RESPONSES=1`, a Responses API será usada para os provedores compatíveis: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI usam seus caminhos de API nativos e não são cobertos pela Responses API.
Para os demais provedores, o uag volta ao caminho específico do provedor ou ao fluxo chat-completions.

Veja [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) para as configurações `UAGENT_A2A_*`, como autenticação, host, porta, recarregamento, URL base pública, concorrência e mecanismo.

### Dicas Úteis (Continuidade e Controle)

- `:tools`: Exibe uma lista das ferramentas carregadas.
- `:logs [n]`: Mostra os logs da sessão (`n` para especificar o número de entradas).
- `:load <index>`: Carrega uma sessão anterior para retomar a conversa.
- `:skills`: selecionar e carregar Agent Skills (use `:skills mp_search` para navegar nos marketplaces [SkillsMP](https://skillsmp.com) ou [ClawHub](https://clawhub.ai))
- `:shrink [n]`: Organiza o histórico para manter apenas as últimas `n` mensagens para economizar tokens.
- Small LLM tips: see [SLM_TIPS.md](SLM_TIPS.md).

## Configuração e Detalhes

### Variáveis de Ambiente e Configuração

Para configurações detalhadas (chaves de API, idioma de exibição `UAGENT_LANG`, configurações de redução de histórico, etc.), consulte **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

- **Setup**: Configure interativamente via `python -m uagent.setup_cli`.
- **Criptografia**: Criptografe seus arquivos `.env` com segurança usando a ferramenta `uag_envsec`.
- **Atualização**: Use `uag_envsec add --file .env.sec --key NAME --value VALUE` para adicionar ou atualizar uma variável em um arquivo criptografado existente.

### Desenvolvedores e Internacionalização

- **Docs para Desenvolvedores**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Adicionando Locais**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README em outros idiomas**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
