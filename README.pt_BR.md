<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Agente de IA Local)

O uag é um agente interativo que executa **comandos**, manipula **arquivos** e lê **vários formatos de dados** (PDF/PPTX/Excel, etc.) no seu PC local. Ele oferece três interfaces: CLI, GUI e Web.

GitHub: https://github.com/awaku7/agentcli

## Instalação

Você pode instalar o `uag` via pip:

```bash
pip install uag
```

Após a instalação, a primeira execução do `uag` iniciará automaticamente um **assistente de configuração interativo** para configurar suas variáveis de ambiente. Para informações detalhadas sobre configuração e criptografia, consulte **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Principais Características

- **Conjunto de Ferramentas Práticas**: Equipado com ferramentas para manipulação de arquivos, busca na web, extração de dados (PDF/PPTX/Excel), geração de imagens e análise, todas executáveis em seu ambiente local.
- **Suporte Multi-Provedor**: Suporta OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Interfaces Flexíveis**: 
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: Suporte para conexão com servidores de ferramentas MCP externos.
- **Continuidade de Sessão**: Mantém o contexto da conversa mesmo ao trocar de provedor ou modelo.
- **Web Inspector**: Salva automaticamente transições de navegador, DOM e capturas de tela usando o `playwright_inspector`.
- **Documentação Integrada**: Acesse instantaneamente a documentação interna detalhada usando o comando `uag docs`.

## Uso

### Iniciar e Sair
Execute `uag` no seu terminal para começar. Digite `:exit` para sair.

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
- `:skills`: Seleciona e carrega Agent Skills (funções ou instruções adicionais).
- `:shrink [n]`: Organiza o histórico para manter apenas as últimas `n` mensagens para economizar tokens.

## Configuração e Detalhes

### Variáveis de Ambiente e Configuração
Para configurações detalhadas (chaves de API, idioma de exibição `UAGENT_LANG`, configurações de redução de histórico, etc.), consulte **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.
- **Setup**: Configure interativamente via `python -m uagent.setup_cli`.
- **Criptografia**: Criptografe seus arquivos `.env` com segurança usando a ferramenta `uag_envsec`.
- **Atualização**: Use `uag_envsec add --file .env.sec --key NAME --value VALUE` para adicionar ou atualizar uma variável em um arquivo criptografado existente.

### Desenvolvedores e Internacionalização
- **Docs para Desenvolvedores**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Adicionando Locais**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README em outros idiomas**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/README.nb.md)
