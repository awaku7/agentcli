<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Agente de IA local)

uag es un agente interactivo que ejecuta **comandos**, manipula **archivos** y lee **varios formatos de datos** (PDF/PPTX/Excel, etc.) en su PC local. Ofrece tres interfaces: CLI, GUI y Web.


GitHub: https://github.com/awaku7/agentcli

## Instalación

Puede instalar `uag` a través de pip:

```bash
pip install uag
```

Después de la instalación, la primera vez que ejecute `uag` se iniciará automáticamente un **asistente de configuración interactivo** para configurar sus variables de entorno. Para obtener información detallada sobre la configuración y el cifrado, consulte **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Características principales

- **Conjunto de herramientas prácticas**: Equipado con herramientas para la manipulación de archivos, búsqueda web, extracción de datos (PDF/PPTX/Excel), generación de imágenes y análisis, todas ejecutables en su entorno local.
- **Soporte multiproveedor**: Soporta OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Interfaces flexibles**: 
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: Soporte para conectar con servidores de herramientas MCP externos.
- **Continuidad de sesión**: Mantiene el contexto de la conversación incluso al cambiar de proveedor o modelo.
- **Web Inspector**: Guarda automáticamente las transiciones del navegador, el DOM y las capturas de pantalla con `playwright_inspector`.
- **Documentación integrada**: Acceda instantáneamente a la documentación interna detallada utilizando el comando `uag docs`.

## Uso

### Inicio y salida
Ejecute `uag` desde su terminal para comenzar. Escriba `:exit` para salir.

### Servidor A2A (Agent2Agent)
Puede iniciar un servidor HTTP compatible con A2A separado de las interfaces existentes.
```bash
uaga
# o python -m uagent.a2a.server
```

### Consejos prácticos (continuidad y控制)
- `:tools`: Muestra una lista de las herramientas cargadas.
- `:logs [n]`: Muestra los registros de sesión (`n` para especificar el número de entradas).
- `:load <index>`: Carga una sesión pasada para reanudar la conversación.
- `:skills`: Selecciona y carga Agent Skills (roles o instrucciones adicionales).
- `:shrink [n]`: Organiza el historial para mantener solo los últimos `n` mensajes y ahorrar tokens.

## Configuración y detalles

### Variables de entorno y configuración
Para ajustes detallados (claves API, idioma de pantalla `UAGENT_LANG`, ajustes de reducción de historial, etc.), consulte **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.
- **Configuración**: Configure de forma interactiva a través de `python -m uagent.setup_cli`.
- **Cifrado**: Cifre sus archivos `.env` de forma segura utilizando la herramienta `uag_envsec`.
- **Actualización**: Use `uag_envsec add --file .env.sec --key NAME --value VALUE` para agregar o actualizar una variable en un archivo cifrado existente.

### Desarrolladores e internacionalización
- **Documentación para desarrolladores**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Añadir locales**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README en otros idiomas**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/README.id.md)
