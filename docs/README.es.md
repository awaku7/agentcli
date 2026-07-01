<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag - Puerta de enlace universal de IA</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## ¿Por qué uag?

**Libérese de la dependencia de un proveedor.** La mayoría de los asistentes de IA lo vinculan a un proveedor o servicio en la nube específico. uag es diferente.

- **Se ejecuta localmente** en su máquina. Sus datos permanecen con usted (excepto las llamadas API que realice).
- **Libertad de proveedores**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... Más de 15 proveedores, todos accesibles desde una única interfaz. Cambie entre ellos reconfigurando las variables de entorno: sin reinstalación ni migración.
- **131 herramientas**: E/S de archivos, búsqueda web, generación de imágenes, Gmail, escaneo de dispositivos BLE, integración de servidor MCP. **76 son seguras en paralelo** (hasta 8 se ejecutan simultáneamente a través del grupo de subprocesos, configurables a través de `UAGENT_PARALLEL_WORKERS`). Cuando el LLM activa varias llamadas a herramientas a la vez, uag las paraleliza automáticamente.
- **3 UI + A2A**: CLI, GUI, web y protocolo de agente a agente. Mismo motor, cualquier interfaz.
- **Listo para IoT**: SwitchBot, ECHONET Lite, Matter, UPnP: controle sus dispositivos domésticos a través de IA.
- **Habilidades del agente**: instale habilidades creadas por la comunidad desde el mercado. Extiende uag sin cesar.

uag es **tu asistente de IA según tus términos**. No vinculado a un proveedor, no vinculado a una interfaz, no vinculado a una plataforma.

## Inicio rápido

```bash
pip install uag
uag
```

En el primer inicio, el asistente de configuración lo guiará a través de la configuración del proveedor.
Consulte [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) para conocer todas las variables de entorno.

## Características

### 🧠 Arquitectura multiproveedor

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Todos los proveedores comparten el mismo conjunto de herramientas e interfaz. Cambie configurando `UAGENT_PROVIDER`: sin cambios de código, sin instalaciones separadas.

### ⚡ Ejecución de herramientas paralelas

Cuando el LLM solicita varias herramientas simultáneamente, uag las **paraleliza automáticamente**.
76 herramientas están marcadas como `x_parallel_safe` y se ejecutan simultáneamente a través de un `ThreadPoolExecutor` (8 subprocesos de forma predeterminada; configure `UAGENT_PARALLEL_WORKERS` para cambiar).

**Ejemplo**: Pregunte "Consulte el clima en las capitales nórdicas" → LLM activa `search_web` × 5 países → las 5 búsquedas se ejecutan en paralelo → los resultados se recopilan en un lote.

Las herramientas de solo lectura (búsqueda de archivos, cálculo hash, listado de directorios, traducción, consultas de bases de datos, etc.) están agresivamente paralelizadas.

### 🔄 Continuidad de la sesión

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 herramientas

| Categoría | Herramientas |
|---|---|
| **Operaciones de archivos** | leer/escribir/crear/eliminar/buscar/grep/hash/zip, parse_eml (archivos .eml) |
| **Web** | fetch_url, search_web, captura de pantalla, browser_playwright |
| **Medios** | generar_imagen, analizar_imagen, img2img, audio_speech, audio_transcribe |
| **Documentos** | Extracción de PDF/PPTX/DOCX/RTF/ODT, extracción estructurada de Excel |
| **Comunicación** | gmail_send, gmail_read, bluesky, discord_channel, equipos_webhook: consulte [COMMUNICATION.md](https://github.com/awak7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Nube + BLE), ECHONET Lite, Matter, UPnP |
| **Herramientas de desarrollo** | git_ops, python_compile, lint_format, run_tests, db_query, **13 navegadores de código fuente (familia idx)** |
| **MCP** | Conéctese a servidores MCP externos, enumere herramientas, ejecute |
| **A2A** | Comunicación de agente a agente (con otras instancias de uag o servidores compatibles con A2A) |
| **Sistema** | vars env, especificaciones del sistema, hora, cálculo de fecha |
| **Navegación de origen** | **13 herramientas idx** para Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL: obtenga un índice de función/clase o una definición específica sin leer el archivo completo |

### 🖥 4 interfaces + extensión de código VS

| Modo | Comando | Propósito |
|---|---|---|
| **CLI** | `uag` | Operación rápida basada en terminal |
| **GUI** | `uagg` | UI de escritorio a través de tkinter |
| **Web** | `uagw` | Acceso basado en navegador |
| **Servidor A2A** | `uagá` | Protocolo Agent2Agent para comunicación multiagente |
| **Código VS** | — | [Extensión](https://github.com/awak7/agentcli/blob/main/VSCODE.md) con panel de chat, explicación, refactorización, corrección de errores y vista de árbol de herramientas |

Consulte [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) para obtener detalles sobre la extensión VS Code: instalación, comandos, combinaciones de teclas y configuración.

### 🏠 Control de dispositivos IoT

- **SwitchBot**: control de lotes en la nube y escaneo/control BLE
- **ECHONET Lite**: descubre y controla electrodomésticos (aire acondicionado, luces, calentadores de agua, etc.) en la red local
- **Asunto**: Inspección de solo lectura de la topología del controlador/puente/dispositivo
- **UPnP**: descubrimiento de dispositivos y reenvío de puertos IGD

Consulte [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Mercado de habilidades para agentes

`:skills mp_search` para explorar [SkillsMP](https://skillsmp.com) y [ClawHub](https://clawhub.ai) en busca de habilidades comunitarias.
Instale y amplíe las capacidades de uag sobre la marcha.

### 🤖 Piloto automático (`:auto`)

uag puede **perseguir un objetivo de forma autónoma en varias rondas de LLM**. Perfecto para tareas complejas de varios pasos que necesitan un refinamiento iterativo.

- **Cómo funciona**: Cada ronda tiene una consulta principal (Paso A) seguida de un juicio del revisor (Paso B) que decide "¿COMPLETAR o CONTINUAR?"
- **Mismo proveedor, misma API**: el criterio del revisor utiliza la ruta de código idéntica a la de la consulta principal, incluida la compatibilidad con la API de Respuestas.
- **Juez separado LLM** (opcional): configure `UAGENT_AP_PROVIDER` para usar un proveedor/modelo diferente para el revisor (por ejemplo, use un modelo más económico para juzgar).
- **Salir en cualquier momento**: presione la tecla `x` para detenerse inmediatamente, incluso a mitad de respuesta. O dejar que el revisor decida cuándo se alcanza el objetivo.
- **Configurable**: `--max-rounds N` para controlar el presupuesto.

Consulte [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) para obtener la documentación completa.

### 🧩 Administrador de estado de lotes

uag puede realizar un seguimiento del progreso en tareas de varios archivos de larga duración. Cuando el LLM procesa docenas de archivos, `batch_state` conserva la lista de archivos pendientes, completados y fallidos en el disco. Si la sesión finaliza o una ronda se agota, la siguiente ejecución se reanuda desde donde se detuvo y no se pierde nada.

### 🛡 Humano en el circuito

`human_ask` permite que el LLM se detenga y solicite su confirmación antes de realizar operaciones destructivas (eliminación de archivos, sobrescrituras, comandos de shell). Tú mantienes el control.

### 🛑 Interrumpir (tecla c / botón Detener)

Detenga la generación de respuesta de LLM en cualquier momento e inyecte un comando de parada nuevamente al LLM.

| Interfaz | Cómo interrumpir |
|---|---|
| **CLI** | Presione la tecla `c` durante la transmisión de LLM: la respuesta actual se detiene y `"Detener"` se envía como un mensaje de usuario para que el LLM responda en consecuencia |
| **UI WEB** | Haga clic en el botón rojo **■ Detener** (aparece automáticamente durante el procesamiento de LLM) |
| **GUI de escritorio** | Haga clic en el botón rojo **■** (aparece automáticamente durante el procesamiento de LLM) |

La interrupción funciona como una "inyección rápida": en lugar de simplemente abortar, envía "Detener" al LLM como un mensaje de usuario, lo que le permite concluir o reconocer la interrupción con elegancia.

Presione la tecla `x` para salir del modo de piloto automático (consulte [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ Automatización del navegador e inspector web

Dos herramientas complementarias basadas en Dramaturgo:

- **browser_playwright**: automatice sesiones de navegador reales: navegue, haga clic, complete formularios, extraiga datos, maneje flujos de varias páginas. Funciona sin cabeza o con cabeza.
- **playwright_inspector**: registra transiciones del navegador, captura instantáneas de DOM y capturas de pantalla en cada paso. Útil para depurar interacciones web o auditar cambios de página a lo largo del tiempo.

### 🔄 Carga dinámica de herramientas

`tool_catalog` y `tool_load` le permiten descubrir y habilitar herramientas en tiempo de ejecución.
No es necesario cargar todo al inicio: active solo lo que necesite, cuando lo necesite.

### 🌐i18n/L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / y más.
Configure `UAGENT_LANG` para cambiar. Consulte [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) para agregar una nueva configuración regional.

Las traducciones de este README están disponibles en [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variables de entorno cifradas

Almacene claves y secretos de API en `.env.sec`, un archivo `.env` cifrado.
Administrar con `uag_envsec`.

## Configuración y detalles

- **Variables de entorno**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Asistente de configuración**: `python -m uagent.setup_cli`
- **Entorno cifrado**: `uag_envsec` — cifra `.env` como `.env.sec`
- **API de respuestas**: establezca `UAGENT_RESPONSES=1` para el modo API de respuestas (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Habilitado automáticamente para Sakana AI (Fugu).
- **Documentos del desarrollador**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Pequeños consejos de LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filosofía del proyecto

uag aspira a ser **su IA, en su máquina, en sus términos.**

- Sin dependencia de SaaS: se ejecuta localmente
- Sin dependencia de proveedor: cambie en cualquier momento
- Sin bloqueo de interfaz de usuario: CLI / GUI / Web / A2A
- Sin bloqueo de funciones: amplíelo con herramientas y habilidades

Una experiencia de agente de IA gratuita, sin dependencia de proveedores.
