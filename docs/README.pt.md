<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Agente de IA local)

O uag é um agente interativo local que executa **comandos**, manipula **arquivos** e lê arquivos de dados como PDF, PPTX e Excel. Ele oferece três interfaces de usuário: CLI, GUI e Web.

O uag foi criado para **mantê-lo livre de aplicativos presos a um fornecedor**: use a interface que melhor se encaixa no seu fluxo de trabalho, troque de provedor e mantenha o controle do seu ambiente.

GitHub: https://github.com/awaku7/agentcli

## Instalação

Instale do PyPI com pip:

```bash
pip install uag
```

Se você usa um ambiente virtual, ative-o primeiro e depois execute o comando acima.

Na primeira execução, o `uag` verifica seu ambiente e inicia automaticamente o assistente de configuração quando faltam variáveis exigidas do provedor. Para detalhes de configuração, consulte [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Principais recursos

- **Conjunto de ferramentas prático**: manipulação de arquivos, busca na web, extração de PDF/PPTX/Excel, geração de imagens e análise de imagens.
- **Suporte a múltiplos provedores**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI).
- **Três interfaces**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **Servidor A2A**: `uaga` / `python -m uagent.a2a.server`
- **Suporte a MCP**: conecte-se a servidores externos de ferramentas MCP.
- **Continuidade de sessão**: mantenha o contexto ao trocar de modelos ou provedores.
- **Web Inspector**: salve transições do navegador, snapshots do DOM e capturas de tela com `playwright_inspector`.
- **Documentação embutida**: leia os docs incluídos com `uag docs`.

## Uso

### Iniciar e sair

Execute `uag` no terminal para iniciar. Digite `:exit` para sair.

### Servidor A2A

Inicie um servidor HTTP compatível com Agent2Agent:

```bash
uaga
```

Consulte [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) para as configurações `UAGENT_A2A_*`, como autenticação, host, porta, recarregamento, URL base pública, concorrência e mecanismo.

### Dicas úteis

- `:tools`: mostra as ferramentas carregadas
- `:logs [n]`: mostra os registros recentes da sessão
- `:load <index>`: carrega uma sessão anterior
- `:skills`: seleciona e carrega Agent Skills
- `:shrink [n]`: resume o histórico e mantém as últimas `n` mensagens

## Configuração e detalhes

### Variáveis de ambiente e configuração

Para chaves de API, configurações de idioma (`UAGENT_LANG`), ajustes de redução de histórico e mais, consulte [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **Assistente de configuração**: `python -m uagent.setup_cli`
- **Ambiente criptografado**: use `uag_envsec` para criptografar `.env` como `.env.sec`
- **Atualizar valores criptografados**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Nota sobre a Responses API

Se você definir `UAGENT_RESPONSES=1`, a Responses API será usada para os provedores compatíveis: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Para os demais provedores, o uag retorna ao caminho específico do provedor ou ao fluxo chat-completions.

### Docs para desenvolvedores e traduções

- **Docs para desenvolvedores**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Adicionar idiomas**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Outros README traduzidos**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)

Se você definir `UAGENT_RESPONSES=1`, a Responses API será usada para os provedores compatíveis: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.
