# USO (Opciones de línea de comandos)

Este documento describe las opciones de línea de comandos disponibles para los puntos de entrada de uag.

______________________________________________________________________

## Puntos de entrada

| Comando | Módulo de Python | Interfaz |
|---|---|---|
| `uag` | `python -m uagent` | CLI (bucle de entrada estándar) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Servidor web (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | servidor A2A HTTP |

______________________________________________________________________

## Opciones de inicio de la CLI (`uag`)

### `--workdir` / `-C <ruta>`

Directorio de trabajo. Si no se especifica, se utiliza por defecto la variable de entorno `UAGENT_WORKDIR` y, en su defecto, el directorio actual.
Si el directorio no existe, se crea.

### `--tool-genre-mask <int>`

Máscara de bits de género de herramienta. Cuando se especifica, se omite el mensaje interactivo de selección de género.

| Bit | Género | Descripción |
|-----|-------|-------------|
| 1 | basic | Herramientas básicas de archivos y chat |
| 2 | comm | Herramientas de comunicación (Bluesky, Teams) |
| 4 | office | Herramientas de suite ofimática (Excel, PDF, PPTX) |
| 8 | devel | Herramientas de desarrollo (git, lint, compile) |
| 16 | iot | Herramientas para dispositivos IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Herramientas de ejecución de comandos |
| 64 | external | Herramientas de complementos externos |
| 128 | media | Generación y análisis de imágenes y audio |
| 256 | file | Herramientas de gestión de archivos |
| 512 | index | Herramientas de navegación por código fuente e índices |
| 1024 | dev | Herramientas para desarrolladores y repositorios |
| 2048 | web | Herramientas web y de navegador |
| 4096 | utility | Herramientas de utilidades y soporte |
| 8191 | all | Todas las herramientas |

Ejemplos:

```
uag --tool-genre-mask 1 # solo básicas
uag --tool-genre-mask 9 # básico + desarrollo (1 + 8)
uag --tool-genre-mask 8191    # todas las herramientas
```

### `--use-tool` / `--no-use-tool`

Activa o desactiva el envío de definiciones de herramientas a LLM. Anula la variable de entorno `UAGENT_USE_TOOL`.

- `--use-tool` activa el envío de herramientas.
- `--no-use-tool` desactiva el envío de herramientas.

Cuando está desactivado, el LLM no recibe definiciones de herramientas y no puede llamar a ninguna herramienta.

### `--computer-use` / `--no-computer-use`

Activa o desactiva el uso del ordenador. Anula la variable de entorno `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <mensaje>`

Inserta un mensaje en el LLM al inicio y sale una vez finalizado. Esto implica `--non-interactive`.

### `--embedded`

Modo integrado para implementaciones con restricciones o en las que la reproducibilidad es fundamental.

- Desactiva el almacén de sesiones.
- Oculta las herramientas de gestión de herramientas (`tool_catalog`, `tool_load`, `unload_tool`) a menos que se habiliten explícitamente.
- Ignora `--tool-genre-mask`; utiliza `--enable-tool` para cargar herramientas de forma explícita.

### `--enable-tool <nombre>`

Carga explícitamente una herramienta al inicio. La opción se puede repetir, y también se aceptan nombres separados por comas.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Se conserva el orden especificado y se refleja en el orden de las herramientas que se presenta a LLM. Las herramientas habilitadas explícitamente quedan bloqueadas para evitar su descarga automática.

### `--plugin-dir <ruta>`

Carga los complementos desde el directorio especificado. La opción se puede repetir.

______________________________________________________________________

## Opciones exclusivas de la CLI

### `--inject-message-auto <opciones-del-objetivo>`

Inicia el piloto automático a partir de un objetivo inyectado no interactivo. El valor utiliza las mismas opciones que `:auto`; hay que poner entre comillas el valor completo cuando contenga opciones.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Ordenar los elementos --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Ordenar los elementos --infinite"
```

El modo normal utiliza la ruta de decisión del revisor. Establece `UAGENT_AUTO_SENTINEL=1` para activar el modo de centinela único LLM. En ese modo, el LLM de destino debe terminar cada respuesta con exactamente uno de los siguientes:

- `<AUTO_CONTINUE>` — ejecutar otra ronda
- `<AUTO_COMPLETE>` — finalizar con éxito

Los marcadores ausentes o no válidos detienen el piloto automático de forma segura. Esto sigue ejecutando el LLM de destino; solo evita la llamada adicional al revisor LLM.

### `--non-interactive`

Modo no interactivo. No inicia el bucle de stdin. Si se proporciona una ruta de archivo como argumento posicional, se procesa y el programa sale inmediatamente.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Opciones del servidor web (`uagw`)

### `--host <address>`

Dirección de enlace para el servidor web (por defecto: `127.0.0.1`, se puede anular mediante `UAGENT_WEB_HOST`).

Por defecto, el servidor web escucha únicamente en localhost (`127.0.0.1`). Para que sea accesible desde otros equipos de la red, utiliza `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Selecciona los géneros de herramientas utilizando la misma máscara de bits descrita anteriormente. Cuando se especifica, se omite la solicitud interactiva de género.

### `--use-tool` / `--no-use-tool`

Activa o desactiva el envío de definiciones de herramientas a LLM. Anula `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Activa o desactiva el uso del ordenador. Anula `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Ejecuta solo API sin plantillas HTML ni archivos frontend estáticos.

### `--embedded`

Desactiva el almacén de sesiones y oculta las herramientas de gestión de herramientas (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Opciones del servidor A2A (`uaga`)

### `--host <address>`

Dirección de enlace para el servidor A2A HTTP (por defecto: `0.0.0.0`, se puede sobrescribir mediante `UAGENT_A2A_HOST`).

### `--port <número>`

Número de puerto del servidor A2A HTTP (por defecto: `8765`, se puede anular mediante `UAGENT_A2A_PORT`).

### `--reload`

Activa la recarga en caliente al realizar cambios en el código (por defecto: desactivada, se puede anular mediante `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Selecciona los géneros de herramientas utilizando la máscara de bits descrita anteriormente. Cuando se especifica, se omite la solicitud interactiva de género.

### `--use-tool` / `--no-use-tool`

Activa o desactiva el envío de definiciones de herramientas a LLM. Anula `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Activa o desactiva el uso del ordenador. Anula `UAGENT_COMPUTER_USE`.

### `--embedded`

Desactiva el almacén de sesiones y oculta las herramientas de gestión de herramientas (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Variables de entorno relacionadas

| Variable | Descripción |
|---|---|
| `UAGENT_PROVIDER` | Nombre del proveedor LLM (obligatorio al inicio) |
| `UAGENT_*_API_KEY` | Clave API para el proveedor seleccionado |
| `UAGENT_WORKDIR` | Directorio de trabajo predeterminado |
| `UAGENT_WEB_HOST` | Dirección de enlace del servidor web (por defecto: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Dirección de enlace del servidor de A2A (por defecto: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Puerto del servidor de A2A (por defecto: `8765`) |
| `UAGENT_A2A_RELOAD` | Habilita la recarga en caliente de A2A de forma predeterminada |
| `UAGENT_USE_TOOL` | Deshabilita las herramientas cuando se establece en `0`, `false`, `no` u `off` |
| `UAGENT_COMPUTER_USE` | Habilita o deshabilita el uso del ordenador de forma predeterminada |
| `UAGENT_SESSION_STORE` | Habilita o deshabilita el almacenamiento de sesiones; El modo integrado impone el valor `0` |
| `UAGENT_PLUGIN_DIRS` | Directorios adicionales de búsqueda de complementos |
| `UAGENT_AUTO_SENTINEL` | Activa el modo centinela de piloto automático único de LLM cuando se establece en `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Número máximo de llamadas consecutivas a herramientas nuevas (por defecto: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Número máximo de rondas de LLM por herramienta por operación de usuario (por defecto: `200`) |
| `UAGENT_SHRINK_CNT` | Umbral opcional de reducción automática en los mensajes (`0`/sin configurar = desactivado) |
| `UAGENT_SHRINK_KEEP_LAST` | Mensajes que se conservarán tras la reducción (por defecto: `20`) |
| `UAGENT_LANG` | Idioma de la interfaz (`ja`, `en`, etc.) |

Para ver la lista completa de variables de entorno, consulta [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Ejemplos

### Inicio mínimo con OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Ollama local solo con herramientas básicas

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Servidor web en todas las interfaces

```
establecer UAGENT_WEB_HOST=0.0.0.0
uagw
```

o

```
uagw --host 0.0.0.0
```

### Servidor A2A en localhost con puerto personalizado

```
uaga --host 127.0.0.1 --port 8080
```

### Desactivar herramientas para un modelo pequeño

```
uag --no-use-tool --tool-genre-mask 1
```

### Procesamiento de archivos no interactivo

```
uag --non-interactive README.md
```
