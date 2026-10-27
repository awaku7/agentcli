<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Un agente local. Cualquier modelo. Cualquier herramienta. Tu entorno, tus reglas.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**¿Por qué uag?**

uag es un agente de IA local que conecta el modelo que prefieres con las herramientas que realmente utilizas.
Te ofrece un único entorno de ejecución extensible para archivos, navegadores, bases de código, comunicación,
API en la nube, dispositivos IoT, servidores MCP y flujos de trabajo multiagente.

- **Libertad de proveedores** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek y más.
- **Ejecución local** — el entorno de ejecución del agente y las herramientas permanecen en tu equipo; solo salen de él las llamadas a la API que elijas.
- **Una sola capa de herramientas** — las mismas herramientas funcionan desde la CLI, la GUI de escritorio, la interfaz web, VS Code y A2A.
- **Paralelismo por diseño** — las operaciones independientes de solo lectura pueden ejecutarse simultáneamente.
- **Extensible** — añade herramientas, plugins, Agent Skills, servidores MCP y herramientas respaldadas por Rust sin cambiar el núcleo.
- **Consciente de la seguridad** — las acciones destructivas, credenciales, controles de dispositivos y escrituras de red admiten confirmación explícita y controles de políticas.

> **En resumen:** uag es el plano de control entre tus modelos de IA y tu entorno real.

> **🧠 Resultados de herramientas adaptados al contexto** — Los resultados de herramientas de gran tamaño se mantienen fuera del contexto del modelo activo siempre que sea posible. uag los almacena como artefactos y, en su lugar, pasa al modelo una vista previa limitada con una referencia estable a Artifact. Esto puede reducir sustancialmente el número de tokens de entrada necesarios para los turnos siguientes cuando una herramienta genera un resultado extenso.
> [Guía detallada de compresión del contexto](CONTEXT_COMPRESSION.es.md)

## Inicio rápido

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

El primer lanzamiento abre el asistente de configuración. Ayuda a configurar un proveedor y guarda los ajustes seleccionados
en tu entorno local.

Para los grupos de funciones habituales:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Las integraciones de plataforma son opcionales. Instala solo lo que necesite tu sistema operativo; consulta

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Interfaces

| Interfaz | Comando | Ideal para |
|---|---|---|
| **CLI** | `uag` | Trabajo rápido centrado en el teclado |
| **GUI de escritorio** | `uagg` | Una experiencia de escritorio nativa |
| **Interfaz web** | `uagw` | Acceso desde el navegador |
| **Servidor A2A** | `uaga` | Comunicación entre agentes |
| **VS Code** | Extension | Explicar, refactorizar, corregir y explorar herramientas en el editor |

Todas las interfaces comparten la misma configuración de proveedor, registro de herramientas, reglas de seguridad y datos de sesión.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Qué puedes crear

Los adaptadores de proveedores abarcan entornos alojados y locales, incluidos:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

Cambia de proveedor con `UAGENT_PROVIDER`; tus herramientas y tu interfaz no cambian.

**Trabajar con tu entorno**

- Leer, crear, editar, buscar, calcular hashes, archivar e inspeccionar archivos
- Revisar cambios de Git, buscar secretos, ejecutar pruebas, aplicar linting, compilar y medir la cobertura
- Navegar por grandes bases de código de Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA y otros lenguajes
- Automatizar navegadores con Playwright, incluidos flujos de varias páginas y descargas

**Conectar servicios y dispositivos**

- **MCP** — conecta servidores de herramientas externos, incluidos servicios con OAuth
- **A2A** — coordina con otros agentes y servidores compatibles
- **Cloud** — acceso a las API de AWS, Google Cloud y Azure, con confirmación para las escrituras
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams y pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA y UPnP
- **Media** — generación y edición de imágenes, transcripción y síntesis de audio, captura de cámara y códigos QR
- **Documents** — análisis de PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL y registros

**IoT y control del mundo físico**

- **SwitchBot** — descubrimiento mediante Cloud y BLE, estado, control, procesamiento por lotes y suscripciones
- **ECHONET Lite** — descubre y controla electrodomésticos japoneses, incluidas las notificaciones INF
- **Matter** — endpoints, clústeres, atributos, historial de estado, suscripciones y control
- **BACnet / Modbus TCP / OPC UA** — lecturas, escrituras, exploración y supervisión de automatización industrial y de edificios
- **UPnP** — descubrimiento de dispositivos, estado WAN y gestión de asignaciones de puertos del router

### Dónde encaja uag

uag se sitúa entre las personas y las interfaces, por un lado, y los modelos, las herramientas y los sistemas del mundo real, por otro.
Coordina la conversación, selecciona capacidades, aplica reglas de seguridad y mantiene el flujo de trabajo reanudable.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugins, Agent Skills y marketplaces

Convierte uag en un agente especializado sin bifurcar el núcleo:

- Instala **plugins compatibles con Claude Code** desde un directorio, ZIP, repositorio Git, fuente HTTP o marketplace
- Agrupa skills, subagentes, servidores MCP, hooks, comandos slash, estilos de salida, dependencias y canales
- Explora capacidades de la comunidad en [SkillsMP](https://skillsmp.com) y [ClawHub](https://clawhub.ai)
- Añade skills y herramientas privadas de la organización localmente mediante `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Consulta la [Guía de desarrollo de plugins](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **Más de 200 herramientas** para archivos, web, multimedia, documentos, código, nube, comunicación e IoT
- **Descubrimiento y carga dinámicos** — usa `tool_catalog` para encontrar capacidades y `tool_load` para activarlas solo cuando sea necesario
- **Inteligencia de código** — `code_map`, navegadores `idx` específicos de cada lenguaje, revisión de Git, ejecución de pruebas, linting, compilación y cobertura
- **Plugins compatibles con Claude Code** con skills, agentes, servidores MCP, hooks, comandos y marketplaces
- **Agent Skills** de SkillsMP y ClawHub
- **Herramientas Python personalizadas** con `TOOL_SPEC` y `run_tool()`
- **Herramientas respaldadas por Rust** para extensiones nativas ligeras

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Diseñado para flujos de trabajo reales

### 🧠 Resultados de herramientas adaptados al contexto

Los resultados de herramientas de gran tamaño se mantienen fuera del contexto del modelo activo siempre que sea posible. uag los almacena como artefactos y, en su lugar, pasa al modelo una vista previa limitada con una referencia estable a Artifact. Esto puede reducir sustancialmente el número de tokens de entrada necesarios para los turnos siguientes cuando una herramienta genera un resultado extenso.

Reanuda conversaciones anteriores con `:load <index>`. Los resultados de las herramientas pueden almacenarse en caché y los proveedores pueden cambiarse
sin reconstruir la aplicación.

[Context compression](CONTEXT_COMPRESSION.es.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Piloto automático

Usa `:auto` para trabajos de varias rondas con un modelo revisor opcional. Establece un límite de rondas con `--max-rounds N`.
Pulsa **F12** para detener el piloto automático o **F12** para detener la respuesta actual.

Las operaciones independientes de solo lectura se ejecutan simultáneamente cuando es seguro. Las búsquedas web, la inspección de archivos,
el análisis de repositorios y cargas similares pueden completarse en paralelo con un grupo de trabajadores configurable
(`UAGENT_PARALLEL_WORKERS`). Las operaciones de escritura siguen serializadas o requieren confirmación.

La continuidad de sesión, la caché de resultados de herramientas, el estado por lotes, la recuperación tras reinicios, la planificación DAG y
la orquestación multiagente hacen que el trabajo complejo sea reanudable en lugar de limitarse a una única ejecución.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privado, multilingüe y consciente de las políticas

`human_ask` pausa antes de realizar acciones sensibles. La eliminación y sobrescritura de archivos, los comandos de shell, los controles de dispositivos,
las operaciones con credenciales y las escrituras de red pueden estar regidos por reglas de confirmación y políticas.

Usa el almacén de credenciales en lugar de colocar secretos de larga duración en los prompts:

La interfaz web incluye inicio de sesión OIDC usando Authorization Code + PKCE, tokens de ID verificados, sesiones del lado del servidor y controles de acceso a proyectos/salas. Las reclamaciones de grupo verificadas de Microsoft Entra ID pueden alimentar políticas de acceso respaldadas por directorios cuando están configuradas. Las implementaciones de Windows Active Directory, OAuth y trusted-proxy pueden integrarse mediante adaptadores de identidad verificados explícitamente; Windows AD requiere un verificador Kerberos/Negotiate específico para la implementación y no está habilitado por defecto.

uag incluye trazas y métricas de OpenTelemetry, independientes del proveedor y de activación opcional, para operaciones de Agent, LLM, herramientas, Context, Memory y recuperación. La observabilidad está deshabilitada de forma predeterminada.

Priorizar la ejecución local no significa que UAG funcione por defecto sin conexión ni que todas las herramientas estén aisladas. Las solicitudes a modelos y servicios externos dependen de la configuración.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Traducción multilingüe

- `translate_text` es compatible con Google Translate y con el cliente oficial de DeepL para Python mediante `provider=auto`, `provider=deepl` o `provider=google`.
- Las definiciones de herramientas están disponibles en 37 configuraciones regionales, además del inglés (38 en total), conservando los marcadores de posición y los identificadores técnicos.

La voz full-duplex está disponible mediante OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
y Bedrock Nova Sonic, con cancelación de eco AEC3 opcional y llamadas de funciones en tiempo real limitadas por seguridad.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Documentación

| Tema | Documentación |
|---|---|
| Variables de entorno | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Arquitectura e invariantes | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Herramientas del repositorio | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Casos de uso de IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Herramientas de comunicación | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Piloto automático | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| OAuth / proxy de MCP | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Extensión de VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Guía del desarrollador | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Flujo de herramientas | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Desarrollo y contribución

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Ejecuta las comprobaciones previas a un PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Para consultar el flujo de desarrollo completo, visita [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Se aceptan informes de errores, ideas de funciones, mejoras de documentación, traducciones, herramientas, skills y pull requests.
Abre un issue o una discusión antes de realizar cambios importantes. Lee la [Guía del desarrollador](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
y ejecuta las comprobaciones anteriores antes de enviar un pull request.

## Licencia

Publicado bajo la [Licencia Apache 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
