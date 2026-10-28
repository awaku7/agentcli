<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Tus modelos de IA. Tus herramientas. Tu entorno.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Otros idiomas</a></p>

---

**UAG es un entorno de ejecución de agentes de IA de código abierto que prioriza el funcionamiento local.** Conecta el modelo de lenguaje que prefieras con las herramientas y los sistemas que utilizas. Permite trabajar con código, archivos, navegadores, servicios y dispositivos desde una interfaz coherente, sin vincular tus procesos a un único proveedor de modelos.

| **Elige tu modelo** | **Conecta herramientas reales** | **Conserva el control** |
| :--- | :--- | :--- |
| Modelos alojados o locales: OpenAI, Claude, Gemini, Grok, Bedrock, Ollama, entre otros | Archivos, código, web, MCP, Agent Skills, plugins, servicios en la nube e IoT | Ejecución local, confirmación humana, almacenamiento de credenciales y políticas configurables |

> UAG es **la capa de ejecución de agentes, no un proveedor de modelos**. Las solicitudes a modelos externos y servicios conectados dependen de tu configuración. «Local-first» no significa que todo funcione sin conexión ni que todas las operaciones estén aisladas de forma predeterminada.

## Inicio rápido
<!-- README-SYNC:quick-start -->

Necesitas **Python 3.11 o posterior**. Instala UAG desde [PyPI](https://pypi.org/project/uag/) e inicia la interfaz de terminal:

~~~bash
python -m pip install --upgrade uag
uag
~~~

La primera vez que lo ejecutes, el asistente te ayudará a elegir un proveedor y configurar sus credenciales. También puedes utilizar variables de entorno o el almacén de credenciales. Para instalar de antemano más dependencias de proveedores y herramientas:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Prueba a pedirle lo siguiente:

~~~text
> ¿Qué ha cambiado en este repositorio Git? Resume los riesgos.
> Busca la documentación más reciente de esta biblioteca y explica los pasos para migrar.
> Examina estos archivos y prepara un informe breve.
> :help
~~~

Si acabas de llegar, consulta la guía de instalación para Windows, con los pasos de Git y entornos virtuales, y la referencia de configuración: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Interfaces
<!-- README-SYNC:interfaces -->

La misma ejecución de agentes y el mismo registro de herramientas sirven para todas las interfaces.

| Interfaz | Inicio | Uso recomendado |
| :--- | :--- | :--- |
| **CLI** | `uag` | Trabajo en terminal y automatización |
| **Escritorio** | `uagg` | Conversaciones en una aplicación nativa |
| **Web** | `uagw` | Conversaciones y salas en el navegador |
| **A2A** | `uaga` | Integración entre agentes |
| **VS Code** | [Guía de la extensión](VSCODE.md) | Trabajo junto al código fuente |

Las interfaces de escritorio y web necesitan dependencias adicionales que no incluye la instalación inicial `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

El servidor web también puede intentar instalar FastAPI y Uvicorn al iniciarse. Si los instalas antes, no dependerás de la instalación automática. Consulta: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Qué puedes hacer con UAG
<!-- README-SYNC:capabilities -->

| Capacidad | Qué ofrece UAG |
| :--- | :--- |
| **Flujos independientes del modelo** | Cambiar entre proveedores alojados y locales mediante `UAGENT_PROVIDER`, sin reescribir herramientas |
| **Código y archivos** | Navegar por repositorios, revisar Git, ejecutar analizadores y pruebas, operar con archivos y automatizar navegadores |
| **Herramientas extensibles** | Más de 200 herramientas, descubrimiento dinámico mediante `tool_catalog` y `tool_load`, herramientas propias en Python o Rust |
| **Agentes conectados** | Servidores MCP, A2A, plugins compatibles con Claude Code, Agent Skills y subagentes |
| **Trabajos prolongados** | Piloto automático, lecturas independientes en paralelo, tareas programadas, recuperación tras reinicios y sesiones persistentes |
| **Más allá del terminal** | Servicios de nube y comunicación, documentos, medios, voz en tiempo real y protocolos IoT compatibles |

### Un mismo motor para muchas integraciones
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**Ejemplos de proveedores admitidos:** aparecen a continuación. Consulta la referencia de configuración para los ajustes específicos.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Personalización con skills y plugins
<!-- README-SYNC:extensions -->

Amplía UAG sin modificar el núcleo. Instala Agent Skills desde SkillsMP o ClawHub, conecta servidores MCP o carga plugins compatibles con Claude Code que incluyan herramientas, skills, agentes y hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Las herramientas propias pueden definir `TOOL_SPEC` y `run_tool()`; también se admiten herramientas basadas en Rust. Empieza por las guías siguientes: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Diseñado para tareas reales
<!-- README-SYNC:workflows -->

### Contexto y memoria
<!-- README-SYNC:context-memory -->

Los resultados grandes de las herramientas pueden guardarse como **artefactos** en lugar de ocupar el contexto activo del modelo. El agente recupera después solo la parte necesaria mediante `artifact_read`. Las sesiones se almacenan en SQLite de forma predeterminada, con búsqueda en el historial y revisión explícita de memoria.

- [Context compression](CONTEXT_COMPRESSION.es.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatización y colaboración
<!-- README-SYNC:automation -->

UAG permite ejecutar lecturas independientes en paralelo, coordinar varios agentes, recuperar sesiones y usar el piloto automático para tareas con varias rondas. Inícialo con `:auto`; pulsa **F12** para interrumpir la respuesta actual y solicitar que se detenga el piloto automático.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Seguridad y observabilidad
<!-- README-SYNC:security -->

Las operaciones delicadas pueden requerir confirmación mediante `human_ask`. Las credenciales se pueden guardar en el gestor del sistema operativo o en archivos cifrados. La interfaz web admite inicio de sesión OIDC y control de acceso si se configuran. Las trazas y métricas de OpenTelemetry son **opcionales**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Estas medidas son configurables y **no garantizan** que cualquier herramienta se ejecute aislada en un entorno protegido. Revisa las guías de despliegue y políticas antes de exponer UAG a usuarios o redes que no sean de confianza.

### Idiomas, dispositivos y voz
<!-- README-SYNC:languages -->

UAG incluye recursos para **38 configuraciones regionales** (inglés y otras 37 traducciones), integraciones opcionales de voz bidireccional y herramientas para SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP y OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Documentación
<!-- README-SYNC:documentation -->

Utiliza las guías siguientes para empezar y profundizar en cada tema:

| Empieza aquí | Más información |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

También puedes explorar el directorio completo de documentación y los demás idiomas: [Documentation](./) · [Other languages](README.translations.md).

## Desarrollo y contribuciones
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Antes de presentar una solicitud de incorporación que modifique **código Python**, ejecuta las pruebas pertinentes y las comprobaciones del proyecto:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Encontrarás las normas y la guía de desarrollo aquí. Se agradecen informes de errores, mejoras de documentación, traducciones, herramientas y contribuciones concretas: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licencia
<!-- README-SYNC:license -->

UAG se distribuye bajo la licencia: [Apache License 2.0](../LICENSE).
