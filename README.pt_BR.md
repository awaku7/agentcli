# uag (uagent)

uag é um agente de execução de ferramentas de propósito geral que roda em seu ambiente local. Ele interage com os usuários através de uma interface de linha de comando (CLI) e realiza várias tarefas, como operações de arquivo, busca na web e execução de scripts Python de acordo com as instruções.

## Principais Funcionalidades

- **Operações de arquivos locais**: Leitura, escrita, edição e busca de arquivos.
- **Recuperação de informações**: Busca na web com DuckDuckGo e extração de conteúdo de páginas web.
- **Execução de código**: Execução segura de scripts Python e comandos PowerShell.
- **Processamento multimídia**: Geração de imagens, leitura de arquivos PDF/PPTX, capturas de tela.
- **Suporte a vários idiomas**: Suporta vários idiomas, incluindo português, japonês e inglês.
- **Suporte MCP (Model Context Protocol)**: Pode ser conectado a servidores MCP externos para expandir suas funções.

## Instalação

Você pode instalá-lo com pip do PyPI:

```bash
pip install uag
```

Na primeira execução, um assistente de configuração será iniciado automaticamente.

## Início Rápido

Após a instalação, basta digitar o seguinte comando para começar:

```bash
uag
```

Uma vez iniciado, você pode pedir ao agente coisas como:
- "Leia o README no diretório atual e resuma seu conteúdo."
- "Pesquise na web as últimas notícias sobre IA e faça um resumo."
- "Compacte todos os arquivos PNG na pasta 'images' em um arquivo ZIP."

## Configuração (Variáveis de Ambiente)

O comportamento do uag pode ser configurado através de variáveis de ambiente. Para mais detalhes, consulte:
- [ENVIRONMENT.md (English)](ENVIRONMENT.md)

## Documentação

- [README.md (English)](README.md)
- [README.ja.md (Japanese)](README.ja.md)

## Licença

Publicado sob a Licença Apache 2.0.
