# Compresión de contexto y contexto de modelo acotado

uag utiliza varias capas para mantener acotado el contexto de modelo activo. El objetivo es reducir los tokens de entrada innecesarios sin eliminar los archivos, los resultados de las herramientas o los datos de sesión que el usuario aún pueda necesitar.

Este documento describe la implementación actual. También distingue el comportamiento determinista del comportamiento específico del proveedor o asistido por LLM.

## 1. Superficie dinámica de herramientas

No es necesario enviar todas las definiciones de herramientas al modelo en cada turno.

- `tool_catalog` busca entre las capacidades disponibles.
- `tool_load` habilita únicamente las herramientas necesarias para la tarea actual.
- `tool_catalog`, `tool_load` y `unload_tool` siguen estando disponibles como herramientas de gestión.
- Los flujos Responses API compatibles con GPT-5.4 pueden utilizar Tool Search nativo del lado del servidor.
- El modo heredado de Tool Search limita las especificaciones de las herramientas con `tool_catalog` en el lado del cliente.

Esto reduce los tokens de entrada utilizados por los esquemas de herramientas, especialmente en instalaciones con muchas herramientas.

## 2. Los resultados extensos de las herramientas textuales se convierten en artefactos

Cuando el resultado de una herramienta textual supera el umbral de Artifact, uag almacena el resultado completo como un Artifact y envía al modelo una referencia limitada y una vista previa en lugar del texto completo.

Los límites predeterminados son:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

La representación visible para el modelo contiene el nombre de la herramienta, la longitud original, una referencia `artifact://`, la ruta de almacenamiento y una vista previa limitada. El resultado completo sigue estando disponible a través del almacén de Artifact.

El umbral se puede modificar con `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Un valor de `0` desactiva la promoción de Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` controla la política habitual de resultados limitados; `0` desactiva ese límite habitual.

## 3. Recuperación limitada de `Artifact`

La herramienta de infraestructura `artifact_read` recupera únicamente la parte solicitada de un `Artifact`:

- `start_line` selecciona la primera línea.
- `max_lines` tiene un límite de 500.
- `max_chars` tiene un límite de 50 000 caracteres.
- Se pueden utilizar tanto un identificador de Artifact como un URI de `artifact://`.

Esto permite inspeccionar un pequeño intervalo relevante en lugar de reinyectar un archivo completo o el resultado de un comando en el siguiente turno del modelo.

Los nuevos artefactos se almacenan a continuación:

```text
~/.uag/artifacts/
```

Las rutas Artifact heredadas existentes siguen siendo legibles por motivos de compatibilidad.

## 4. Aislamiento de la carga útil binaria

Los datos binarios en línea no se envían como resultado textual de la herramienta al siguiente turno del modelo. Los campos con formato Base64 se sustituyen por un marcador breve como:

```text
[carga binaria omitida del contexto LLM]
```

La interfaz de usuario y los clientes remotos siguen pudiendo recibir archivos adjuntos en memoria, y los archivos guardados siguen estando disponibles a través de sus rutas o referencias Artifact. Esto evita que las imágenes, el audio, las capturas de pantalla y otras cargas binarias sobrecarguen el contexto textual del modelo.

La misma clase de carga binaria se depura antes de su persistencia en SQLite y JSONL, lo que impide que vuelva a aparecer como una carga de gran tamaño tras la recarga de la sesión.

## 5. Compresión automática del historial

uag puede comprimir el historial de conversaciones más antiguo cuando el recuento de mensajes o el recuento estimado de tokens alcanza el límite configurado.

La política de compresión utiliza:

- el número de mensajes que no son del sistema;
- la ventana de contexto resuelta del modelo, cuando esté disponible;
- `UAGENT_SHRINK_KEEP_LAST` (20 por defecto);
- `UAGENT_SHRINK_MAX_TOKENS` o una sustitución específica del modelo;
- `UAGENT_SHRINK_CNT`; y
- `UAGENT_SHRINK_RATIO` (0,5 por defecto cuando se conoce una ventana de contexto).

Se puede especificar un límite específico del modelo de la siguiente forma:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

No se vuelve a generar un resumen anterior en cada turno. La histéresis requiere que se acumule suficiente historial nuevo, o que se produzca otro desbordamiento del presupuesto de tokens, antes de que la compresión se ejecute de nuevo.

## 6. Resúmenes de historial asistidos por LLM

Cuando la compresión automática utiliza el LLM, los mensajes más antiguos del usuario, del asistente y de las herramientas se resumen en un mensaje del sistema de forma continua, mientras que se conserva la cola más reciente.

Los historiales largos se pueden resumir por partes. Los controles relevantes son:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

El resumen se desplaza hacia adelante en lugar de crear una secuencia ilimitada de mensajes de resumen. Se trata de una operación asistida por LLM y puede requerir solicitudes adicionales al proveedor.

## 7. Compresión determinista de reserva

Si no se dispone de un resumen LLM, uag puede conservar los mensajes del sistema iniciales y solo los mensajes más recientes. Los límites de las llamadas a herramientas se reparan para que el historial resultante no comience ni termine con una llamada a herramienta huérfana.

El cargador y el depurador también eliminan las entradas no relevantes para el modelo o inválidas, incluidos los mensajes exclusivos de la interfaz de usuario, los mensajes de control internos, las líneas de registro dañadas, los roles no compatibles, los resultados de herramientas huérfanos y los bloques de llamadas a herramientas incompletos.

Cuando se recarga una sesión, se restaura el indicador actual del sistema y solo se conservan los mensajes del sistema inyectados que sean relevantes, como el contexto de una habilidad o un gancho.

## 8. Recuperación por desbordamiento de contexto

Si un proveedor informa de que se ha superado la ventana de contexto, uag identifica un mensaje reciente de gran tamaño en el historial y revierte ese mensaje y el historial posterior antes de volver a intentarlo. Se trata de una solución alternativa reactiva, no de un sustituto de la gestión normal del presupuesto.

## 9. Continuación y compactación por parte del proveedor

Cuando sea compatible, el Responses API utiliza `previous_response_id` para continuar una cadena de respuestas sin reenviar desde el cliente todo el historial de respuestas gestionado por el proveedor.

Los flujos Responses API también envían la configuración de compactación del lado del proveedor utilizando el mismo umbral de reducción local. El comportamiento exacto depende del proveedor; el Artifact local y las políticas de historial siguen siendo las medidas de seguridad independientes del proveedor.

## 10. Eficiencia en el recuento de tokens

Los recuentos de tokens utilizados para las decisiones de compresión se almacenan en caché y se actualizan de forma incremental cuando solo se han añadido mensajes nuevos. Esto no reduce directamente el contexto del modelo, pero reduce el coste de CPU y la latencia a la hora de decidir cuándo es necesaria la compresión.

## Lo que aún no constituye una capa unificada completa

La implementación actual aún no proporciona todo lo siguiente como un único gestor independiente del proveedor:

- un `ContextManager` y un `ContextBudget` unificados;
- un `ToolResultRecord` con metadatos de importancia y expulsión;
- resúmenes semánticos que no requieran un `LLM`;
- la recuperación y reinyección automáticas de artefactos relevantes;
- un gestor de resultados central que garantice la conversión a `Artifact` para todas las herramientas que generen binarios; o
- una expulsión que tenga en cuenta las prioridades en todas las categorías de sistema, historial, esquema de herramientas y resultados.

En resumen, uag combina actualmente el truncamiento determinista, las referencias a Artifact, el aislamiento de binarios, la selección dinámica de herramientas, los resúmenes del historial, la continuidad del proveedor y la recuperación ante desbordamiento. La hoja de ruta de diseño para una capa de contexto unificada se documenta en [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
