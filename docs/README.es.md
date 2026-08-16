<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Puerta de enlace universal de IA</h1>

<p align="center">
 <b>U</b>I <b>I <b>Gateway universal: su entorno, su libertad.
</p>

<p align="center">
 Operaciones de archivos / Búsqueda Web / Generación y análisis de imágenes / Extracción de PDF y Excel / Control de IoT / Integración MCP<br>
 24 proveedores / 3 UI / Ejecución de herramientas paralelas / Mercado de habilidades de agentes
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Lee esto en tu idioma</a>
</p>

______________________________________________________________________

## ¿Por qué uag?

**Libérese del bloqueo del proveedor.** La mayoría de los asistentes de IA lo vinculan a un proveedor o servicio en la nube específico. uag es diferente.

- **Se ejecuta localmente** en su máquina. Tus datos permanecen contigo (excepto API llamadas que realices).
- **Libertad de proveedor**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 proveedores, todos accesibles desde una única interfaz. Intercambie entre ellos reconfigurando las variables de entorno: sin reinstalación ni migración.
- **222 herramientas**: E/S de archivos, búsqueda web, generación de imágenes, Gmail, escaneo de dispositivos BLE, integración de servidor MCP — **130 están marcadas estáticamente como paralelas seguras** (hasta 8 se ejecutan simultáneamente a través del grupo de subprocesos, configurable a través de `UAGENT_PARALLEL_WORKERS`). Cuando LLM activa varias llamadas a herramientas a la vez, uag las paraleliza automáticamente.
- **3 UI + A2A**: CLI, GUI, Web y protocolo de agente a agente. Mismo motor, cualquier interfaz.
- **Listo para IoT**: SwitchBot, ECHONET Lite, Matter, UPnP: controle sus dispositivos domésticos a través de IA.
- **Habilidades de agente**: instale habilidades del mercado creadas por la comunidad. Extiende uag sin fin.

uag es **tu asistente de IA según tus términos**. No vinculado a un proveedor, no vinculado a una interfaz, no vinculado a una plataforma.

## Inicio rápido

```bash
pip install uag
uag
```

En el primer inicio, el asistente de instalación lo guía a través de la configuración del proveedor.
Consulte [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) para conocer todos los entornos variables.

## Computer Use

Computer Use es opcional y admite tanto un tiempo de ejecución de navegador Playwright
visible como un tiempo de ejecución de escritorio. Cuando está habilitado, ambos tiempos de ejecución se crean y registran;

```bat
set UAGENT_COMPUTER_USE=1
```

Use `desktop` para seleccionar el tiempo de ejecución del escritorio del sistema operativo. Runtime recursos están
cerrados juntos en la salida normal, `Ctrl-C` y el cierre del proceso. Establezca
`UAGENT_COMPUTER_HEADLESS=1` para pruebas de humo o CI basadas en navegador.
Consulte [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
para conocer los detalles de integración y seguridad.

## Voz en tiempo real y AEC3

El modo de voz en tiempo real admite OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API y Amazon Bedrock Nova Sonic con micrófono full-duplex y E/S de altavoz. El backend AEC3 `pywebrtc-audio` requerido se instala automáticamente, y el SDK de transmisión bidireccional opcional de Bedrock se instala automáticamente solo cuando se selecciona el proveedor de Bedrock:

```bash
python scheck.py realtime
```

La tubería AEC3 recibe la señal del micrófono real (`cerca`) y el audio realmente entregado al altavoz (`lejos`) para que el asistente pueda escuchar mientras habla. Habilite el diagnóstico solo cuando investigue problemas de audio:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Llamada de función en tiempo real

OpenAI Realtime admite una integración de llamada de función con seguridad limitada. El adaptador en tiempo real actual expone automáticamente `get_current_time` de solo lectura. Las herramientas destructivas y los controles de dispositivos no se exponen sin una lista de permitidos explícitos y un flujo de confirmación. Grok en tiempo real usa un adaptador separado y no usa esta ruta de llamada de función específica de OpenAI.

## Funciones

### 🧠 Arquitectura multiproveedor

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Todos los proveedores comparten el mismo conjunto de herramientas e interfaz. Cambie configurando `UAGENT_PROVIDER`: sin cambios de código, sin instalaciones separadas.

#### Ollama y llama.cpp

Ollama y llama.cpp son proveedores separados. Ollama utiliza su propio servicio y gestión de modelos, mientras que `llama.cpp` se conecta a un punto final compatible con `llama-server` OpenAI:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

El proveedor llama.cpp utiliza la ruta compatible con Finalizaciones de Chat. Mantenga `UAGENT_RESPONSES=0` a menos que se configure un proxy compatible.

### ⚡ Ejecución de herramientas paralelas

Cuando LLM solicita varias herramientas simultáneamente, uag **las paraleliza automáticamente**.
130 herramientas están marcadas estáticamente como `x_parallel_safe` y se ejecutan simultáneamente a través de un `ThreadPoolExecutor` (8 subprocesos de forma predeterminada; configure `UAGENT_PARALLEL_WORKERS` para cambiar).

**Ejemplo**: Pregunte "Consulte el clima en las capitales nórdicas" → LLM activa `search_web` × 5 países → las 5 búsquedas se ejecutan en paralelo → resultados recopilados en un lote.

El recuento actual se basa en módulos de herramientas que definen una `TOOL_SPEC` (actualmente 222, incluidas las 2 herramientas respaldadas por Rust en `src/uagent/tools_rust/`). `http_request` utiliza seguridad sensible a los métodos: las llamadas `GET`/`HEAD`/`OPTIONS` pueden ejecutarse en paralelo, mientras que los métodos de escritura permanecen en serie.

Las herramientas de solo lectura (búsqueda de archivos, cálculo hash, listado de directorios, traducción, consultas de bases de datos, etc.) están agresivamente paralelizadas.

### 🧩 Sistema de complementos (compatible con código Claude)

uagent implementa un **Claude Sistema de complementos compatible con código**. Los complementos agrupan habilidades, agentes, servidores MCP, enlaces y más en directorios independientes con un manifiesto `.claude-plugin/plugin.json`.

**Componentes compatibles**: habilidades, subagentes, servidores MCP, enlaces (12 eventos de ciclo de vida), comandos de barra diagonal, estilos de salida, configuración de usuario, dependencias, canales, Marketplaces

**CLI comandos**:

```
:lista de complementos # Listar complementos instalados
:instalación de complementos <fuente> [--scope] # Instalar (dir/zip/git/http)
:instalación de complementos <nombre>@<mercado> # Instalar desde Marketplace
:eliminación de complementos <nombre> # Desinstalar
:habilitar/deshabilitar complementos <nombre> # Alternar
:plugin Marketplace agregar/eliminar/listar # Administrar mercados
:plugin init <nombre> # Scaffolding nuevo complemento
```

Consulte [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) para obtener la documentación completa.

### 🔄 Continuidad de sesión

- **Cambiar de proveedor a mitad de sesión** con `UAGENT_PROVIDER`: se conserva el historial de conversaciones.
- **Recargar sesiones pasadas** con `:load <index>`: continuar donde lo dejaste.
- **Almacenamiento en caché de resultados de herramientas** evita la reejecución redundante cuando se repite la misma llamada de herramienta.

### 🛠 229 Herramientas

| Categoría | Herramientas |
|---|---|
| **Operaciones de archivos** | leer/escribir/crear/eliminar/buscar/grep/hash/zip, tipo_archivo, parse_eml (archivos .eml), `alias_ruta` |
| **Web** | fetch_url, search_web, captura de pantalla, browser_playwright, `url_alias`, `public_transit_route` ([guía](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Medios** | generar_imagen, analizar_imagen, img2img, audio_speech, audio_transcribe |
| **Documentos** | Extracción de PDF/PPTX/DOCX/RTF/ODT, extracción estructurada de Excel |
| **Previsión** | Pronóstico de series de tiempo con 9 modelos (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), selección automática de modelo, generación de gráficos, i18n |
| **Comunicación** | gmail_send, gmail_read, bluesky, discord_channel, equipos_webhook, **pybitchat** (BLE Mesh) — consulte [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) y [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Nube + BLE), ECHONET Lite, Matter, UPnP, código_geoinverso |
| **API en la nube** | `aws_api`, `gcp_api`, `azure_api`: operaciones genéricas de AWS, Google Cloud y Azure API; las operaciones de escritura requieren confirmación explícita |
| **Herramientas de desarrollo** | workspace_status, git_ops, git_review, security_scan, cover_report, python_compile, lint_format, run_tests, db_query, **29 navegadores de código fuente (familia idx)** |
| **MCP** | Conéctese a servidores MCP externos, enumere herramientas, ejecute — [Guía de OAuth/Proxy](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Comunicación de agente a agente (con otras instancias uag o servidores compatibles con A2A) |
| **Sistema** | vars env, especificaciones del sistema, hora, cálculo de fecha, [cantidades](docs/QUANTITIES.md), [distancia_geodésica](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Navegación de origen** | **29 herramientas idx** para Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile: obtenga un índice de función/clase o una definición específica sin leer el archivo completo |

#### Revisión y cobertura del repositorio

- `workspace_status`: informa la rama Git del espacio de trabajo activo, cambios, estado de sincronización ascendente, tiempo de ejecución de Python y marcadores comunes del proyecto sin modificar archivos.
- `git_review`: resume los cambios de Git, archivos riesgosos, candidatos de prueba y hallazgos secretos sin exponer valores secretos.
- `security_scan`: escanea los archivos del repositorio en busca de secretos probables y archivos de configuración riesgosos.
- `coverage_report`: ejecuta y normaliza la cobertura para Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift y Dart/Flutter.
- Las dependencias de cobertura que faltan se pueden instalar automáticamente cuando se solicita la ejecución; `dry_run` nunca instala paquetes.

Consulte [Herramientas de análisis de repositorio](docs/REPOSITORY_TOOLS.md) para obtener parámetros, resultados y detalles de seguridad.

Consulte [Alias de ruta y URL](docs/PATH_URL_ALIASES.md) para acortar rutas de archivo repetidas y URL en los argumentos de la herramienta.

### 🖥 4 interfaces + código VS Extensión

| Modo | Comando | Propósito |
|---|---|---|
| **CLI** | `uag` | Operación rápida basada en terminal |
| **GUI** | `uagg` | Interfaz de usuario de escritorio a través de tkinter |
| **Web** | `uagw` | Acceso basado en navegador |
| **A2A Servidor** | `uagá` | Protocolo Agent2Agent para comunicación multiagente |
| **Código VS** | — | [Extensión](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) con panel de chat, explicación, refactorización, corrección de errores y vista de árbol de herramientas |

Consulte [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) para obtener detalles sobre la extensión VS Code: instalación, comandos, combinaciones de teclas y configuración.

### 🏠 Control de dispositivos IoT

- **BACnet**: lectura/escritura de dispositivos BACnet/IP (HVAC, iluminación, medidores de energía). Suscripción COV para notificaciones push
- **Modbus TCP**: lectura/escritura de registros de retención/entrada y bobinas. Monitoreo de cambios basado en sondeo
- **OPC UA**: explore el espacio de direcciones, lea/escriba variables, suscríbase a cambios de datos
- **SwitchBot**: control de lotes en la nube y escaneo/control BLE. Suscripción basada en sondeo
- **ECHONET Lite**: descubra, controle y suscríbase a notificaciones INF de electrodomésticos (aire acondicionado, luces, calentadores de agua, etc.)
- **Materia**: control de lectura/escritura + suscripción de atributos para monitoreo de cambios de estado
- **UPnP**: descubrimiento de dispositivos y reenvío de puertos IGD

Ver [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` para explorar [SkillsMP](https://skillsmp.com) y [ClawHub](https://clawhub.ai) para la comunidad habilidades.
Instala y amplía las capacidades de uag sobre la marcha.

### 🤖 Piloto automático (`:auto`)

uag puede **perseguir de forma autónoma un objetivo en múltiples rondas de LLM**. Perfecto para tareas complejas de varios pasos que necesitan un refinamiento iterativo.

- **Cómo funciona**: cada ronda tiene una consulta principal (Paso A) seguida de un criterio del revisor (Paso B) que decide "¿COMPLETAR o CONTINUAR?"
- **Mismo proveedor, mismo API**: el criterio del revisor utiliza la misma ruta de código que la consulta principal, incluido el soporte de Respuestas API.
- **Juez separado LLM** (opcional): configure `UAGENT_AP_PROVIDER` para usar un proveedor/modelo diferente para el revisor (por ejemplo, use un modelo más económico para juzgar).
- **Salir en cualquier momento**: presione la tecla `x` para detenerse inmediatamente, incluso a mitad de la respuesta. O deje que el revisor decida cuándo se cumple el objetivo.
- **Configurable**: `--max-rounds N` para controlar el presupuesto.

Consulte [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) para obtener la documentación completa.

### 🧩 Estado del lote Manager

uag puede realizar un seguimiento del progreso en tareas de varios archivos de larga duración. Cuando LLM procesa docenas de archivos, `batch_state` conserva la lista de archivos pendientes, completados y fallidos en el disco. Si la sesión finaliza o una ronda se agota, la siguiente ejecución se reanuda desde donde se detuvo: no se pierde nada.

### 🛡 Human-in-the-Loop

`human_ask` permite que LLM haga una pausa y solicite su confirmación antes de realizar operaciones destructivas (eliminación de archivos, sobrescrituras, comandos de shell). Tú mantienes el control.

### 🛑 Interrumpir (tecla C / botón Detener)

Detener la generación de respuesta de LLM en cualquier momento e inyectar un comando de parada nuevamente al LLM.

| Interfaz | Cómo interrumpir |
|---|---|
| **CLI** | Presione la tecla `c` durante la transmisión de LLM: la respuesta actual se detiene y `"Detener"` se envía como un mensaje de usuario para que LLM responda en consecuencia |
| **UI WEB** | Haga clic en el botón rojo **■ Detener** (aparece automáticamente durante el procesamiento de LLM) |
| **Escritorio GUI** | Haga clic en el botón rojo **■** (aparece automáticamente durante el procesamiento de LLM) |

La interrupción funciona como "inyección rápida": en lugar de simplemente abortar, envía `"Detener"` al LLM como un mensaje de usuario, lo que le permite concluir o reconocer la interrupción con gracia.

Presione la tecla `x` para salir del modo de piloto automático (consulte [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Automatización del navegador y Web Inspector

Dos herramientas complementarias basadas en Playwright:

- **browser_playwright**: automatiza sesiones reales del navegador: navega, haz clic y completa formularios, extraer datos, manejar flujos de varias páginas. Funciona sin cabeza o con cabeza.
- **playwright_inspector**: graba transiciones del navegador, captura instantáneas de DOM y capturas de pantalla en cada paso. Útil para depurar interacciones web o auditar cambios de páginas a lo largo del tiempo.

### 🔄 Carga dinámica de herramientas

`tool_catalog` y `tool_load` le permiten descubrir y habilitar herramientas en tiempo de ejecución.
No es necesario cargar todo al inicio: active solo lo que necesita, cuando lo necesita.

### 🦀 Herramientas nativas de Rust

`uuid_gen` y `slugify` se implementan en Rust (a través de PyO3) para mejorar el rendimiento.
Se cargan directamente desde un `.pyd` prediseñado — **no se requiere `pip install`**.

Los desarrolladores externos también pueden enviar herramientas basadas en Rust: coloque un `.pyd` al lado del
wrapper `.py`, use `load_rust_pyd()` de `uagent.tools.rust_helper`, y
los usuarios obtienen la herramienta sin dependencias adicionales. Ver
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Inglés / 简体中文 /繁體中文 / 한국어 / Español / Français / Русский / y más.
Configure `UAGENT_LANG` para cambiar. Consulte [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) para agregar una nueva configuración regional.

Las traducciones de este README están disponibles en [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variables de entorno cifradas

Almacene API claves y secretos en `.env.sec`, un archivo `.env` cifrado.
Administre con `uag_envsec`.

## Configuración y detalles

- **Variables de entorno**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Asistente de configuración**: `python -m uagent.setup_cli`
- **Entorno cifrado**: `uag_envsec` — cifrar `.env` como `.env.sec`
- **Respuestas API**: Establezca `UAGENT_RESPONSES=1` para el modo Respuestas API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Habilitado automáticamente para Sakana AI (Fugu).
- **Documentos del desarrollador**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Flujo de herramientas**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md): cómo se envían las herramientas a los LLM (máscara de género, catálogo de herramientas, GPT-5.4+ búsqueda de herramientas nativa)
- **Pequeños LLM consejos**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Project Philosophy

uag aspira a ser **su IA, en su máquina, en sus términos.**

- Sin dependencia de SaaS: se ejecuta localmente
- Sin bloqueo de proveedor: cambie en cualquier momento
- Sin bloqueo de interfaz de usuario: CLI / GUI / Web / A2A
- Sin bloqueo de funciones: amplíelo con herramientas y habilidades

A experiencia gratuita de agente de IA, libre de dependencia de proveedores.

### ✨ Cree sus propias herramientas

Escribir una nueva herramienta para uag es sencillo: cree un único archivo `.py` con
`TOOL_SPEC` y `run_tool()`, colóquelo en `UAGENT_EXTERNAL_TOOLS_DIR` y
estará disponible de inmediato. Para los desarrolladores de Rust, envíe un `.pyd` prediseñado con
cero dependencias adicionales para los usuarios.

Consulte [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
para obtener la guía paso a paso.

## Contribuyendo

¡Las contribuciones son bienvenidas! Informes de errores, sugerencias de funciones, mejoras de documentación, traducciones y solicitudes de extracción: todo ello se agradece.

- **Problemas**: abra una edición GitHub para errores o solicitudes de funciones.
- **Solicitudes de extracción**: bifurque el repositorio, realice sus cambios y envíe un PR. Consulte [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) para conocer la configuración y las pautas de desarrollo.
- **Traducciones**: README traducciones y adiciones de configuración regional son bienvenidas. Consulte [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Herramientas y habilidades**: se pueden contribuir nuevos complementos de herramientas y habilidades de agente a través del mercado.

### Comprobaciones de desarrollo (antes de PR)

Instale primero las dependencias de solo prueba. Se mantienen fuera de la lista de dependencias del tiempo de ejecución:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Ejecute las mismas comprobaciones utilizadas por GitHub Acciones antes de presionar:

```bash
python -m ruff check src tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Para una iteración local más rápida, ejecute solo las pruebas afectadas:

```bash
pytest -q tests/<área_affectada>
```

Comprobaciones adicionales cuando sea relevante:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Después de las ediciones locales (`.po`): `python scripts/compile_locales.py` y `python scripts/po_qc_summary.py`.

Runtime política (detalles en [DEVELOP.md](https://github.com/awak7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): los ayudantes generan en lugar de `sys.exit`; el host de la herramienta convierte la herramienta `SystemExit`/`Exception` en cadenas de error para que una sola herramienta no pueda finalizar el proceso. Las salidas rápidas de inicio siguen siendo intencionales.

## Arquitectura e invariantes operativas

Consulte [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para conocer los contratos duraderos que cubren el ciclo de vida A2A, contextos I18N, instalación de dependencia opcional, seguridad de herramientas, capacidades del proveedor, límites de confianza de OAuth, eventos estructurados y verificación de aceptación.

## Enterprise Policy Engine

Se admiten políticas a nivel de organización para herramientas, proveedores, credenciales, servidores MCP, redes, habilidades y complementos. Establezca `UAGENT_POLICY_FILE` en un archivo de política JSON/YAML; consulte [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) para ver ejemplos de configuración, roles, confirmación y listas de permitidos.

### Runtime recuperación y orquestación

Consulte [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) para recuperación duradera, ejecución con reconocimiento de dependencias, orquestación de múltiples agentes y uso remoto de A2A.

Consulte [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) para la coordinación del arrendamiento del líder en tiempo de ejecución compartido.
