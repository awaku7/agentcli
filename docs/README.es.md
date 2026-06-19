<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Agente de IA local)

uag es un agente interactivo que ejecuta **comandos**, manipula **archivos** y lee **varios formatos de datos** (PDF/PPTX/Excel, etc.) en su PC local. Ofrece tres interfaces: CLI, GUI y Web.

uag está diseñado para **mantenerle libre de aplicaciones atadas a un proveedor**: use la interfaz que mejor se adapte a su flujo de trabajo, cambie de proveedor y mantenga el control de su entorno.

GitHub: https://github.com/awaku7/agentcli

## Instalación

Puede instalar `uag` a través de pip:

```bash
pip install uag
```

Después de la instalación, la primera vez que ejecute `uag` se iniciará automáticamente un **asistente de configuración interactivo** para configurar sus variables de entorno. Para obtener información detallada sobre la configuración y el cifrado, consulte **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Características principales

- **Conjunto de herramientas prácticas**: Equipado con herramientas para la manipulación de archivos, búsqueda web, extracción de datos (PDF/PPTX/Excel), generación de imágenes y análisis, todas ejecutables en su entorno local.
- **Soporte multiproveedor**: Soporta OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI / MiMo / LM Studio.
- **Interfaces flexibles**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: Soporte para conectar con servidores de herramientas MCP externos.
- **Continuidad de sesión**: Mantiene el contexto de la conversación incluso al cambiar de proveedor o modelo.
- **Mercado de habilidades de agente**: Explore e instale habilidades comunitarias de [SkillsMP](https://skillsmp.com) o [ClawHub](https://clawhub.ai) con `:skills mp_search`.
- **Web Inspector**: Guarda automáticamente las transiciones del navegador, el DOM y las capturas de pantalla con `playwright_inspector`.
- **Documentación integrada**: Acceda instantáneamente a la documentación interna detallada utilizando el comando `uag docs`.
- **Catálogo de herramientas (Nuevo!)**: Descubra y cargue herramientas dinámicamente con `tool_catalog`/`tool_load`. Funciona con todos los proveedores compatibles — no requiere APIs específicas del proveedor.
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

### Inicio y salida

Ejecute `uag` desde su terminal para comenzar. Escriba `:exit` para salir.

For all command-line options, see [USAGE.md](USAGE.md).

### Servidor A2A (Agent2Agent)

Puede iniciar un servidor HTTP compatible con A2A separado de las interfaces existentes.

```bash
uaga
# o python -m uagent.a2a.server
```

### Nota sobre la API de Responses

Si establece `UAGENT_RESPONSES=1`, se usará la API de Responses para los proveedores compatibles: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI usan sus rutas de API nativas y no están cubiertos por la API de Responses.
Para los demás proveedores, uag vuelve a la ruta específica del proveedor o al flujo chat-completions.

Consulte [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) para la configuración de `UAGENT_A2A_*` como autenticación, host, puerto, recarga, URL base pública, concurrencia y motor.

### Consejos prácticos (continuidad y控制)

- `:tools`: Muestra una lista de las herramientas cargadas.
- `:logs [n]`: Muestra los registros de sesión (`n` para especificar el número de entradas).
- `:load <index>`: Carga una sesión pasada para reanudar la conversación.
- `:skills`: seleccionar y cargar Agent Skills (use `:skills mp_search` para explorar los mercados de [SkillsMP](https://skillsmp.com) o [ClawHub](https://clawhub.ai))
- `:shrink [n]`: Organiza el historial para mantener solo los últimos `n` mensajes y ahorrar tokens.
- Small LLM tips: see [SLM_TIPS.md](SLM_TIPS.md).

## Configuración y detalles

### Variables de entorno y configuración

Para ajustes detallados (claves API, idioma de pantalla `UAGENT_LANG`, ajustes de reducción de historial, etc.), consulte **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

- **Configuración**: Configure de forma interactiva a través de `python -m uagent.setup_cli`.
- **Cifrado**: Cifre sus archivos `.env` de forma segura utilizando la herramienta `uag_envsec`.
- **Actualización**: Use `uag_envsec add --file .env.sec --key NAME --value VALUE` para agregar o actualizar una variable en un archivo cifrado existente.

### Desarrolladores e internacionalización

- **Documentación para desarrolladores**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Añadir locales**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README en otros idiomas**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
